"""Phase 5: PPTX template parse and design-system extraction.

Writes a unified Design System under ``04_design/``.
Does not generate PPT files, search the network, or rewrite customer originals.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aippt.paths import append_project_log, load_project_id, project_info_path

EMU_PER_INCH = 914400


def analyze_design(
    project_dir: Path | str,
    *,
    max_templates: int = 5,
) -> dict[str, Any]:
    """Analyze local PPTX templates and write ``04_design`` artifacts."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")
    if max_templates < 1:
        raise ValueError("max_templates must be >= 1")

    project_id = load_project_id(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources = _discover_templates(root)[:max_templates]
    if not sources:
        raise FileNotFoundError(
            "no local PPTX templates found under 01_input/reference_templates "
            "or 01_input/customer_files"
        )

    analyses = []
    for source in sources:
        analyses.append(_analyze_pptx(source, project_id=project_id))

    design = _unify_design_system(
        project_id=project_id,
        analyzed_at=stamp,
        analyses=analyses,
    )
    _write_design_system(root, design)
    _update_status(root, project_id=project_id, stamp=stamp)
    append_project_log(
        root,
        f"{stamp} DESIGNED project_id={project_id} templates={len(analyses)} "
        f"primary={design['color_palette']['primary']} "
        f"ratio={design['design_tokens']['page']['aspect_ratio']}",
    )
    return design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze PPTX templates and write a unified design system."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    parser.add_argument(
        "--max-templates",
        type=int,
        default=5,
        help="Maximum local PPTX templates to analyze.",
    )
    args = parser.parse_args(argv)
    try:
        design = analyze_design(args.project, max_templates=args.max_templates)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    out = Path(args.project).resolve() / "04_design" / "design_system" / "template_rules.md"
    print(out)
    palette = design["color_palette"]
    page = design["design_tokens"]["page"]
    print(
        f"templates={len(design['sources'])} "
        f"ratio={page['aspect_ratio']} "
        f"primary={palette['primary']}"
    )
    return 0


def _discover_templates(project_dir: Path) -> list[dict[str, str]]:
    roots = [
        ("reference_templates", project_dir / "01_input" / "reference_templates"),
        ("customer_files", project_dir / "01_input" / "customer_files"),
    ]
    found: list[dict[str, str]] = []
    for source, folder in roots:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.pptx")):
            if path.name.startswith("~"):
                continue
            found.append(
                {
                    "source": source,
                    "path": str(path),
                    "relative_path": path.relative_to(project_dir / "01_input").as_posix(),
                    "original_filename": path.name,
                }
            )
    return found


