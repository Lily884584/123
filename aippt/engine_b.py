"""ENGINE B: smart fill of an authorized local PPTX template.

Copies the template (never overwrites ``01_input/``), maps outline pages onto
slides, fills editable text, and appends slides when the outline is longer.
Unauthorized commercial templates are rejected by the orchestrator before call.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

EMU_PER_INCH = 914400


def generate_engine_b(
    *,
    template_path: Path | str,
    outline: dict[str, Any],
    design: dict[str, Any] | None,
    output_path: Path | str,
    reference_images: list[Path] | None = None,
) -> dict[str, Any]:
    """Fill ``template_path`` with outline content and write ``output_path``."""

    from pptx import Presentation

    source = Path(template_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"template PPTX not found: {source}")
    pages = outline.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("outline must contain pages")

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out)

    presentation = Presentation(str(out))
    slides = list(presentation.slides)
    filled = 0
    appended = 0
    images_placed = 0
    image_as_full_background = False

    for index, page in enumerate(pages):
        if index < len(slides):
            slide = slides[index]
            _fill_slide_text(slide, page)
            filled += 1
        else:
            blank = presentation.slide_layouts[6]
            slide = presentation.slides.add_slide(blank)
            _add_fallback_text_boxes(slide, page, design, presentation)
            appended += 1
            filled += 1

        if reference_images and _page_wants_image(page):
            placed = _place_side_image(
                slide,
                reference_images[images_placed % len(reference_images)],
                presentation,
            )
            if placed:
                images_placed += 1

    unused = max(0, len(slides) - len(pages))
    if unused:
        _blank_trailing_slides(slides[len(pages) :])

    presentation.save(str(out))
    return {
        "engine": "B",
        "template_path": str(source),
        "output_path": str(out),
        "pages_filled": filled,
        "slides_appended": appended,
        "unused_template_slides_blanked": unused,
        "images_placed": images_placed,
        "image_as_full_background": image_as_full_background,
        "editable_elements_preserved": True,
    }


def _fill_slide_text(slide: Any, page: dict[str, Any]) -> None:
    text_shapes = [shape for shape in slide.shapes if shape.has_text_frame]
    text_shapes.sort(key=lambda shape: (int(shape.top), int(shape.left)))
    title = str(page.get("title") or "").strip()
    body_lines = _body_lines(page)

    if not text_shapes:
        return

    _set_text_frame(text_shapes[0].text_frame, title)
    if len(text_shapes) == 1:
        # Single box: title then body paragraphs.
        frame = text_shapes[0].text_frame
        if body_lines:
            _append_paragraphs(frame, body_lines)
        return

    _set_text_frame(text_shapes[1].text_frame, body_lines[0] if body_lines else "")
    if len(body_lines) > 1:
        _append_paragraphs(text_shapes[1].text_frame, body_lines[1:])

    for extra in text_shapes[2:]:
        # Keep shape editable but clear leftover template copy.
        _set_text_frame(extra.text_frame, "")


def _add_fallback_text_boxes(
    slide: Any,
    page: dict[str, Any],
    design: dict[str, Any] | None,
    presentation: Any,
) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    width_in = float(presentation.slide_width) / EMU_PER_INCH
    margin = 0.7
    typography = (design or {}).get("typography") or {}
    palette = (design or {}).get("color_palette") or {}
    title_font = ((typography.get("title") or {}).get("font")) or "Arial"
    title_size = float((typography.get("title") or {}).get("size_pt") or 28)
    body_font = ((typography.get("body") or {}).get("font")) or title_font
    body_size = float((typography.get("body") or {}).get("size_pt") or 16)
    text_hex = str(palette.get("text") or "#111111")

    title_box = slide.shapes.add_textbox(
        Inches(margin),
        Inches(0.6),
        Inches(max(width_in - 2 * margin, 4)),
        Inches(1.0),
    )
    title_frame = title_box.text_frame
    title_frame.text = str(page.get("title") or "")
    run = title_frame.paragraphs[0].runs[0]
    run.font.name = title_font
    run.font.size = Pt(title_size)
    run.font.bold = True
    run.font.color.rgb = _rgb(text_hex)

    body_box = slide.shapes.add_textbox(
        Inches(margin),
        Inches(1.9),
        Inches(max(width_in - 2 * margin, 4)),
        Inches(4.5),
    )
    body_frame = body_box.text_frame
    body_frame.clear()
    lines = _body_lines(page)
    if not lines:
        lines = ["待补"]
    for index, line in enumerate(lines):
        paragraph = body_frame.paragraphs[0] if index == 0 else body_frame.add_paragraph()
        paragraph.text = line
        paragraph.level = 0
        if paragraph.runs:
            run = paragraph.runs[0]
            run.font.name = body_font
            run.font.size = Pt(body_size)
            run.font.color.rgb = _rgb(text_hex)


def _place_side_image(slide: Any, image_path: Path, presentation: Any) -> bool:
    """Place a small side image; never as a full-bleed page background."""

    path = Path(image_path)
    if not path.is_file():
        return False
    width_in = float(presentation.slide_width) / EMU_PER_INCH
    height_in = float(presentation.slide_height) / EMU_PER_INCH
    from pptx.util import Inches

    # Cap at ~28% of slide width so it cannot act as a full-page background.
    img_width = min(width_in * 0.28, 3.2)
    img_height = min(height_in * 0.35, 2.4)
    left = width_in - img_width - 0.5
    top = height_in - img_height - 0.5
    slide.shapes.add_picture(
        str(path),
        Inches(left),
        Inches(top),
        width=Inches(img_width),
        height=Inches(img_height),
    )
    return True


def _blank_trailing_slides(slides: list[Any]) -> None:
    for slide in slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                _set_text_frame(shape.text_frame, "")


def _body_lines(page: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    core = str(page.get("core_point") or "").strip()
    if core:
        lines.append(core)
    for item in page.get("supporting_data") or []:
        text = str(item).strip()
        if text:
            lines.append(text)
    purpose = str(page.get("purpose") or "").strip()
    if purpose and purpose not in lines:
        lines.append(purpose)
    return lines[:8]


def _set_text_frame(frame: Any, text: str) -> None:
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.text = text


def _append_paragraphs(frame: Any, lines: list[str]) -> None:
    for line in lines:
        paragraph = frame.add_paragraph()
        paragraph.text = line
        paragraph.level = 0


def _page_wants_image(page: dict[str, Any]) -> bool:
    suggestion = str(page.get("image_suggestion") or "").strip().lower()
    if not suggestion or suggestion in {"无", "none", "n/a", "不需要", "无需"}:
        return False
    return True


def _rgb(hex_color: str) -> Any:
    from pptx.dml.color import RGBColor

    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        value = "111111"
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
