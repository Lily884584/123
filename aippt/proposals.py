"""Phase 8: three differentiated proposal samples (A/B/C).

Writes ``06_proposals/proposal_{A,B,C}/`` with ``sample.pptx``, ``preview/``,
and ``design_description.md``. Uses the same core outline content for all
three. Does not run quality checks or produce a final full deck.
Does not modify Phase 1–7 modules or ``01_input/`` originals.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aippt.paths import append_project_log, load_project_id, project_info_path

PROPOSAL_KEYS = ("A", "B", "C")
SAMPLE_PAGE_COUNT = 5  # cover / section / analysis / chart / summary
EMU_PER_INCH = 914400

# Base style identities (SOP §9). Soft-adjusted from project design_style.
BASE_STYLES: dict[str, dict[str, Any]] = {
    "A": {
        "code": "A",
        "name": "高端极简风",
        "positioning": "留白优先、少装饰、强层级，适合品牌/高管场景。",
        "background": "#F7F7F5",
        "primary": "#111111",
        "accent": "#C2A878",
        "text": "#1A1A1A",
        "muted": "#6B6B6B",
        "panel": "#EFEFEA",
        "title_font": "Georgia",
        "body_font": "Calibri",
        "title_size": 34,
        "body_size": 15,
        "accent_bar": "top_thin",
        "density": "sparse",
    },
    "B": {
        "code": "B",
        "name": "商业咨询风",
        "positioning": "结构清晰、论证导向，适合对客户/管理层的商务汇报。",
        "background": "#FFFFFF",
        "primary": "#0B1F3A",
        "accent": "#2F6FED",
        "text": "#0B1F3A",
        "muted": "#4A5568",
        "panel": "#EEF3FA",
        "title_font": "Calibri",
        "body_font": "Calibri",
        "title_size": 30,
        "body_size": 15,
        "accent_bar": "left_thick",
        "density": "structured",
    },
    "C": {
        "code": "C",
        "name": "科技创意风",
        "positioning": "几何点缀与冷色强调，适合产品/技术发布场景。",
        "background": "#0B1220",
        "primary": "#7DD3FC",
        "accent": "#22D3EE",
        "text": "#E2E8F0",
        "muted": "#94A3B8",
        "panel": "#152033",
        "title_font": "Arial",
        "body_font": "Arial",
        "title_size": 32,
        "body_size": 15,
        "accent_bar": "corner_block",
        "density": "expressive",
    },
}


def build_proposals(project_dir: Path | str) -> dict[str, Any]:
    """Generate three proposal sample packs for one project."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")

    project_id = load_project_id(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outline = _require_json(root / "05_content" / "ppt_outline.json", "outline")
    analysis = _load_json(root / "00_project_info" / "requirement_analysis.json") or {}
    design = _load_design(root)
    sample_pages = _select_sample_pages(outline)
    styles = _resolve_styles(analysis=analysis, design=design)

    proposals_root = root / "06_proposals"
    proposal_results: list[dict[str, Any]] = []
    for key in PROPOSAL_KEYS:
        style = styles[key]
        folder = proposals_root / f"proposal_{key}"
        folder.mkdir(parents=True, exist_ok=True)
        pptx_path = folder / "sample.pptx"
        build_meta = _build_sample_pptx(
            output_path=pptx_path,
            pages=sample_pages,
            style=style,
            theme=str(outline.get("theme") or analysis.get("theme") or "Untitled"),
        )
        preview_meta = _write_preview(folder / "preview", pptx_path, sample_pages, style)
        desc_path = folder / "design_description.md"
        desc_path.write_text(
            _design_description_markdown(
                project_id=project_id,
                created_at=stamp,
                style=style,
                pages=sample_pages,
                analysis=analysis,
                build_meta=build_meta,
            ),
            encoding="utf-8",
        )
        proposal_results.append(
            {
                "key": key,
                "name": style["name"],
                "path": f"06_proposals/proposal_{key}",
                "sample_pptx": f"06_proposals/proposal_{key}/sample.pptx",
                "preview_dir": f"06_proposals/proposal_{key}/preview",
                "design_description": f"06_proposals/proposal_{key}/design_description.md",
                "page_count": len(sample_pages),
                "preview": preview_meta,
            }
        )

    report = {
        "project_id": project_id,
        "created_at": stamp,
        "phase": 8,
        "sample_page_count": len(sample_pages),
        "shared_core_titles": [page["title"] for page in sample_pages],
        "shared_core_roles": [page["sample_role"] for page in sample_pages],
        "proposals": proposal_results,
        "notes": [
            "Three samples share the same core content for comparison.",
            "No invented numeric claims; missing evidence stays 待补.",
            "Phase 9 quality check and Phase 10 final delivery are out of scope.",
        ],
    }
    report_dir = proposals_root
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "proposals_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "proposals_report.md").write_text(
        _proposals_report_markdown(report),
        encoding="utf-8",
    )
    _update_status(root, project_id=project_id, stamp=stamp)
    append_project_log(
        root,
        f"{stamp} PROPOSALS project_id={project_id} packs=3 "
        f"pages_each={len(sample_pages)}",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate three differentiated PPT proposal samples (A/B/C)."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    args = parser.parse_args(argv)
    try:
        report = build_proposals(args.project)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    root = Path(args.project).resolve()
    print(root / "06_proposals" / "proposals_report.md")
    print(
        f"packs=3 pages_each={report['sample_page_count']} "
        f"titles={len(report['shared_core_titles'])}"
    )
    return 0


def _select_sample_pages(outline: dict[str, Any]) -> list[dict[str, Any]]:
    pages = outline.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("outline must contain pages")

    by_role: dict[str, list[dict[str, Any]]] = {}
    for page in pages:
        role = str(page.get("role") or "content")
        by_role.setdefault(role, []).append(page)

    def pick(roles: tuple[str, ...], fallback_index: int) -> dict[str, Any]:
        for role in roles:
            if by_role.get(role):
                return dict(by_role[role][0])
        return dict(pages[min(fallback_index, len(pages) - 1)])

    selected = [
        {**pick(("cover",), 0), "sample_role": "cover"},
        {**pick(("agenda", "section", "context"), 1), "sample_role": "section"},
        {
            **pick(("content", "context", "analysis"), min(2, len(pages) - 1)),
            "sample_role": "analysis",
        },
        {
            **pick(("data", "content"), min(3, len(pages) - 1)),
            "sample_role": "chart",
        },
        {
            **pick(("summary", "next_steps", "content"), len(pages) - 1),
            "sample_role": "summary",
        },
    ]

    # Keep exactly 5 sample pages (within SOP 3–5, covering required types).
    if len(selected) != SAMPLE_PAGE_COUNT:
        raise ValueError("internal error: sample page count mismatch")

    # Sanitize: never invent numbers; keep 待补 markers from outline.
    cleaned: list[dict[str, Any]] = []
    for page in selected:
        support = []
        for item in page.get("supporting_data") or []:
            text = str(item).strip()
            if text:
                support.append(text)
        if not support:
            support = ["待补：来自客户资料的证据"]
        cleaned.append(
            {
                "page": page.get("page"),
                "title": str(page.get("title") or "待补：标题").strip(),
                "purpose": str(page.get("purpose") or "待补：本页目的").strip(),
                "core_point": str(page.get("core_point") or "待补：核心观点").strip(),
                "supporting_data": support,
                "image_suggestion": str(page.get("image_suggestion") or "无").strip(),
                "chart_suggestion": str(page.get("chart_suggestion") or "无").strip(),
                "recommended_layout": str(
                    page.get("recommended_layout") or "title_body"
                ).strip(),
                "role": str(page.get("role") or "content"),
                "sample_role": page["sample_role"],
            }
        )
    return cleaned


def _resolve_styles(
    *,
    analysis: dict[str, Any],
    design: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    styles = {key: dict(BASE_STYLES[key]) for key in PROPOSAL_KEYS}
    requested = str(analysis.get("design_style") or "").strip()
    palette = (design or {}).get("color_palette") or {}

    # Soft-adjust B toward stated business style; keep A/C identities distinct.
    if requested:
        styles["B"]["positioning"] = (
            f"{styles['B']['positioning']} 客户偏好风格参考：{requested}。"
        )
        styles["A"]["positioning"] = (
            f"{styles['A']['positioning']} 相对客户偏好「{requested}」更克制留白。"
        )
        styles["C"]["positioning"] = (
            f"{styles['C']['positioning']} 相对客户偏好「{requested}」更强调科技差异。"
        )

    # Optionally borrow design-system accent into B (consulting) without collapsing A/C.
    if palette.get("primary") and _looks_hex(palette["primary"]):
        styles["B"]["primary"] = str(palette["primary"])
    if palette.get("accent") and _looks_hex(palette["accent"]):
        styles["B"]["accent"] = str(palette["accent"])
    if palette.get("text") and _looks_hex(palette["text"]):
        styles["B"]["text"] = str(palette["text"])

    typography = (design or {}).get("typography") or {}
    title_font = ((typography.get("title") or {}).get("font")) or None
    body_font = ((typography.get("body") or {}).get("font")) or None
    if title_font:
        styles["B"]["title_font"] = title_font
    if body_font:
        styles["B"]["body_font"] = body_font

    page = ((design or {}).get("design_tokens") or {}).get("page") or {}
    width_in = float(page.get("width_in") or 13.333)
    height_in = float(page.get("height_in") or 7.5)
    for style in styles.values():
        style["width_in"] = width_in
        style["height_in"] = height_in
    return styles


def _build_sample_pptx(
    *,
    output_path: Path,
    pages: list[dict[str, Any]],
    style: dict[str, Any],
    theme: str,
) -> dict[str, Any]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.util import Inches, Pt

    presentation = Presentation()
    presentation.slide_width = Inches(float(style["width_in"]))
    presentation.slide_height = Inches(float(style["height_in"]))
    blank = presentation.slide_layouts[6]
    width_in = float(style["width_in"])
    height_in = float(style["height_in"])

    for page in pages:
        slide = presentation.slides.add_slide(blank)
        _set_slide_background(slide, style["background"])
        _draw_chrome(slide, style, width_in=width_in, height_in=height_in)

        role = page["sample_role"]
        margin_l = 0.85 if style["accent_bar"] != "left_thick" else 1.05
        margin_t = 0.7

        title_box = slide.shapes.add_textbox(
            Inches(margin_l),
            Inches(margin_t),
            Inches(width_in - margin_l - 0.7),
            Inches(1.1),
        )
        title_frame = title_box.text_frame
        title_frame.word_wrap = True
        title_text = page["title"]
        if role == "cover":
            title_text = theme if theme else page["title"]
        title_frame.text = title_text
        _style_run(
            title_frame.paragraphs[0],
            font=style["title_font"],
            size=float(style["title_size"]) + (4 if role == "cover" else 0),
            color=style["text"],
            bold=True,
        )

        if role == "cover":
            sub = slide.shapes.add_textbox(
                Inches(margin_l),
                Inches(2.1),
                Inches(width_in * 0.6),
                Inches(1.4),
            )
            sub.text_frame.word_wrap = True
            sub.text_frame.text = page["core_point"]
            _style_run(
                sub.text_frame.paragraphs[0],
                font=style["body_font"],
                size=float(style["body_size"]) + 2,
                color=style["muted"],
                bold=False,
            )
            _add_bullets(
                slide,
                left=margin_l,
                top=3.7,
                width=width_in * 0.55,
                height=2.2,
                lines=page["supporting_data"][:4],
                style=style,
            )
        elif role == "section":
            _add_bullets(
                slide,
                left=margin_l,
                top=2.1,
                width=width_in - margin_l - 0.8,
                height=4.2,
                lines=[page["core_point"], *page["supporting_data"][:4]],
                style=style,
                numbered=True,
            )
        elif role == "chart":
            _add_bullets(
                slide,
                left=margin_l,
                top=2.0,
                width=width_in * 0.42,
                height=4.0,
                lines=[page["core_point"], *page["supporting_data"][:3]],
                style=style,
            )
            _add_chart_panel(
                slide,
                left=width_in * 0.52,
                top=2.0,
                width=width_in * 0.4,
                height=3.8,
                style=style,
                suggestion=page["chart_suggestion"],
            )
        elif role == "summary":
            _add_bullets(
                slide,
                left=margin_l,
                top=2.0,
                width=width_in - margin_l - 0.8,
                height=3.6,
                lines=[page["core_point"], *page["supporting_data"][:5]],
                style=style,
            )
            footer = slide.shapes.add_textbox(
                Inches(margin_l),
                Inches(height_in - 1.0),
                Inches(width_in - margin_l - 0.8),
                Inches(0.5),
            )
            footer.text_frame.text = "下一步：待用户确认样稿后进入完整制作（Phase 10）。"
            _style_run(
                footer.text_frame.paragraphs[0],
                font=style["body_font"],
                size=12,
                color=style["muted"],
                bold=False,
            )
        else:  # analysis
            _add_bullets(
                slide,
                left=margin_l,
                top=2.0,
                width=width_in * 0.55,
                height=4.2,
                lines=[page["core_point"], *page["supporting_data"][:5]],
                style=style,
            )
            panel = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(width_in * 0.62),
                Inches(2.1),
                Inches(width_in * 0.3),
                Inches(3.2),
            )
            panel.fill.solid()
            panel.fill.fore_color.rgb = _rgb(style["panel"])
            panel.line.fill.background()
            note = slide.shapes.add_textbox(
                Inches(width_in * 0.62 + 0.2),
                Inches(2.4),
                Inches(width_in * 0.3 - 0.4),
                Inches(2.5),
            )
            note.text_frame.word_wrap = True
            note.text_frame.text = page["purpose"]
            _style_run(
                note.text_frame.paragraphs[0],
                font=style["body_font"],
                size=13,
                color=style["muted"],
                bold=False,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(output_path))
    return {
        "pages_written": len(pages),
        "width_in": width_in,
        "height_in": height_in,
        "style_code": style["code"],
    }


def _draw_chrome(
    slide: Any,
    style: dict[str, Any],
    *,
    width_in: float,
    height_in: float,
) -> None:
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.util import Inches

    kind = style["accent_bar"]
    if kind == "top_thin":
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0.85),
            Inches(0.35),
            Inches(1.8),
            Inches(0.06),
        )
    elif kind == "left_thick":
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0),
            Inches(0),
            Inches(0.28),
            Inches(height_in),
        )
    else:  # corner_block
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(width_in - 1.4),
            Inches(0),
            Inches(1.4),
            Inches(0.35),
        )
        geo = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RIGHT_TRIANGLE,
            Inches(width_in - 2.2),
            Inches(height_in - 1.6),
            Inches(1.5),
            Inches(1.2),
        )
        geo.fill.solid()
        geo.fill.fore_color.rgb = _rgb(style["panel"])
        geo.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(style["accent"])
    bar.line.fill.background()