def _analyze_pptx(source: dict[str, str], *, project_id: str) -> dict[str, Any]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.util import Emu

    path = Path(source["path"])
    presentation = Presentation(str(path))
    width = int(presentation.slide_width)
    height = int(presentation.slide_height)
    aspect = round(width / height, 4) if height else None

    fonts: Counter[str] = Counter()
    title_sizes: list[float] = []
    body_sizes: list[float] = []
    colors: Counter[str] = Counter()
    background_colors: Counter[str] = Counter()
    image_frames = 0
    chart_frames = 0
    decorative = 0
    margins = []
    page_structures = []

    for index, slide in enumerate(presentation.slides, start=1):
        bg = _slide_background_color(slide)
        if bg:
            background_colors[bg] += 1
            colors[bg] += 1

        texts = []
        shape_boxes = []
        for shape in slide.shapes:
            shape_boxes.append(
                {
                    "left": int(shape.left),
                    "top": int(shape.top),
                    "width": int(shape.width),
                    "height": int(shape.height),
                }
            )
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                image_frames += 1
            if getattr(shape, "has_chart", False):
                chart_frames += 1
            if shape.shape_type in {
                MSO_SHAPE_TYPE.AUTO_SHAPE,
                MSO_SHAPE_TYPE.FREEFORM,
                MSO_SHAPE_TYPE.LINE,
            }:
                decorative += 1

            fill_color = _shape_fill_color(shape)
            if fill_color:
                colors[fill_color] += 1

            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                runs_text = "".join(run.text for run in paragraph.runs).strip()
                if runs_text:
                    texts.append(runs_text)
                for run in paragraph.runs:
                    font_name = run.font.name
                    if font_name:
                        fonts[font_name] += 1
                    size = run.font.size
                    if size is not None:
                        pt = float(Emu(size).pt)
                        # Heuristic: larger text near the top counts as title-like.
                        if shape.top < height * 0.28 or pt >= 24:
                            title_sizes.append(pt)
                        else:
                            body_sizes.append(pt)
                    color = _font_color(run)
                    if color:
                        colors[color] += 1

        if shape_boxes:
            left = min(box["left"] for box in shape_boxes)
            top = min(box["top"] for box in shape_boxes)
            right = max(box["left"] + box["width"] for box in shape_boxes)
            bottom = max(box["top"] + box["height"] for box in shape_boxes)
            margins.append(
                {
                    "left_in": round(left / EMU_PER_INCH, 3),
                    "top_in": round(top / EMU_PER_INCH, 3),
                    "right_in": round((width - right) / EMU_PER_INCH, 3),
                    "bottom_in": round((height - bottom) / EMU_PER_INCH, 3),
                }
            )

        page_structures.append(
            {
                "page": index,
                "shape_count": len(shape_boxes),
                "text_blocks": len(texts),
                "has_image": any(
                    True
                    for shape in slide.shapes
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
                ),
                "has_chart": any(
                    getattr(shape, "has_chart", False) for shape in slide.shapes
                ),
            }
        )

    return {
        "project_id": project_id,
        "original_filename": source["original_filename"],
        "source": source["source"],
        "relative_path": source["relative_path"],
        "page": {
            "width_emu": width,
            "height_emu": height,
            "width_in": round(width / EMU_PER_INCH, 3),
            "height_in": round(height / EMU_PER_INCH, 3),
            "aspect_ratio": aspect,
        },
        "background_colors": background_colors.most_common(),
        "colors": colors.most_common(),
        "fonts": fonts.most_common(),
        "title_font_sizes_pt": sorted(title_sizes, reverse=True)[:12],
        "body_font_sizes_pt": sorted(body_sizes, reverse=True)[:12],
        "image_frame_count": image_frames,
        "chart_frame_count": chart_frames,
        "decorative_shape_count": decorative,
        "margins": margins,
        "page_structures": page_structures,
    }


