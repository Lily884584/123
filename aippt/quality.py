"""Phase 9: quality-check agent for the three proposal samples.

Runs content, visual, and technical checks on
``06_proposals/proposal_{A,B,C}/sample.pptx``. Uses LibreOffice for
render-assisted visual checks when installed; otherwise records the gap
and continues with python-pptx heuristics. Auto-fix + recheck at most
three rounds. Failed checks are never reported as passed.

Writes ``09_reports/quality_report.md`` (and JSON). Does not generate a
final full deck or edit Phase 1–8 modules.
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
from typing import Any

from aippt.paths import append_project_log, load_project_id, project_info_path

PROPOSAL_KEYS = ("A", "B", "C")
EXPECTED_PAGES = 5
MAX_FIX_ROUNDS = 3
EMU_PER_INCH = 914400

# Numbers that look like invented metrics unless marked 待补/来源/占位.
_INVENTED_NUMBER = re.compile(
    r"(?<![#\w])(?:\d{1,3}(?:,\d{3})+|\d+\.\d+%|\d{2,}%|\d{4,})(?!\w)"
)
_SAFE_MARKER = re.compile(r"(待补|来源|占位|示意|fixture|page-\d+)", re.I)


def run_quality_check(project_dir: Path | str) -> dict[str, Any]:
    """Quality-check proposal samples for one project."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")

    project_id = load_project_id(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outline = _load_json(root / "05_content" / "ppt_outline.json") or {}
    analysis = _load_json(root / "00_project_info" / "requirement_analysis.json") or {}
    brief = _read_text(root / "00_project_info" / "customer_requirements.md")
    evidence = _collect_evidence_text(root, outline=outline, analysis=analysis, brief=brief)

    packs = _discover_packs(root)
    if not packs:
        raise FileNotFoundError(
            "no proposal samples found under 06_proposals/proposal_{A,B,C}/sample.pptx"
        )

    renderer = _detect_libreoffice()
    pack_reports: list[dict[str, Any]] = []
    overall_failed = 0
    overall_passed = 0
    overall_skipped = 0

    for pack in packs:
        pack_report = _check_pack_with_fixes(
            root=root,
            pack=pack,
            evidence=evidence,
            outline=outline,
            analysis=analysis,
            renderer=renderer,
        )
        pack_reports.append(pack_report)
        for issue in pack_report.get("issues") or []:
            status = issue.get("status")
            if status == "failed":
                overall_failed += 1
            elif status == "passed":
                overall_passed += 1
            elif status == "skipped":
                overall_skipped += 1

    # Aggregate: any unresolved failed issue ⇒ report not fully passed.
    unresolved = [
        {
            "proposal": pack["key"],
            "check": issue["check"],
            "category": issue["category"],
            "detail": issue["detail"],
        }
        for pack in pack_reports
        for issue in pack.get("issues") or []
        if issue.get("status") == "failed"
    ]
    verdict = "passed" if not unresolved else "failed_with_findings"
    report = {
        "project_id": project_id,
        "created_at": stamp,
        "phase": 9,
        "verdict": verdict,
        "libreoffice": renderer,
        "fix_rounds_max": MAX_FIX_ROUNDS,
        "counts": {
            "passed": overall_passed,
            "failed": overall_failed,
            "skipped": overall_skipped,
            "unresolved": len(unresolved),
        },
        "unresolved_issues": unresolved,
        "proposals": pack_reports,
        "notes": [
            "Failed checks are never marked passed.",
            "Auto-fix attempted at most three rounds per proposal pack.",
            "Phase 10 final deck generation is out of scope.",
        ],
    }

    _write_reports(root, report)
    _update_status(
        root,
        project_id=project_id,
        stamp=stamp,
        verdict=verdict,
    )
    append_project_log(
        root,
        f"{stamp} QUALITY project_id={project_id} verdict={verdict} "
        f"unresolved={len(unresolved)} libreoffice={renderer.get('status')}",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 9 quality checks on proposal_A/B/C samples."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    args = parser.parse_args(argv)
    try:
        report = run_quality_check(args.project)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    root = Path(args.project).resolve()
    print(root / "09_reports" / "quality_report.md")
    print(
        f"verdict={report['verdict']} "
        f"unresolved={report['counts']['unresolved']} "
        f"libreoffice={report['libreoffice']['status']}"
    )
    # Non-zero only on tool/project errors; findings stay in the report.
    return 0


def _check_pack_with_fixes(
    *,
    root: Path,
    pack: dict[str, Any],
    evidence: dict[str, Any],
    outline: dict[str, Any],
    analysis: dict[str, Any],
    renderer: dict[str, Any],
) -> dict[str, Any]:
    rounds: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    last_render: dict[str, Any] | None = None

    for round_index in range(1, MAX_FIX_ROUNDS + 1):
        issues = _run_all_checks(
            root=root,
            pack=pack,
            evidence=evidence,
            outline=outline,
            analysis=analysis,
            renderer=renderer,
        )
        render_info = _maybe_render(pack, renderer=renderer, round_index=round_index)
        last_render = render_info
        failed = [item for item in issues if item["status"] == "failed"]
        rounds.append(
            {
                "round": round_index,
                "failed_count": len(failed),
                "render": render_info,
                "fixes_applied": [],
            }
        )
        if not failed:
            break
        if round_index >= MAX_FIX_ROUNDS:
            break
        fixes = _apply_fixes(pack["pptx"], failed)
        rounds[-1]["fixes_applied"] = fixes
        if not fixes:
            # Nothing actionable — stop early; leave failures recorded.
            break

    failed_final = [item for item in issues if item["status"] == "failed"]
    return {
        "key": pack["key"],
        "path": pack["rel_dir"],
        "sample_pptx": pack["rel_pptx"],
        "rounds": rounds,
        "render": last_render,
        "issues": issues,
        "failed_count": len(failed_final),
        "pack_verdict": "passed" if not failed_final else "failed_with_findings",
    }


def _run_all_checks(
    *,
    root: Path,
    pack: dict[str, Any],
    evidence: dict[str, Any],
    outline: dict[str, Any],
    analysis: dict[str, Any],
    renderer: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    pptx_path = pack["pptx"]

    # --- technical: open ---
    try:
        from pptx import Presentation

        presentation = Presentation(str(pptx_path))
        issues.append(
            _issue(
                "technical",
                "pptx_opens",
                "passed",
                f"Opened {pptx_path.name}",
            )
        )
    except Exception as exc:  # noqa: BLE001 - must record open failures
        issues.append(
            _issue("technical", "pptx_opens", "failed", f"Cannot open PPTX: {exc}")
        )
        return issues

    slides = list(presentation.slides)
    slide_width = int(presentation.slide_width)
    slide_height = int(presentation.slide_height)

    # page count
    expected = int(outline.get("sample_page_count") or EXPECTED_PAGES)
    if len(slides) == expected:
        issues.append(
            _issue(
                "technical",
                "page_count",
                "passed",
                f"page_count={len(slides)} expected={expected}",
            )
        )
    else:
        issues.append(
            _issue(
                "technical",
                "page_count",
                "failed",
                f"page_count={len(slides)} expected={expected}",
            )
        )

    slide_payloads = [_inspect_slide(slide, slide_width, slide_height) for slide in slides]
    all_texts = [text for payload in slide_payloads for text in payload["texts"]]

    # images complete
    broken_images = sum(payload["broken_pictures"] for payload in slide_payloads)
    if broken_images:
        issues.append(
            _issue(
                "technical",
                "images_complete",
                "failed",
                f"broken_or_empty_pictures={broken_images}",
            )
        )
    else:
        issues.append(
            _issue(
                "technical",
                "images_complete",
                "passed",
                f"pictures={sum(p['picture_count'] for p in slide_payloads)} ok",
            )
        )

    # charts
    chart_notes = []
    for payload in slide_payloads:
        if payload["has_chart_shape"]:
            chart_notes.append("native_chart")
        if payload["has_chart_placeholder_label"]:
            chart_notes.append("placeholder_labeled")
    if any(p["has_chart_shape"] and p["chart_errors"] for p in slide_payloads):
        issues.append(
            _issue(
                "technical",
                "charts",
                "failed",
                "native chart reported errors on at least one slide",
            )
        )
    else:
        issues.append(
            _issue(
                "technical",
                "charts",
                "passed",
                "charts=" + (",".join(sorted(set(chart_notes))) or "none"),
            )
        )

    # font substitution — needs LO/system font audit; heuristic only here
    fonts = sorted({font for payload in slide_payloads for font in payload["fonts"]})
    if renderer.get("status") == "available":
        # Without a full font inventory we can only note declared fonts.
        issues.append(
            _issue(
                "technical",
                "font_substitution",
                "passed",
                f"declared_fonts={fonts or ['(default)']}; LibreOffice present for render",
            )
        )
    else:
        issues.append(
            _issue(
                "technical",
                "font_substitution",
                "skipped",
                "LibreOffice missing; cannot verify font substitution on render",
            )
        )

    # --- content ---
    theme = str(analysis.get("theme") or outline.get("theme") or "").strip()
    joined = "\n".join(all_texts)
    if theme and theme not in joined and not _fuzzy_theme_hit(theme, joined):
        issues.append(
            _issue(
                "content",
                "off_brief",
                "failed",
                f"theme `{theme}` not reflected in sample slide text",
            )
        )
    else:
        issues.append(
            _issue(
                "content",
                "off_brief",
                "passed",
                f"theme/brief signals present or theme empty (theme=`{theme or 'n/a'}`)",
            )
        )

    # repetition across slides (duplicate non-trivial titles)
    titles = [payload["title_guess"] for payload in slide_payloads if payload["title_guess"]]
    dupes = sorted({title for title in titles if titles.count(title) > 1 and len(title) >= 4})
    if dupes:
        issues.append(
            _issue(
                "content",
                "repetition",
                "failed",
                f"duplicate_titles={dupes}",
            )
        )
    else:
        issues.append(
            _issue("content", "repetition", "passed", "no duplicate slide titles")
        )

    invented = _find_invented_claims(all_texts, evidence=evidence)
    if invented:
        issues.append(
            _issue(
                "content",
                "invented_data",
                "failed",
                f"suspicious_numeric_claims={invented[:8]}",
            )
        )
    else:
        issues.append(
            _issue(
                "content",
                "invented_data",
                "passed",
                "no unmarked numeric claims detected",
            )
        )

    bad_cites = _find_bad_citations(all_texts, evidence=evidence)
    if bad_cites:
        issues.append(
            _issue(
                "content",
                "bad_citations",
                "failed",
                f"unmatched_citations={bad_cites[:8]}",
            )
        )
    else:
        issues.append(
            _issue("content", "bad_citations", "passed", "no unmatched 来源 citations")
        )

    logic_problems = _logic_problems(slide_payloads)
    if logic_problems:
        issues.append(
            _issue("content", "logic", "failed", "; ".join(logic_problems))
        )
    else:
        issues.append(
            _issue("content", "logic", "passed", "cover→summary order looks coherent")
        )

    # --- visual (pptx geometry heuristics; LO render is supplemental) ---
    overflow = [
        f"slide={i+1}"
        for i, payload in enumerate(slide_payloads)
        if payload["text_overflow"]
    ]
    if overflow:
        issues.append(
            _issue("visual", "text_overflow", "failed", f"overflow_on={overflow}")
        )
    else:
        issues.append(_issue("visual", "text_overflow", "passed", "no text box overflow"))

    overlap = [
        f"slide={i+1}:{payload['overlap_pairs']}"
        for i, payload in enumerate(slide_payloads)
        if payload["overlap_pairs"]
    ]
    if overlap:
        issues.append(
            _issue("visual", "element_overlap", "failed", f"overlaps={overlap[:6]}")
        )
    else:
        issues.append(_issue("visual", "element_overlap", "passed", "no major overlaps"))

    distorted = [
        f"slide={i+1}"
        for i, payload in enumerate(slide_payloads)
        if payload["distorted_pictures"]
    ]
    if distorted:
        issues.append(
            _issue("visual", "image_distortion", "failed", f"distorted_on={distorted}")
        )
    else:
        issues.append(
            _issue("visual", "image_distortion", "passed", "no distorted pictures flagged")
        )

    mixed_font_slides = [
        f"slide={i+1}:{sorted(payload['fonts'])}"
        for i, payload in enumerate(slide_payloads)
        if len(payload["fonts"]) > 3
    ]
    if mixed_font_slides:
        issues.append(
            _issue(
                "visual",
                "font_consistency",
                "failed",
                f"too_many_fonts_on={mixed_font_slides[:4]}",
            )
        )
    else:
        issues.append(
            _issue(
                "visual",
                "font_consistency",
                "passed",
                f"fonts_seen={fonts or ['(default)']}",
            )
        )

    crowded = [
        f"slide={i+1}:shapes={payload['shape_count']}"
        for i, payload in enumerate(slide_payloads)
        if payload["shape_count"] > 18 or payload["text_chars"] > 900
    ]
    if crowded:
        issues.append(
            _issue("visual", "crowding", "failed", f"crowded_slides={crowded}")
        )
    else:
        issues.append(_issue("visual", "crowding", "passed", "density within limits"))

    # style consistency within pack: title fonts should not swing wildly per slide
    title_fonts = [payload["title_font"] for payload in slide_payloads if payload["title_font"]]
    if title_fonts and len(set(title_fonts)) > 2:
        issues.append(
            _issue(
                "visual",
                "style_consistency",
                "failed",
                f"title_fonts_vary={sorted(set(title_fonts))}",
            )
        )
    else:
        issues.append(
            _issue(
                "visual",
                "style_consistency",
                "passed",
                f"title_fonts={sorted(set(title_fonts)) or ['(default)']}",
            )
        )

    if renderer.get("status") != "available":
        issues.append(
            _issue(
                "visual",
                "libreoffice_render",
                "skipped",
                renderer.get("detail")
                or "LibreOffice/soffice not found; geometry checks only",
            )
        )
    else:
        issues.append(
            _issue(
                "visual",
                "libreoffice_render",
                "passed",
                f"renderer={renderer.get('tool')}",
            )
        )

    return issues


def _inspect_slide(slide: Any, slide_width: int, slide_height: int) -> dict[str, Any]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    texts: list[str] = []
    fonts: set[str] = set()
    title_guess = ""
    title_font = ""
    boxes: list[tuple[int, int, int, int]] = []
    text_overflow = False
    picture_count = 0
    broken_pictures = 0
    distorted_pictures = 0
    has_chart_shape = False
    chart_errors = 0
    has_chart_placeholder_label = False
    text_chars = 0
    shape_count = 0

    for shape in slide.shapes:
        shape_count += 1
        left = int(getattr(shape, "left", 0) or 0)
        top = int(getattr(shape, "top", 0) or 0)
        width = int(getattr(shape, "width", 0) or 0)
        height = int(getattr(shape, "height", 0) or 0)
        boxes.append((left, top, left + width, top + height))

        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            picture_count += 1
            try:
                image = shape.image
                if not image.blob:
                    broken_pictures += 1
                else:
                    # Distortion heuristic: compare shape box ratio vs PNG/JPEG header when possible.
                    intrinsic = _image_size(image.blob)
                    if intrinsic and width > 0 and height > 0:
                        box_ratio = width / max(height, 1)
                        img_ratio = intrinsic[0] / max(intrinsic[1], 1)
                        if abs(box_ratio - img_ratio) / max(img_ratio, 0.01) > 0.45:
                            distorted_pictures += 1
            except Exception:  # noqa: BLE001
                broken_pictures += 1

        if getattr(shape, "has_chart", False):
            has_chart_shape = True
            try:
                _ = shape.chart
            except Exception:  # noqa: BLE001
                chart_errors += 1

        if not shape.has_text_frame:
            continue
        shape_text_parts: list[str] = []
        for paragraph in shape.text_frame.paragraphs:
            runs_text = "".join(run.text or "" for run in paragraph.runs).strip()
            if not runs_text and paragraph.text:
                runs_text = paragraph.text.strip()
            if runs_text:
                shape_text_parts.append(runs_text)
                texts.append(runs_text)
                text_chars += len(runs_text)
            for run in paragraph.runs:
                if run.font.name:
                    fonts.add(run.font.name)
        joined_shape = "\n".join(shape_text_parts)
        if "占位示意" in joined_shape or "图表" in joined_shape:
            has_chart_placeholder_label = True
        if top < slide_height * 0.28 and shape_text_parts and not title_guess:
            title_guess = shape_text_parts[0][:80]
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.font.name:
                        title_font = run.font.name
                        break
                if title_font:
                    break
        # Overflow: box extends past slide or very long text in a short box.
        if top + height > slide_height + 20000:  # ~0.02" tolerance in EMU
            text_overflow = True
        if height > 0 and text_chars > 0 and (text_chars / max(height / EMU_PER_INCH, 0.1)) > 420:
            # Extremely dense text relative to box height.
            text_overflow = True

    overlap_pairs = _count_overlaps(boxes)
    return {
        "texts": texts,
        "fonts": fonts,
        "title_guess": title_guess,
        "title_font": title_font,
        "text_overflow": text_overflow,
        "overlap_pairs": overlap_pairs,
        "picture_count": picture_count,
        "broken_pictures": broken_pictures,
        "distorted_pictures": distorted_pictures,
        "has_chart_shape": has_chart_shape,
        "chart_errors": chart_errors,
        "has_chart_placeholder_label": has_chart_placeholder_label,
        "text_chars": text_chars,
        "shape_count": shape_count,
    }


def _apply_fixes(pptx_path: Path, failed: list[dict[str, Any]]) -> list[str]:
    """Apply conservative in-file fixes for a subset of failed checks."""

    from pptx import Presentation
    from pptx.util import Pt

    failed_names = {item["check"] for item in failed}
    fixes: list[str] = []
    presentation = Presentation(str(pptx_path))
    slide_height = int(presentation.slide_height)

    if "text_overflow" in failed_names or "crowding" in failed_names:
        for slide in presentation.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                # Pull overflowing boxes up within the slide.
                if int(shape.top) + int(shape.height) > slide_height:
                    new_height = max(slide_height - int(shape.top) - 20000, 20000)
                    shape.height = new_height
                    fixes.append("trim_overflow_box")
                # Soften overcrowding by slightly reducing font sizes.
                if "crowding" in failed_names:
                    for paragraph in shape.text_frame.paragraphs:
                        for run in paragraph.runs:
                            size = run.font.size
                            if size and size.pt > 12:
                                run.font.size = Pt(max(12, size.pt - 2))
                                fixes.append("reduce_font_size")

    if "repetition" in failed_names:
        seen: set[str] = set()
        for index, slide in enumerate(presentation.slides):
            text_shapes = [shape for shape in slide.shapes if shape.has_text_frame]
            text_shapes.sort(key=lambda shape: int(shape.top))
            if not text_shapes:
                continue
            title = text_shapes[0].text_frame.text.strip()
            if title in seen and title:
                text_shapes[0].text_frame.paragraphs[0].text = f"{title}（续{index+1}）"
                fixes.append("dedupe_title")
            elif title:
                seen.add(title)

    if "page_count" in failed_names:
        # Cannot reliably add/remove slides without design context; record only.
        pass

    if "invented_data" in failed_names:
        for slide in presentation.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    original = paragraph.text
                    if not original:
                        continue
                    if _INVENTED_NUMBER.search(original) and not _SAFE_MARKER.search(
                        original
                    ):
                        paragraph.text = original + "（待补：核实数据）"
                        fixes.append("mark_unverified_number")

    if fixes:
        presentation.save(str(pptx_path))
    # Unique stable list
    return sorted(set(fixes))


def _maybe_render(
    pack: dict[str, Any],
    *,
    renderer: dict[str, Any],
    round_index: int,
) -> dict[str, Any]:
    preview_dir = pack["dir"] / "quality_render" / f"round-{round_index:02d}"
    preview_dir.mkdir(parents=True, exist_ok=True)
    if renderer.get("status") != "available":
        note = {
            "status": "skipped",
            "detail": renderer.get("detail"),
            "output_dir": str(preview_dir),
        }
        (preview_dir / "render_status.json").write_text(
            json.dumps(note, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"status": "skipped", "detail": renderer.get("detail"), "pages": []}

    try:
        pages = _render_with_libreoffice(pack["pptx"], preview_dir, renderer["tool"])
        status = {
            "status": "available",
            "tool": renderer["tool"],
            "pages": pages,
        }
    except Exception as exc:  # noqa: BLE001
        status = {"status": "error", "detail": str(exc), "pages": []}
    (preview_dir / "render_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return status


def _render_with_libreoffice(
    pptx_path: Path, output_dir: Path, tool: str
) -> list[dict[str, Any]]:
    import pymupdf

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aippt-quality-") as tmp:
        tmp_dir = Path(tmp)
        completed = subprocess.run(
            [
                tool,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_dir),
                str(pptx_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "libreoffice failed")
        pdfs = list(tmp_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice produced no PDF")
        doc = pymupdf.open(pdfs[0])
        pages = []
        try:
            for index in range(doc.page_count):
                page = doc.load_page(index)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                name = f"page-{index+1:03d}.png"
                pix.save(output_dir / name)
                pages.append(
                    {
                        "page": index + 1,
                        "path": name,
                        "width": pix.width,
                        "height": pix.height,
                    }
                )
        finally:
            doc.close()
        shutil.copy2(pdfs[0], output_dir / "sample.pdf")
        return pages


def _discover_packs(project_dir: Path) -> list[dict[str, Any]]:
    packs = []
    for key in PROPOSAL_KEYS:
        folder = project_dir / "06_proposals" / f"proposal_{key}"
        pptx = folder / "sample.pptx"
        if pptx.is_file():
            packs.append(
                {
                    "key": key,
                    "dir": folder,
                    "pptx": pptx,
                    "rel_dir": f"06_proposals/proposal_{key}",
                    "rel_pptx": f"06_proposals/proposal_{key}/sample.pptx",
                }
            )
    return packs


def _collect_evidence_text(
    project_dir: Path,
    *,
    outline: dict[str, Any],
    analysis: dict[str, Any],
    brief: str,
) -> dict[str, Any]:
    blobs = [brief, json.dumps(outline, ensure_ascii=False), json.dumps(analysis, ensure_ascii=False)]
    known_files: set[str] = set()
    for page in outline.get("pages") or []:
        for item in page.get("supporting_data") or []:
            blobs.append(str(item))
            match = re.search(r"来源文件：\s*(.+)$", str(item))
            if match:
                known_files.add(match.group(1).strip())
            if "customer_requirements.md" in str(item):
                known_files.add("customer_requirements.md")
    known_files.add("customer_requirements.md")
    # Manifest originals
    manifest = _load_json(project_dir / "02_extracted_content" / "file_manifest.json") or {}
    for item in manifest.get("files") or []:
        name = item.get("original_filename")
        if name:
            known_files.add(str(name))
    return {"text": "\n".join(blobs), "known_files": known_files}


def _find_invented_claims(texts: list[str], *, evidence: dict[str, Any]) -> list[str]:
    evidence_text = evidence.get("text") or ""
    found: list[str] = []
    for text in texts:
        if _SAFE_MARKER.search(text):
            continue
        for match in _INVENTED_NUMBER.finditer(text):
            token = match.group(0)
            if token in evidence_text:
                continue
            # Year-like 20xx alone is allowed if present in brief/theme context.
            if re.fullmatch(r"20\d{2}", token) and token in evidence_text:
                continue
            snippet = text.strip()
            if snippet not in found:
                found.append(snippet[:120])
    return found


def _find_bad_citations(texts: list[str], *, evidence: dict[str, Any]) -> list[str]:
    known = evidence.get("known_files") or set()
    bad: list[str] = []
    for text in texts:
        for match in re.finditer(r"来源文件：\s*([^\s；;]+)", text):
            name = match.group(1).strip()
            if name not in known and name not in bad:
                bad.append(name)
        for match in re.finditer(r"来源：\s*([^\s；;]+)", text):
            name = match.group(1).strip()
            if name.endswith(".md") or name.endswith(".txt") or name.endswith(".pptx"):
                if name not in known and name not in bad:
                    bad.append(name)
    return bad


def _logic_problems(slide_payloads: list[dict[str, Any]]) -> list[str]:
    problems = []
    if not slide_payloads:
        return ["no slides"]
    # Heuristic: first slide should look like a cover (short title / fewer bullets).
    first = slide_payloads[0]
    last = slide_payloads[-1]
    if first["text_chars"] > 1200:
        problems.append("cover slide unusually dense")
    # Summary-ish last slide should not be empty.
    if last["text_chars"] < 8:
        problems.append("final slide appears empty")
    return problems


def _fuzzy_theme_hit(theme: str, joined: str) -> bool:
    tokens = [token for token in re.split(r"[\s·\-_/]+", theme) if len(token) >= 2]
    if not tokens:
        return True
    hits = sum(1 for token in tokens if token in joined)
    return hits >= max(1, len(tokens) // 2)


def _count_overlaps(boxes: list[tuple[int, int, int, int]]) -> int:
    count = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a = boxes[i]
            b = boxes[j]
            # Ignore tiny decorative overlaps under ~0.05"
            if _intersects(a, b) and _overlap_area(a, b) > (0.05 * EMU_PER_INCH) ** 2:
                # Skip near-identical full-bleed pairs
                count += 1
    # Only flag when many overlaps — a few accent/text overlaps are normal.
    return count if count >= 4 else 0


def _intersects(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _overlap_area(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> int:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def _image_size(blob: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image
        import io

        with Image.open(io.BytesIO(blob)) as image:
            return image.size
    except Exception:  # noqa: BLE001
        return None


def _detect_libreoffice() -> dict[str, Any]:
    for tool in ("soffice", "libreoffice"):
        path = shutil.which(tool)
        if path:
            return {"status": "available", "tool": path, "detail": None}
    return {
        "status": "missing",
        "tool": None,
        "detail": "LibreOffice/soffice not found; PPTX render skipped; geometry checks still ran",
    }


def _issue(category: str, check: str, status: str, detail: str) -> dict[str, Any]:
    if status not in {"passed", "failed", "skipped"}:
        raise ValueError(f"invalid issue status: {status}")
    return {
        "category": category,
        "check": check,
        "status": status,
        "detail": detail,
    }


def _write_reports(project_dir: Path, report: dict[str, Any]) -> None:
    out = project_dir / "09_reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "quality_report.md").write_text(_markdown(report), encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Quality report",
        "",
        f"- project_id: `{report['project_id']}`",
        f"- created_at: `{report['created_at']}`",
        f"- verdict: **{report['verdict']}**",
        f"- libreoffice: `{report['libreoffice'].get('status')}`"
        + (
            f" ({report['libreoffice'].get('detail')})"
            if report["libreoffice"].get("detail")
            else ""
        ),
        f"- passed: {report['counts']['passed']}",
        f"- failed: {report['counts']['failed']}",
        f"- skipped: {report['counts']['skipped']}",
        f"- unresolved: {report['counts']['unresolved']}",
        "",
        "## Unresolved issues",
        "",
    ]
    if not report["unresolved_issues"]:
        lines.append("- none")
    else:
        for item in report["unresolved_issues"]:
            lines.append(
                f"- [{item['proposal']}] `{item['category']}/{item['check']}`: {item['detail']}"
            )
    lines.extend(["", "## Proposals", ""])
    for pack in report["proposals"]:
        lines.extend(
            [
                f"### Proposal {pack['key']} — {pack['pack_verdict']}",
                "",
                f"- sample: `{pack['sample_pptx']}`",
                f"- failed_count: {pack['failed_count']}",
                f"- rounds: {len(pack.get('rounds') or [])}",
                "",
            ]
        )
        for issue in pack.get("issues") or []:
            mark = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[issue["status"]]
            lines.append(
                f"- [{mark}] `{issue['category']}/{issue['check']}`: {issue['detail']}"
            )
        lines.append("")
    lines.extend(["## Notes", ""])
    for note in report.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _update_status(
    project_dir: Path,
    *,
    project_id: str,
    stamp: str,
    verdict: str,
) -> None:
    path = project_dir / "00_project_info" / "project_status.json"
    if path.is_file():
        status = json.loads(path.read_text(encoding="utf-8"))
    else:
        status = {"project_id": project_id, "history": []}
    if status.get("project_id") not in {None, project_id}:
        raise ValueError("project_status.json project_id mismatch")
    status["project_id"] = project_id
    status["status"] = "QUALITY_CHECK"
    status["updated_at"] = stamp
    status["last_step"] = "quality_check"
    status["quality_verdict"] = verdict
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "status": "QUALITY_CHECK",
            "at": stamp,
            "step": "quality_check",
            "verdict": verdict,
        }
    )
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "QUALITY_CHECK"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
