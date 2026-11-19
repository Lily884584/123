"""ENGINE C: redesign slides from the Design System.

Builds a new editable PPTX from outline pages using design tokens.
Does not paste reference images as full-page backgrounds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

EMU_PER_INCH = 914400


def generate_engine_c(
    *,
    outline: dict[str, Any],
    design: dict[str, Any],
    output_path: Path | str,
    reference_images: list[Path] | None = None,
) -> dict[str, Any]:
    """Create a redesigned deck from design tokens + outline content."""

    from pptx import Presentation
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    pages = outline.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("outline must contain pages")

    tokens = design.get("design_tokens") or {}
    page_token = tokens.get("page") or {}
    palette = design.get("color_palette") or {}
    typography = design.get("typography") or {}
    layouts = design.get("layouts") or {}
    spacing = layouts.get("spacing") or {}

    width_in = float(page_token.get("width_in") or 13.333)
    height_in = float(page_token.get("height_in") or 7.5)
    margin_l = float(spacing.get("margin_left_in") or 0.7)
    margin_t = float(spacing.get("margin_top_in") or 0.55)
    margin_r = float(spacing.get("margin_right_in") or 0.7)

    background = str(palette.get("background") or "#FFFFFF")
    primary = str(palette.get("primary") or "#111111")
    accent = str(palette.get("accent") or primary)
    text_color = str(palette.get("text") or "#111111")
    muted = str(palette.get("secondary") or "#4A4A4A")

    title_font = str((typography.get("title") or {}).get("font") or "Arial")
    title_size = float((typography.get("title") or {}).get("size_pt") or 32)
    body_font = str((typography.get("body") or {}).get("font") or title_font)
    body_size = float((typography.get("body") or {}).get("size_pt") or 16)

    presentation = Presentation()
    presentation.slide_width = Inches(width_in)
    presentation.slide_height = Inches(height_in)
    blank = presentation.slide_layouts[6]

    images_placed = 0
    charts_sketched = 0
    image_as_full_background = False
    content_width = max(width_in - margin_l - margin_r, 4.0)

    for page in pages:
        slide = presentation.slides.add_slide(blank)
        _set_slide_background(slide, background)

        # Accent bar — design language cue, not a photo background.
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0),
            Inches(0),
            Inches(0.18),
            Inches(height_in),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = _rgb(accent)
        bar.line.fill.background()

        role = str(page.get("role") or "content")
        layout_name = str(page.get("recommended_layout") or role)

        title_box = slide.shapes.add_textbox(
            Inches(margin_l),
            Inches(margin_t),
            Inches(content_width),
            Inches(1.1),
        )
        title_frame = title_box.text_frame
        title_frame.word_wrap = True
        title_frame.text = str(page.get("title") or "")
        title_run = title_frame.paragraphs[0].runs[0]
        title_run.font.name = title_font
        title_run.font.size = Pt(title_size if role != "cover" else title_size + 6)
        title_run.font.bold = True
        title_run.font.color.rgb = _rgb(text_color)
        if role == "cover":
            title_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

        body_top = margin_t + 1.25
        body_height = max(height_in - body_top - 0.6, 2.0)
        use_split = layout_name in {
            "two_column",
            "image_right",
            "chart_focus",
            "data",
        } or role in {"data", "agenda"}

        body_width = content_width * (0.58 if use_split else 1.0)
        body_box = slide.shapes.add_textbox(
            Inches(margin_l),
            Inches(body_top),
            Inches(body_width),
            Inches(body_height),
        )
        body_frame = body_box.text_frame
        body_frame.word_wrap = True
        body_frame.clear()
        lines = _body_lines(page)
        for index, line in enumerate(lines):
            paragraph = (
                body_frame.paragraphs[0] if index == 0 else body_frame.add_paragraph()
            )
            paragraph.text = line
            paragraph.level = 0 if index == 0 else 1
            if paragraph.runs:
                run = paragraph.runs[0]
                run.font.name = body_font
                run.font.size = Pt(body_size if index == 0 else max(body_size - 2, 12))
                run.font.color.rgb = _rgb(text_color if index == 0 else muted)

        if use_split:
            panel_left = margin_l + body_width + 0.35
            panel_width = max(width_in - panel_left - margin_r, 2.0)
            panel = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(panel_left),
                Inches(body_top),
                Inches(panel_width),
                Inches(min(body_height, 4.2)),
            )
            panel.fill.solid()
            panel.fill.fore_color.rgb = _rgb(_lighten(primary, 0.88))
            panel.line.fill.background()

            chart_hint = str(page.get("chart_suggestion") or "").strip()
            if chart_hint and chart_hint.lower() not in {"无", "none", "n/a"}:
                _sketch_chart_placeholder(
                    slide,
                    left=panel_left + 0.25,
                    top=body_top + 0.35,
                    width=panel_width - 0.5,
                    height=2.2,
                    accent=accent,
                    label=chart_hint[:80],
                    font=body_font,
                    color=text_color,
                )
                charts_sketched += 1
            elif reference_images and _page_wants_image(page):
                placed = _place_panel_image(
                    slide,
                    reference_images[images_placed % len(reference_images)],
                    left=panel_left + 0.25,
                    top=body_top + 0.35,
                    width=panel_width - 0.5,
                    height=min(body_height - 0.7, 3.0),
                )
                if placed:
                    images_placed += 1
            else:
                note = slide.shapes.add_textbox(
                    Inches(panel_left + 0.25),
                    Inches(body_top + 0.4),
                    Inches(panel_width - 0.5),
                    Inches(1.5),
                )
                note.text_frame.text = str(page.get("image_suggestion") or "视觉区")
                if note.text_frame.paragraphs[0].runs:
                    run = note.text_frame.paragraphs[0].runs[0]
                    run.font.name = body_font
                    run.font.size = Pt(12)
                    run.font.color.rgb = _rgb(muted)
        elif reference_images and _page_wants_image(page):
            placed = _place_corner_image(
                slide,
                reference_images[images_placed % len(reference_images)],
                slide_width=width_in,
                slide_height=height_in,
            )
            if placed:
                images_placed += 1

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(out))
    return {
        "engine": "C",
        "output_path": str(out),
        "pages_built": len(pages),
        "images_placed": images_placed,
        "charts_sketched": charts_sketched,
        "image_as_full_background": image_as_full_background,
        "editable_elements_preserved": True,
        "design_primary": primary,
        "page_aspect_ratio": page_token.get("aspect_ratio"),
    }


def _body_lines(page: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    core = str(page.get("core_point") or "").strip()
    if core:
        lines.append(core)
    for item in page.get("supporting_data") or []:
        text = str(item).strip()
        if text and text not in lines:
            lines.append(text)
    purpose = str(page.get("purpose") or "").strip()
    if purpose and purpose not in lines:
        lines.append(purpose)
    return lines[:8] or ["待补"]


def _page_wants_image(page: dict[str, Any]) -> bool:
    suggestion = str(page.get("image_suggestion") or "").strip().lower()
    if not suggestion or suggestion in {"无", "none", "n/a", "不需要", "无需"}:
        return False
    return True


def _set_slide_background(slide: Any, hex_color: str) -> None:
    from pptx.oxml.ns import qn
    from pptx.oxml import parse_xml

    # Solid color fill only — never a full-page photograph.
    value = hex_color.strip().lstrip("#").upper()
    if len(value) != 6:
        value = "FFFFFF"
    bg = slide._element.cSld.find(qn("p:bg"))
    if bg is not None:
        slide._element.cSld.remove(bg)
    fill_xml = (
        '<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f"<p:bgPr><a:solidFill><a:srgbClr val=\"{value}\"/></a:solidFill>"
        "<a:effectLst/></p:bgPr></p:bg>"
    )
    slide._element.cSld.insert(0, parse_xml(fill_xml))


def _sketch_chart_placeholder(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    accent: str,
    label: str,
    font: str,
    color: str,
) -> None:
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.util import Inches, Pt

    bars = 4
    gap = 0.12
    bar_width = (width - gap * (bars - 1)) / bars
    heights = [0.45, 0.7, 0.55, 0.85]
    for index, ratio in enumerate(heights):
        bar_h = height * 0.55 * ratio
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(left + index * (bar_width + gap)),
            Inches(top + height * 0.55 - bar_h),
            Inches(bar_width),
            Inches(bar_h),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = _rgb(accent)
        bar.line.fill.background()
    caption = slide.shapes.add_textbox(
        Inches(left),
        Inches(top + height * 0.65),
        Inches(width),
        Inches(0.6),
    )
    caption.text_frame.text = label
    if caption.text_frame.paragraphs[0].runs:
        run = caption.text_frame.paragraphs[0].runs[0]
        run.font.name = font
        run.font.size = Pt(11)
        run.font.color.rgb = _rgb(color)


def _place_panel_image(
    slide: Any,
    image_path: Path,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> bool:
    path = Path(image_path)
    if not path.is_file():
        return False
    from pptx.util import Inches

    # Panel image only — intentionally smaller than the slide.
    slide.shapes.add_picture(
        str(path),
        Inches(left),
        Inches(top),
        width=Inches(width),
        height=Inches(min(height, 3.2)),
    )
    return True


def _place_corner_image(
    slide: Any,
    image_path: Path,
    *,
    slide_width: float,
    slide_height: float,
) -> bool:
    path = Path(image_path)
    if not path.is_file():
        return False
    from pptx.util import Inches

    img_w = min(slide_width * 0.26, 3.0)
    img_h = min(slide_height * 0.32, 2.2)
    slide.shapes.add_picture(
        str(path),
        Inches(slide_width - img_w - 0.55),
        Inches(slide_height - img_h - 0.45),
        width=Inches(img_w),
        height=Inches(img_h),
    )
    return True


def _rgb(hex_color: str) -> Any:
    from pptx.dml.color import RGBColor

    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        value = "111111"
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _lighten(hex_color: str, amount: float) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return "F5F5F5"
    rgb = [int(value[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [int(channel + (255 - channel) * amount) for channel in rgb]
    return "#{:02X}{:02X}{:02X}".format(*mixed)