def _unify_design_system(
    *,
    project_id: str,
    analyzed_at: str,
    analyses: list[dict[str, Any]],
) -> dict[str, Any]:
    # Prefer the first reference template as the style anchor, then merge signals.
    anchor = analyses[0]
    page = dict(anchor["page"])

    color_counter: Counter[str] = Counter()
    bg_counter: Counter[str] = Counter()
    font_counter: Counter[str] = Counter()
    title_sizes: list[float] = []
    body_sizes: list[float] = []
    margin_left = []
    margin_top = []
    margin_right = []
    margin_bottom = []
    layouts = []

    for analysis in analyses:
        color_counter.update(dict(analysis["colors"]))
        bg_counter.update(dict(analysis["background_colors"]))
        font_counter.update(dict(analysis["fonts"]))
        title_sizes.extend(analysis["title_font_sizes_pt"])
        body_sizes.extend(analysis["body_font_sizes_pt"])
        for margin in analysis["margins"]:
            margin_left.append(margin["left_in"])
            margin_top.append(margin["top_in"])
            margin_right.append(margin["right_in"])
            margin_bottom.append(margin["bottom_in"])
        for structure in analysis["page_structures"]:
            layouts.append(
                {
                    "from_template": analysis["original_filename"],
                    "page": structure["page"],
                    "shape_count": structure["shape_count"],
                    "text_blocks": structure["text_blocks"],
                    "has_image": structure["has_image"],
                    "has_chart": structure["has_chart"],
                }
            )

    background = bg_counter.most_common(1)[0][0] if bg_counter else "#FFFFFF"
    ranked_colors = [color for color, _ in color_counter.most_common() if color != background]
    primary = ranked_colors[0] if ranked_colors else "#111111"
    secondary = ranked_colors[1] if len(ranked_colors) > 1 else _derive_secondary(primary)
    accent = ranked_colors[2] if len(ranked_colors) > 2 else _derive_accent(primary)
    neutrals = _neutrals_from(background)

    title_font = font_counter.most_common(1)[0][0] if font_counter else "Arial"
    body_font = (
        font_counter.most_common(2)[1][0]
        if len(font_counter.most_common()) > 1
        else title_font
    )
    title_size = _median(title_sizes) or 32.0
    body_size = _median(body_sizes) or 16.0

    spacing = {
        "margin_left_in": round(_median(margin_left) or 0.5, 3),
        "margin_top_in": round(_median(margin_top) or 0.5, 3),
        "margin_right_in": round(_median(margin_right) or 0.5, 3),
        "margin_bottom_in": round(_median(margin_bottom) or 0.5, 3),
    }

    design_tokens = {
        "project_id": project_id,
        "analyzed_at": analyzed_at,
        "page": page,
        "colors": {
            "background": background,
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "text": neutrals["text"],
            "muted_text": neutrals["muted_text"],
        },
        "typography": {
            "title_font": title_font,
            "body_font": body_font,
            "title_size_pt": title_size,
            "body_size_pt": body_size,
        },
        "spacing": spacing,
        "motifs": {
            "image_frames": sum(item["image_frame_count"] for item in analyses),
            "chart_frames": sum(item["chart_frame_count"] for item in analyses),
            "decorative_shapes": sum(
                item["decorative_shape_count"] for item in analyses
            ),
        },
    }

    color_palette = {
        "project_id": project_id,
        "background": background,
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "text": neutrals["text"],
        "muted_text": neutrals["muted_text"],
        "candidates": [
            {"hex": color, "count": count}
            for color, count in color_counter.most_common(12)
        ],
    }
    typography = {
        "project_id": project_id,
        "title": {
            "font": title_font,
            "size_pt": title_size,
            "weight": "bold",
        },
        "body": {
            "font": body_font,
            "size_pt": body_size,
            "weight": "regular",
        },
        "fonts_seen": [
            {"font": font, "count": count}
            for font, count in font_counter.most_common(12)
        ],
    }
    layouts_doc = {
        "project_id": project_id,
        "page_aspect_ratio": page.get("aspect_ratio"),
        "spacing": spacing,
        "image_layout": {
            "observed_image_frames": sum(item["image_frame_count"] for item in analyses),
            "guidance": "Keep large imagery edge-aware; avoid card grids unless the template uses them.",
        },
        "chart_layout": {
            "observed_chart_frames": sum(item["chart_frame_count"] for item in analyses),
            "guidance": "Place charts with clear margins and one emphasis series color from the palette.",
        },
        "pages": layouts[:50],
    }

    rules = _template_rules_markdown(
        project_id=project_id,
        analyzed_at=analyzed_at,
        sources=analyses,
        design_tokens=design_tokens,
        color_palette=color_palette,
        typography=typography,
        layouts=layouts_doc,
    )

    return {
        "project_id": project_id,
        "analyzed_at": analyzed_at,
        "sources": [
            {
                "original_filename": item["original_filename"],
                "source": item["source"],
                "relative_path": item["relative_path"],
            }
            for item in analyses
        ],
        "design_tokens": design_tokens,
        "color_palette": color_palette,
        "typography": typography,
        "layouts": layouts_doc,
        "template_rules_md": rules,
        "style_unification": {
            "anchor_template": analyses[0]["original_filename"],
            "note": (
                "Multiple templates may inform tokens, but the final deck should "
                "follow this unified palette, typography, and spacing."
            ),
        },
    }


def _write_design_system(project_dir: Path, design: dict[str, Any]) -> None:
    design_root = project_dir / "04_design"
    system_dir = design_root / "design_system"
    system_dir.mkdir(parents=True, exist_ok=True)

    _write_json(system_dir / "design_tokens.json", design["design_tokens"])
    _write_json(design_root / "color_palette.json", design["color_palette"])
    _write_json(design_root / "typography.json", design["typography"])
    _write_json(design_root / "layouts.json", design["layouts"])
    (system_dir / "template_rules.md").write_text(
        design["template_rules_md"], encoding="utf-8"
    )
    summary = {
        "project_id": design["project_id"],
        "analyzed_at": design["analyzed_at"],
        "sources": design["sources"],
        "style_unification": design["style_unification"],
        "artifacts": [
            "04_design/design_system/design_tokens.json",
            "04_design/color_palette.json",
            "04_design/typography.json",
            "04_design/layouts.json",
            "04_design/design_system/template_rules.md",
        ],
    }
    _write_json(design_root / "design_analysis.json", summary)


