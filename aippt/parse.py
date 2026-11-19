"""Parse scanned project files into 02_extracted_content.

Phase 2 only. Reads originals from 01_input without modifying them.
Does not call vision models, search the network, or generate PPT files.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from aippt.paths import append_project_log, extracted_dir, load_project_id, manifest_path

DEFAULT_BATCH_SIZE = 10
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def parse_project(
    project_dir: Path | str,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Parse pending files listed in the project manifest."""

    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    root = Path(project_dir).resolve()
    project_id = load_project_id(root)
    man_path = manifest_path(root)
    if not man_path.is_file():
        raise FileNotFoundError(
            f"file manifest missing; run scan first: {man_path}"
        )
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    if manifest.get("project_id") != project_id:
        raise ValueError("manifest project_id does not match project_info.json")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    renderer = _detect_renderer()
    parsed = 0
    failed = 0

    for item in manifest["files"]:
        if item.get("project_id") != project_id:
            item["parse_status"] = "failed"
            item["error"] = "project_id mismatch"
            failed += 1
            continue
        if not item.get("supported"):
            continue
        if item.get("corrupt"):
            item["parse_status"] = "failed_corrupt"
            failed += 1
            continue
        if item.get("parse_status") not in {"pending", "failed", "parsed"}:
            # Allow re-parse of pending/failed/parsed; skip unsupported statuses.
            if item.get("parse_status") == "skipped_unsupported":
                continue

        source_path = root / "01_input" / item["relative_path"]
        if not source_path.is_file():
            item["parse_status"] = "failed"
            item["error"] = "source file missing"
            failed += 1
            continue

        before = source_path.stat()
        try:
            result_dir = _result_dir(root, item)
            if result_dir.exists():
                shutil.rmtree(result_dir)
            result_dir.mkdir(parents=True, exist_ok=True)
            payload = _parse_one(
                source_path=source_path,
                item=item,
                project_id=project_id,
                result_dir=result_dir,
                batch_size=batch_size,
                renderer=renderer,
            )
            (result_dir / "content.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            item["parse_status"] = "parsed"
            item["error"] = None
            item["result_path"] = result_dir.relative_to(root).as_posix()
            item["parsed_at"] = stamp
            parsed += 1
        except Exception as exc:  # noqa: BLE001 - record per-file failure
            item["parse_status"] = "failed"
            item["error"] = f"{type(exc).__name__}: {exc}"
            failed += 1
        after = source_path.stat()
        if (before.st_mtime_ns, before.st_size, before.st_ino) != (
            after.st_mtime_ns,
            after.st_size,
            after.st_ino,
        ):
            raise RuntimeError(
                f"original file changed during parse: {source_path}"
            )

    manifest["parsed_at"] = stamp
    manifest["parser"] = {
        "batch_size": batch_size,
        "pptx_renderer": renderer,
        "parsed_count": parsed,
        "failed_count": failed,
    }
    man_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_project_log(
        root,
        f"{stamp} PARSED project_id={project_id} parsed={parsed} failed={failed} "
        f"renderer={renderer.get('status')}",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse files listed in a project's file manifest."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Pages or rows processed per batch for large files.",
    )
    args = parser.parse_args(argv)
    try:
        manifest = parse_project(args.project, batch_size=args.batch_size)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    info = manifest.get("parser", {})
    print(manifest_path(Path(args.project).resolve()))
    print(
        f"parsed={info.get('parsed_count', 0)} failed={info.get('failed_count', 0)} "
        f"renderer={info.get('pptx_renderer', {}).get('status')}"
    )
    return 0


def _result_dir(project_dir: Path, item: dict) -> Path:
    fmt = item["format"]
    stem = Path(item["original_filename"]).stem
    safe = _SAFE.sub("_", stem).strip("._") or "file"
    short = item["sha256"][:8]
    return extracted_dir(project_dir) / fmt / f"{safe}__{short}"


def _parse_one(
    *,
    source_path: Path,
    item: dict,
    project_id: str,
    result_dir: Path,
    batch_size: int,
    renderer: dict,
) -> dict:
    fmt = item["format"]
    base = {
        "project_id": project_id,
        "original_filename": item["original_filename"],
        "source": item["source"],
        "relative_path": item["relative_path"],
        "format": fmt,
        "sha256": item["sha256"],
        "size_bytes": item["size_bytes"],
    }
    if fmt == "pptx":
        body = _parse_pptx(source_path, result_dir, batch_size, renderer)
    elif fmt == "pdf":
        body = _parse_pdf(source_path, result_dir, batch_size)
    elif fmt == "docx":
        body = _parse_docx(source_path, batch_size)
    elif fmt == "xlsx":
        body = _parse_xlsx(source_path, batch_size)
    elif fmt == "images":
        body = _parse_image(source_path)
    elif fmt == "text":
        body = _parse_text(source_path, batch_size)
    else:
        raise ValueError(f"unsupported format: {fmt}")
    base.update(body)
    return base


def _parse_pptx(
    path: Path,
    result_dir: Path,
    batch_size: int,
    renderer: dict,
) -> dict:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    presentation = Presentation(str(path))
    slides = []
    for index, slide in enumerate(presentation.slides, start=1):
        texts = []
        images = 0
        charts = 0
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in paragraph.runs).strip()
                    if line:
                        texts.append(line)
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                images += 1
            if shape.has_chart:
                charts += 1
        slides.append(
            {
                "page": index,
                "texts": texts,
                "image_count": images,
                "chart_count": charts,
            }
        )

    render_info = {
        "status": renderer["status"],
        "tool": renderer.get("tool"),
        "detail": renderer.get("detail"),
        "pages": [],
    }
    if renderer["status"] == "available":
        render_info["pages"] = _render_pptx_pages(
            path, result_dir / "pages", batch_size, renderer
        )
    else:
        render_info["detail"] = renderer.get("detail") or (
            "LibreOffice/soffice not found; text extracted without page images"
        )

    return {
        "page_count": len(slides),
        "slides": slides,
        "render": render_info,
    }


