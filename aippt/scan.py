"""Scan a project's 01_input tree and write a file manifest.

Phase 2 only. Originals under 01_input are never written or deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from aippt.formats import INPUT_SUBDIRS, format_for_extension, normalize_extension
from aippt.paths import append_project_log, load_project_id, manifest_path

CHUNK_SIZE = 1024 * 1024


def scan_project(project_dir: Path | str) -> dict:
    """Scan ``01_input`` and write ``02_extracted_content/file_manifest.json``."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")
    input_root = root / "01_input"
    if not input_root.is_dir():
        raise FileNotFoundError(f"01_input missing: {input_root}")

    project_id = load_project_id(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files: list[dict] = []

    for source in INPUT_SUBDIRS:
        folder = input_root / source
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith(".") or path.name == ".gitkeep":
                continue
            relative = path.relative_to(input_root).as_posix()
            extension = normalize_extension(path.name)
            fmt = format_for_extension(extension)
            if fmt is None:
                files.append(
                    {
                        "project_id": project_id,
                        "relative_path": relative,
                        "source": source,
                        "original_filename": path.name,
                        "format": None,
                        "extension": extension or None,
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                        "supported": False,
                        "corrupt": False,
                        "parse_status": "skipped_unsupported",
                        "error": "unsupported format",
                    }
                )
                continue
            size = path.stat().st_size
            digest = _sha256(path)
            corrupt, corrupt_error = _quick_corrupt_check(path, fmt)
            files.append(
                {
                    "project_id": project_id,
                    "relative_path": relative,
                    "source": source,
                    "original_filename": path.name,
                    "format": fmt,
                    "extension": extension,
                    "size_bytes": size,
                    "sha256": digest,
                    "supported": True,
                    "corrupt": corrupt,
                    "parse_status": "pending" if not corrupt else "failed_corrupt",
                    "error": corrupt_error,
                }
            )

    by_hash: dict[str, list[str]] = {}
    for item in files:
        by_hash.setdefault(item["sha256"], []).append(item["relative_path"])
    duplicates = {
        digest: paths for digest, paths in by_hash.items() if len(paths) > 1
    }
    for item in files:
        twins = duplicates.get(item["sha256"], [])
        item["duplicate"] = len(twins) > 1
        item["duplicate_of"] = [path for path in twins if path != item["relative_path"]]

    manifest = {
        "project_id": project_id,
        "scanned_at": stamp,
        "input_root": "01_input",
        "file_count": len(files),
        "supported_count": sum(1 for item in files if item["supported"]),
        "duplicate_groups": [
            {"sha256": digest, "paths": paths}
            for digest, paths in sorted(duplicates.items())
        ],
        "files": files,
    }
    out = manifest_path(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_project_log(
        root,
        f"{stamp} SCANNED project_id={project_id} files={len(files)} "
        f"supported={manifest['supported_count']} duplicates={len(duplicates)}",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan a project's 01_input folder and write a file manifest."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    args = parser.parse_args(argv)
    try:
        manifest = scan_project(args.project)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(manifest_path(Path(args.project).resolve()))
    print(
        f"files={manifest['file_count']} supported={manifest['supported_count']} "
        f"duplicate_groups={len(manifest['duplicate_groups'])}"
    )
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _quick_corrupt_check(path: Path, fmt: str) -> tuple[bool, str | None]:
    """Lightweight open checks. Does not modify the file."""

    try:
        if fmt == "pptx":
            from pptx import Presentation

            Presentation(str(path))
        elif fmt == "pdf":
            import pymupdf

            doc = pymupdf.open(path)
            try:
                if doc.page_count < 0:
                    return True, "pdf reports negative page count"
                if doc.is_encrypted and not doc.authenticate(""):
                    return True, "pdf is encrypted"
            finally:
                doc.close()
        elif fmt == "docx":
            import docx

            docx.Document(str(path))
        elif fmt == "xlsx":
            import openpyxl

            openpyxl.load_workbook(str(path), read_only=True, data_only=True).close()
        elif fmt == "images":
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
        elif fmt == "text":
            path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - record any open failure as corrupt
        return True, f"{type(exc).__name__}: {exc}"
    return False, None


if __name__ == "__main__":
    raise SystemExit(main())