def _template_rules_markdown(
    *,
    project_id: str,
    analyzed_at: str,
    sources: list[dict[str, Any]],
    design_tokens: dict[str, Any],
    color_palette: dict[str, Any],
    typography: dict[str, Any],
    layouts: dict[str, Any],
) -> str:
    lines = [
        "# Template rules",
        "",
        f"- project_id: `{project_id}`",
        f"- analyzed_at: `{analyzed_at}`",
        f"- anchor_template: `{sources[0]['original_filename']}`",
        "",
        "## Page",
        "",
        f"- aspect_ratio: {design_tokens['page'].get('aspect_ratio')}",
        f"- size_in: {design_tokens['page'].get('width_in')} x {design_tokens['page'].get('height_in')}",
        "",
        "## Color",
        "",
        f"- background: `{color_palette['background']}`",
        f"- primary: `{color_palette['primary']}`",
        f"- secondary: `{color_palette['secondary']}`",
        f"- accent: `{color_palette['accent']}`",
        f"- text: `{color_palette['text']}`",
        "",
        "## Typography",
        "",
        f"- title: {typography['title']['font']} / {typography['title']['size_pt']} pt",
        f"- body: {typography['body']['font']} / {typography['body']['size_pt']} pt",
        "",
        "## Spacing and whitespace",
        "",
        f"- margins_in: L{layouts['spacing']['margin_left_in']} "
        f"T{layouts['spacing']['margin_top_in']} "
        f"R{layouts['spacing']['margin_right_in']} "
        f"B{layouts['spacing']['margin_bottom_in']}",
        "",
        "## Layout guidance",
        "",
        f"- images: {layouts['image_layout']['guidance']}",
        f"- charts: {layouts['chart_layout']['guidance']}",
        "- Keep one visual hierarchy across all pages even if multiple templates were referenced.",
        "",
        "## Source templates",
        "",
    ]
    for item in sources:
        lines.append(
            f"- `{item['original_filename']}` ({item['source']}: `{item['relative_path']}`)"
        )
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
    status["status"] = "DESIGNING"
    status["updated_at"] = stamp
    status["last_step"] = "template_design_analysis"
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {"status": "DESIGNING", "at": stamp, "step": "template_design_analysis"}
    )
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "DESIGNING"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _slide_background_color(slide: Any) -> str | None:
    fill = slide.background.fill
    return _fill_to_hex(fill)


def _shape_fill_color(shape: Any) -> str | None:
    try:
        fill = shape.fill
    except Exception:  # noqa: BLE001
        return None
    return _fill_to_hex(fill)


def _fill_to_hex(fill: Any) -> str | None:
    try:
        from pptx.enum.dml import MSO_FILL

        if fill.type != MSO_FILL.SOLID:
            return None
        color = fill.fore_color
        rgb = color.rgb
        return _rgb_to_hex(rgb)
    except Exception:  # noqa: BLE001
        return None


def _font_color(run: Any) -> str | None:
    try:
        color = run.font.color
        rgb = color.rgb
        return _rgb_to_hex(rgb)
    except Exception:  # noqa: BLE001
        return None


def _rgb_to_hex(rgb: Any) -> str | None:
    if rgb is None:
        return None
    text = str(rgb)
    if re.fullmatch(r"[0-9A-Fa-f]{6}", text):
        return f"#{text.upper()}"
    return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(float(ordered[mid]), 2)
    return round((float(ordered[mid - 1]) + float(ordered[mid])) / 2.0, 2)


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    text = value.lstrip("#")
    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
    )


def _rgb_tuple_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(round(rgb[0] * 255)))),
        max(0, min(255, int(round(rgb[1] * 255)))),
        max(0, min(255, int(round(rgb[2] * 255)))),
    )


def _derive_secondary(primary: str) -> str:
    r, g, b = _hex_to_rgb(primary)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return _rgb_tuple_to_hex(colorsys.hsv_to_rgb((h + 0.08) % 1.0, min(1.0, s * 0.7), min(1.0, v * 0.9)))


def _derive_accent(primary: str) -> str:
    r, g, b = _hex_to_rgb(primary)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return _rgb_tuple_to_hex(colorsys.hsv_to_rgb((h + 0.5) % 1.0, min(1.0, max(s, 0.4)), min(1.0, max(v, 0.6))))


def _neutrals_from(background: str) -> dict[str, str]:
    r, g, b = _hex_to_rgb(background)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if luminance > 0.6:
        return {"text": "#111111", "muted_text": "#4A4A4A"}
    return {"text": "#F5F5F5", "muted_text": "#C8C8C8"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