def _parse_pdf(path: Path, result_dir: Path, batch_size: int) -> dict:
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    page_images = []
    pages_dir = result_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    try:
        total = doc.page_count
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            for index in range(start, end):
                page = doc.load_page(index)
                page_number = index + 1
                text = page.get_text("text")
                tables = []
                try:
                    finder = page.find_tables()
                    for table in finder.tables:
                        tables.append(table.extract())
                except Exception:  # noqa: BLE001 - table detection is best-effort
                    tables = []
                pages.append(
                    {
                        "page": page_number,
                        "text": text,
                        "tables": tables,
                        "width": page.rect.width,
                        "height": page.rect.height,
                    }
                )
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image_name = f"page-{page_number:03d}.png"
                pix.save(pages_dir / image_name)
                page_images.append(
                    {
                        "page": page_number,
                        "path": f"pages/{image_name}",
                        "width": pix.width,
                        "height": pix.height,
                    }
                )
    finally:
        doc.close()
    return {
        "page_count": len(pages),
        "pages": pages,
        "render": {"status": "available", "tool": "pymupdf", "pages": page_images},
    }


def _parse_docx(path: Path, batch_size: int) -> dict:
    import docx

    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    tables = []
    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            rows.append([cell.text for cell in row.cells])
        tables.append({"table": table_index, "rows": rows})

    batches = [
        paragraphs[index : index + batch_size]
        for index in range(0, len(paragraphs), batch_size)
    ] or [[]]
    return {
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
        "paragraph_batches": len(batches),
        "tables": tables,
    }


def _parse_xlsx(path: Path, batch_size: int) -> dict:
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        sheets = []
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows = []
            batch = []
            for row in sheet.iter_rows(values_only=True):
                values = ["" if cell is None else cell for cell in row]
                batch.append(values)
                if len(batch) >= batch_size:
                    rows.extend(batch)
                    batch = []
            if batch:
                rows.extend(batch)
            sheets.append(
                {
                    "name": sheet_name,
                    "row_count": len(rows),
                    "rows": rows,
                }
            )
    finally:
        workbook.close()
    return {"sheet_count": len(sheets), "sheets": sheets}


def _parse_image(path: Path) -> dict:
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        fmt = image.format
    return {
        "width": width,
        "height": height,
        "mode": mode,
        "image_format": fmt,
        "vision_analysis": None,
        "note": "Phase 2 records dimensions only; no vision-model calls",
    }


def _parse_text(path: Path, batch_size: int) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    batches = [
        lines[index : index + batch_size]
        for index in range(0, len(lines), batch_size)
    ] or [[]]
    return {
        "line_count": len(lines),
        "char_count": len(text),
        "lines": lines,
        "line_batches": len(batches),
    }


def _detect_renderer() -> dict:
    for tool in ("soffice", "libreoffice"):
        path = shutil.which(tool)
        if path:
            return {"status": "available", "tool": path, "detail": None}
    return {
        "status": "missing",
        "tool": None,
        "detail": "LibreOffice/soffice not found; PPTX page images skipped",
    }


def _render_pptx_pages(
    path: Path,
    pages_dir: Path,
    batch_size: int,
    renderer: dict,
) -> list[dict]:
    import pymupdf

    pages_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aippt-pptx-") as tmp:
        tmp_dir = Path(tmp)
        command = [
            renderer["tool"],
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_dir),
            str(path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "LibreOffice failed to convert PPTX: "
                + (completed.stderr or completed.stdout or "no output")
            )
        pdfs = list(tmp_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice produced no PDF for PPTX render")
        doc = pymupdf.open(pdfs[0])
        rendered = []
        try:
            total = doc.page_count
            for start in range(0, total, batch_size):
                end = min(start + batch_size, total)
                for index in range(start, end):
                    page = doc.load_page(index)
                    page_number = index + 1
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                    image_name = f"page-{page_number:03d}.png"
                    pix.save(pages_dir / image_name)
                    rendered.append(
                        {
                            "page": page_number,
                            "path": f"pages/{image_name}",
                            "width": pix.width,
                            "height": pix.height,
                        }
                    )
        finally:
            doc.close()
        return rendered


if __name__ == "__main__":
    raise SystemExit(main())