def _add_bullets(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    lines: list[str],
    style: dict[str, Any],
    numbered: bool = False,
) -> None:
    from pptx.util import Inches

    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.clear()
    use_lines = [line for line in lines if str(line).strip()] or ["待补"]
    for index, line in enumerate(use_lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        prefix = f"{index + 1}. " if numbered else ("• " if index else "")
        paragraph.text = f"{prefix}{line}"
        paragraph.level = 0
        _style_run(
            paragraph,
            font=style["body_font"],
            size=float(style["body_size"]) if index == 0 and not numbered else float(style["body_size"]),
            color=style["text"] if index == 0 else style["muted"],
            bold=index == 0 and not numbered,
        )


def _add_chart_panel(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    style: dict[str, Any],
    suggestion: str,
) -> None:
    """Non-numeric decorative bars + explicit 待补 label — no invented data."""

    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.util import Inches

    panel = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    panel.fill.solid()
    panel.fill.fore_color.rgb = _rgb(style["panel"])
    panel.line.fill.background()

    # Relative placeholder heights only — caption states data is pending.
    ratios = (0.35, 0.55, 0.45, 0.65)
    gap = 0.12
    bar_w = (width - 0.5 - gap * (len(ratios) - 1)) / len(ratios)
    base_top = top + 0.55
    max_h = height - 1.6
    for index, ratio in enumerate(ratios):
        bar_h = max_h * ratio
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(left + 0.25 + index * (bar_w + gap)),
            Inches(base_top + max_h - bar_h),
            Inches(bar_w),
            Inches(bar_h),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = _rgb(style["accent"])
        bar.line.fill.background()

    caption = slide.shapes.add_textbox(
        Inches(left + 0.2),
        Inches(top + height - 0.9),
        Inches(width - 0.4),
        Inches(0.7),
    )
    hint = suggestion if suggestion and suggestion not in {"无", "none", "N/A"} else "图表"
    caption.text_frame.word_wrap = True
    caption.text_frame.text = f"{hint}（占位示意，数值待补：勿当作真实数据）"
    _style_run(
        caption.text_frame.paragraphs[0],
        font=style["body_font"],
        size=11,
        color=style["muted"],
        bold=False,
    )


def _write_preview(
    preview_dir: Path,
    pptx_path: Path,
    pages: list[dict[str, Any]],
    style: dict[str, Any],
) -> dict[str, Any]:
    """Write preview PNGs from slide titles (Pillow), never inventing content."""

    from PIL import Image, ImageDraw, ImageFont

    preview_dir.mkdir(parents=True, exist_ok=True)
    for old in preview_dir.glob("page-*.png"):
        old.unlink()

    width, height = 1280, 720
    written = []
    for index, page in enumerate(pages, start=1):
        image = Image.new("RGB", (width, height), color=_hex_to_rgb(style["background"]))
        draw = ImageDraw.Draw(image)
        accent = _hex_to_rgb(style["accent"])
        text_color = _hex_to_rgb(style["text"])
        muted = _hex_to_rgb(style["muted"])
        if style["accent_bar"] == "left_thick":
            draw.rectangle([0, 0, 28, height], fill=accent)
        elif style["accent_bar"] == "top_thin":
            draw.rectangle([80, 40, 260, 48], fill=accent)
        else:
            draw.rectangle([width - 160, 0, width, 36], fill=accent)

        title = page["title"][:60]
        role = page["sample_role"]
        draw.text((80, 90), f"Proposal {style['code']} · {style['name']}", fill=muted)
        draw.text((80, 160), title, fill=text_color)
        draw.text((80, 260), f"role: {role}", fill=muted)
        draw.text((80, 320), page["core_point"][:90], fill=text_color)
        filename = f"page-{index:03d}.png"
        image.save(preview_dir / filename, format="PNG")
        written.append({"page": index, "path": filename, "title": page["title"], "role": role})

    manifest = {
        "renderer": "pillow_title_cards",
        "note": (
            "Preview cards mirror sample page titles/core points from the outline; "
            "they are not photographic slide captures."
        ),
        "pages": written,
        "source_pptx": pptx_path.name,
    }
    (preview_dir / "preview_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (preview_dir / "README.md").write_text(
        "# Preview\n\n"
        f"- style: Proposal {style['code']} {style['name']}\n"
        f"- pages: {len(written)}\n"
        f"- renderer: `{manifest['renderer']}`\n\n"
        + "\n".join(
            f"- `{item['path']}` — {item['role']}: {item['title']}" for item in written
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _design_description_markdown(
    *,
    project_id: str,
    created_at: str,
    style: dict[str, Any],
    pages: list[dict[str, Any]],
    analysis: dict[str, Any],
    build_meta: dict[str, Any],
) -> str:
    lines = [
        f"# Proposal {style['code']} — {style['name']}",
        "",
        f"- project_id: `{project_id}`",
        f"- created_at: `{created_at}`",
        f"- positioning: {style['positioning']}",
        f"- customer_design_style: {analysis.get('design_style') or '待补'}",
        f"- page_count: {build_meta['pages_written']}",
        "",
        "## Visual system",
        "",
        f"- background: `{style['background']}`",
        f"- primary: `{style['primary']}`",
        f"- accent: `{style['accent']}`",
        f"- text: `{style['text']}`",
        f"- title_font: {style['title_font']} / {style['title_size']}pt",
        f"- body_font: {style['body_font']} / {style['body_size']}pt",
        f"- accent_motif: `{style['accent_bar']}`",
        f"- density: `{style['density']}`",
        "",
        "## Shared sample pages (same core across A/B/C)",
        "",
    ]
    for page in pages:
        lines.extend(
            [
                f"### {page['sample_role']}: {page['title']}",
                "",
                f"- core_point: {page['core_point']}",
                "- supporting_data:",
            ]
        )
        for item in page["supporting_data"]:
            lines.append(f"  - {item}")
        lines.append("")
    lines.extend(
        [
            "## Scope notes",
            "",
            "- This is a 3–5 page comparison sample, not the final full deck.",
            "- Chart panels are labeled 待补 and must not be read as real metrics.",
            "",
        ]
    )
    return "\n".join(lines)


def _proposals_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Proposals report",
        "",
        f"- project_id: `{report['project_id']}`",
        f"- created_at: `{report['created_at']}`",
        f"- sample_page_count: {report['sample_page_count']}",
        "",
        "## Shared core",
        "",
    ]
    for title, role in zip(
        report["shared_core_titles"], report["shared_core_roles"], strict=True
    ):
        lines.append(f"- `{role}`: {title}")
    lines.extend(["", "## Packs", ""])
    for item in report["proposals"]:
        lines.extend(
            [
                f"### Proposal {item['key']} — {item['name']}",
                "",
                f"- path: `{item['path']}`",
                f"- sample: `{item['sample_pptx']}`",
                f"- preview: `{item['preview_dir']}`",
                f"- description: `{item['design_description']}`",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    for note in report.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _update_status(project_dir: Path, *, project_id: str, stamp: str) -> None:
    path = project_dir / "00_project_info" / "project_status.json"
    if path.is_file():
        status = json.loads(path.read_text(encoding="utf-8"))
    else:
        status = {"project_id": project_id, "history": []}
    if status.get("project_id") not in {None, project_id}:
        raise ValueError("project_status.json project_id mismatch")
    status["project_id"] = project_id
    status["status"] = "WAITING_APPROVAL"
    status["updated_at"] = stamp
    status["last_step"] = "three_proposals"
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "status": "SAMPLE_GENERATING",
            "at": stamp,
            "step": "three_proposals_start",
        }
    )
    history.append(
        {
            "status": "WAITING_APPROVAL",
            "at": stamp,
            "step": "three_proposals",
        }
    )
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "WAITING_APPROVAL"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_design(project_dir: Path) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    for key, relative in (
        ("design_tokens", "design_system/design_tokens.json"),
        ("color_palette", "color_palette.json"),
        ("typography", "typography.json"),
        ("layouts", "layouts.json"),
    ):
        payload = _load_json(project_dir / "04_design" / relative)
        if payload:
            merged[key] = payload
    return merged or None


def _require_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be an object: {path}")
    return data


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _style_run(
    paragraph: Any,
    *,
    font: str,
    size: float,
    color: str,
    bold: bool,
) -> None:
    from pptx.util import Pt

    if not paragraph.runs:
        return
    run = paragraph.runs[0]
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _set_slide_background(slide: Any, hex_color: str) -> None:
    from pptx.oxml.ns import qn
    from pptx.oxml import parse_xml

    value = hex_color.strip().lstrip("#").upper()
    if len(value) != 6:
        value = "FFFFFF"
    bg = slide._element.cSld.find(qn("p:bg"))
    if bg is not None:
        slide._element.cSld.remove(bg)
    fill_xml = (
        '<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f'<p:bgPr><a:solidFill><a:srgbClr val="{value}"/></a:solidFill>'
        "<a:effectLst/></p:bgPr></p:bg>"
    )
    slide._element.cSld.insert(0, parse_xml(fill_xml))


def _rgb(hex_color: str) -> Any:
    from pptx.dml.color import RGBColor

    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        value = "111111"
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return (17, 17, 17)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _looks_hex(value: Any) -> bool:
    return bool(re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(value).strip()))


if __name__ == "__main__":
    raise SystemExit(main())
