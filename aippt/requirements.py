"""Phase 3: customer requirement analysis for one project.

Reads the brief, project metadata, and Phase 2 extraction summaries.
Writes ``00_project_info/requirement_analysis.md`` (and JSON).
Does not search templates, call vision models, or generate PPT files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aippt.model import ModelClient, get_model_client
from aippt.paths import (
    append_project_log,
    load_project_id,
    manifest_path,
    project_info_path,
)

ANALYSIS_MD = "requirement_analysis.md"
ANALYSIS_JSON = "requirement_analysis.json"
STATUS_PATH = "00_project_info/project_status.json"
BRIEF_PATH = "00_project_info/customer_requirements.md"

# Keep model/user summaries small; never dump full extracted bodies into prompts.
MAX_SNIPPET_CHARS = 400
MAX_FILES_IN_SUMMARY = 20

_PAGE_COUNT = re.compile(
    r"(?i)(?:页数|页码|pages?|slides?)\s*[:：]?\s*(\d{1,3})"
)
_LANGUAGE = re.compile(
    r"(?i)(中文|英文|英语|汉语|chinese|english|한국어|韩语|日本語|日语)"
)
_AUDIENCE = re.compile(
    r"(?i)(?:受众|听众|audience|面向)\s*[:：]\s*([^\n。；;]+)"
)
_STYLE = re.compile(
    r"(?i)(?:风格|style)\s*[:：]\s*([^\n。；;]+)"
)
_SCENARIO = re.compile(
    r"(?i)(路演|答辩|汇报|产品介绍|竞聘|教学|比赛|发布会|pitch|demo|training)"
)


def analyze_requirements(
    project_dir: Path | str,
    *,
    model_client: ModelClient | None = None,
) -> dict[str, Any]:
    """Analyze one project's requirements and write analysis artifacts."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")

    project_id = load_project_id(root)
    info = json.loads(project_info_path(root).read_text(encoding="utf-8"))
    brief = _read_brief(root)
    file_summary = _build_file_summary(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    client = model_client if model_client is not None else get_model_client()
    if client is not None:
        analysis = _analyze_with_model(
            client=client,
            project_id=project_id,
            info=info,
            brief=brief,
            file_summary=file_summary,
            analyzed_at=stamp,
        )
        analysis["analyzer"] = "model"
    else:
        analysis = _analyze_locally(
            project_id=project_id,
            info=info,
            brief=brief,
            file_summary=file_summary,
            analyzed_at=stamp,
        )
        analysis["analyzer"] = "local"

    info_dir = root / "00_project_info"
    (info_dir / ANALYSIS_JSON).write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (info_dir / ANALYSIS_MD).write_text(
        _to_markdown(analysis),
        encoding="utf-8",
    )
    _update_status(root, project_id=project_id, stamp=stamp)
    append_project_log(
        root,
        f"{stamp} REQUIREMENTS_ANALYZED project_id={project_id} "
        f"analyzer={analysis['analyzer']} template={analysis['template_situation']}",
    )
    return analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze customer requirements for one AI PPT Studio project."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    args = parser.parse_args(argv)
    try:
        analysis = analyze_requirements(args.project)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    out = Path(args.project).resolve() / "00_project_info" / ANALYSIS_MD
    print(out)
    print(
        f"theme={analysis['theme']} template={analysis['template_situation']} "
        f"pages={analysis['page_count']} analyzer={analysis['analyzer']}"
    )
    return 0


def _read_brief(project_dir: Path) -> str:
    path = project_dir / BRIEF_PATH
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _build_file_summary(project_dir: Path) -> dict[str, Any]:
    man_path = manifest_path(project_dir)
    if not man_path.is_file():
        return {
            "manifest_present": False,
            "files": [],
            "counts_by_source": {},
            "counts_by_format": {},
            "has_reference_templates": False,
            "has_reference_images": False,
            "has_customer_pptx": False,
            "snippets": [],
        }

    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or []
    counts_by_source: dict[str, int] = {}
    counts_by_format: dict[str, int] = {}
    snippets: list[dict[str, str]] = []
    has_reference_templates = False
    has_reference_images = False
    has_customer_pptx = False

    for item in files:
        source = str(item.get("source") or "")
        fmt = str(item.get("format") or "unknown")
        counts_by_source[source] = counts_by_source.get(source, 0) + 1
        counts_by_format[fmt] = counts_by_format.get(fmt, 0) + 1
        if source == "reference_templates" and item.get("supported"):
            has_reference_templates = True
        if source == "reference_images" and item.get("supported"):
            has_reference_images = True
        if (
            source == "customer_files"
            and item.get("format") == "pptx"
            and item.get("supported")
        ):
            has_customer_pptx = True

        if (
            item.get("parse_status") == "parsed"
            and item.get("result_path")
            and len(snippets) < MAX_FILES_IN_SUMMARY
        ):
            snippet = _snippet_from_result(project_dir / item["result_path"])
            if snippet:
                snippets.append(
                    {
                        "original_filename": str(item.get("original_filename")),
                        "source": source,
                        "format": fmt,
                        "snippet": snippet,
                    }
                )

    return {
        "manifest_present": True,
        "file_count": len(files),
        "files": [
            {
                "original_filename": item.get("original_filename"),
                "source": item.get("source"),
                "format": item.get("format"),
                "parse_status": item.get("parse_status"),
            }
            for item in files[:MAX_FILES_IN_SUMMARY]
        ],
        "counts_by_source": counts_by_source,
        "counts_by_format": counts_by_format,
        "has_reference_templates": has_reference_templates,
        "has_reference_images": has_reference_images,
        "has_customer_pptx": has_customer_pptx,
        "snippets": snippets,
    }


def _snippet_from_result(result_dir: Path) -> str:
    content_path = result_dir / "content.json"
    if not content_path.is_file():
        return ""
    try:
        payload = json.loads(content_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""

    parts: list[str] = []
    if "slides" in payload:
        for slide in payload.get("slides") or []:
            texts = slide.get("texts") or []
            parts.extend(texts[:3])
            if sum(len(p) for p in parts) >= MAX_SNIPPET_CHARS:
                break
    elif "pages" in payload:
        for page in payload.get("pages") or []:
            text = (page.get("text") or "").strip()
            if text:
                parts.append(text[:200])
            if sum(len(p) for p in parts) >= MAX_SNIPPET_CHARS:
                break
    elif "paragraphs" in payload:
        parts.extend((payload.get("paragraphs") or [])[:8])
    elif "lines" in payload:
        parts.extend((payload.get("lines") or [])[:12])
    elif "sheets" in payload:
        for sheet in payload.get("sheets") or []:
            rows = sheet.get("rows") or []
            for row in rows[:5]:
                parts.append(" | ".join(str(cell) for cell in row))
    elif payload.get("format") == "images" or "width" in payload:
        parts.append(
            f"image {payload.get('width')}x{payload.get('height')} "
            f"{payload.get('image_format') or ''}".strip()
        )

    text = " / ".join(part.strip() for part in parts if str(part).strip())
    return text[:MAX_SNIPPET_CHARS]


def _analyze_locally(
    *,
    project_id: str,
    info: dict[str, Any],
    brief: str,
    file_summary: dict[str, Any],
    analyzed_at: str,
) -> dict[str, Any]:
    combined = "\n".join(
        part
        for part in (
            brief,
            str(info.get("special_requirements") or ""),
            str(info.get("topic") or ""),
            " ".join(s["snippet"] for s in file_summary.get("snippets") or []),
        )
        if part
    )

    defaults_used: list[str] = []
    open_questions: list[str] = []

    theme = str(info.get("topic") or "").strip() or _first_nonempty_line(brief)
    if not theme or theme.lower().startswith("# customer"):
        theme = "Untitled presentation"
        defaults_used.append("theme defaulted to Untitled presentation")
        open_questions.append("PPT 主题是什么？")

    scenario_match = _SCENARIO.search(combined)
    scenario = scenario_match.group(1) if scenario_match else "通用汇报"
    if scenario_match is None:
        defaults_used.append("scenario defaulted to 通用汇报")

    audience_match = _AUDIENCE.search(combined)
    if audience_match:
        audience = audience_match.group(1).strip()
    else:
        audience = "未指定受众"
        defaults_used.append("audience defaulted to 未指定受众")
        open_questions.append("目标受众是谁？")

    page_match = _PAGE_COUNT.search(combined)
    if page_match:
        page_count = int(page_match.group(1))
        page_count_source = "stated"
    else:
        page_count = 10
        page_count_source = "default"
        defaults_used.append("page_count defaulted to 10")

    language_match = _LANGUAGE.search(combined)
    if language_match:
        language = _normalize_language(language_match.group(1))
        language_source = "stated"
    else:
        language = "zh-CN"
        language_source = "default"
        defaults_used.append("language defaulted to zh-CN")

    style_match = _STYLE.search(combined)
    if style_match:
        design_style = style_match.group(1).strip()
        style_source = "stated"
    else:
        design_style = "简洁商务"
        style_source = "default"
        defaults_used.append("design_style defaulted to 简洁商务")

    content_depth = "standard"
    if re.search(r"(?i)深度|详细|详尽|in[- ]?depth", combined):
        content_depth = "deep"
    elif re.search(r"(?i)概览|摘要|brief|overview", combined):
        content_depth = "overview"

    image_needs = _infer_image_needs(combined, file_summary)
    chart_needs = bool(
        re.search(r"(?i)图表|chart|数据图|统计", combined)
        or (file_summary.get("counts_by_format") or {}).get("xlsx")
    )
    if re.search(r"(?i)(不(需要|要|用)?联网|无需(联网)?研究|no web research)", combined):
        needs_web_research = False
    else:
        needs_web_research = bool(
            re.search(r"(?i)联网|调研|web research|搜(索|资料)", combined)
        )
    template_situation, template_notes, template_questions = _template_situation(
        brief=brief,
        file_summary=file_summary,
    )
    open_questions.extend(template_questions)
    needs_specified_template = template_situation in {"B", "C"}

    return {
        "project_id": project_id,
        "analyzed_at": analyzed_at,
        "theme": theme,
        "scenario": scenario,
        "audience": audience,
        "page_count": page_count,
        "page_count_source": page_count_source,
        "language": language,
        "language_source": language_source,
        "design_style": design_style,
        "design_style_source": style_source,
        "content_depth": content_depth,
        "image_needs": image_needs,
        "chart_needs": chart_needs,
        "needs_web_research": needs_web_research,
        "needs_specified_template": needs_specified_template,
        "template_situation": template_situation,
        "template_notes": template_notes,
        "defaults_used": defaults_used,
        "open_questions": open_questions,
        "evidence": {
            "brief_present": bool(brief.strip()),
            "manifest_present": bool(file_summary.get("manifest_present")),
            "file_counts_by_source": file_summary.get("counts_by_source") or {},
            "file_counts_by_format": file_summary.get("counts_by_format") or {},
            "snippet_count": len(file_summary.get("snippets") or []),
        },
        "recommended_next_step": (
            "确认模板情况与开放问题后进入 Research（Phase 4）；"
            "若暂不联网，可直接进入设计/大纲阶段。"
        ),
    }


def _analyze_with_model(
    *,
    client: ModelClient,
    project_id: str,
    info: dict[str, Any],
    brief: str,
    file_summary: dict[str, Any],
    analyzed_at: str,
) -> dict[str, Any]:
    local = _analyze_locally(
        project_id=project_id,
        info=info,
        brief=brief,
        file_summary=file_summary,
        analyzed_at=analyzed_at,
    )
    system = (
        "You analyze PPT production requirements. "
        "Return JSON only with keys: theme, scenario, audience, page_count, "
        "language, design_style, content_depth, image_needs, chart_needs, "
        "needs_web_research, needs_specified_template, template_situation, "
        "template_notes, open_questions, defaults_used. "
        "template_situation must be A, B, C, or D. "
        "Do not invent customer facts, quotes, or metrics."
    )
    user = json.dumps(
        {
            "project_info": {
                "client": info.get("client"),
                "topic": info.get("topic"),
                "special_requirements": info.get("special_requirements"),
            },
            "brief": brief[:2000],
            "file_summary": {
                "counts_by_source": file_summary.get("counts_by_source"),
                "counts_by_format": file_summary.get("counts_by_format"),
                "has_reference_templates": file_summary.get("has_reference_templates"),
                "has_reference_images": file_summary.get("has_reference_images"),
                "has_customer_pptx": file_summary.get("has_customer_pptx"),
                "snippets": file_summary.get("snippets"),
            },
            "local_draft": local,
        },
        ensure_ascii=False,
    )
    raw = client.complete(system=system, user=user)
    parsed = _extract_json_object(raw)
    merged = dict(local)
    for key in (
        "theme",
        "scenario",
        "audience",
        "page_count",
        "language",
        "design_style",
        "content_depth",
        "image_needs",
        "chart_needs",
        "needs_web_research",
        "needs_specified_template",
        "template_situation",
        "template_notes",
        "open_questions",
        "defaults_used",
    ):
        if key in parsed:
            merged[key] = parsed[key]
    merged["project_id"] = project_id
    merged["analyzed_at"] = analyzed_at
    merged["model_raw_present"] = True
    return merged


def _template_situation(
    *,
    brief: str,
    file_summary: dict[str, Any],
) -> tuple[str, str, list[str]]:
    text = brief.lower()
    questions: list[str] = []

    if re.search(r"(填进模板|套这个|直接用这个模板|照着填)", brief):
        return "B", "Brief asks to fill a provided template without redesign.", []
    if re.search(r"(参考.*风格|做成这种感觉|类似这样|参考图)", brief):
        return "C", "Brief asks to follow a reference style, not fill a locked template.", []
    if re.search(r"(美化|改丑|重新设计.*原稿|optimize.*(ppt|deck))", text):
        return "D", "Brief asks to restyle an existing deck while keeping content.", []

    if file_summary.get("has_reference_templates"):
        questions.append(
            "参考模板是直接套用填内容（B），还是只参考风格重新设计（C）？"
        )
        return (
            "C",
            "Reference templates are present; defaulting to style reference (C) until confirmed.",
            questions,
        )
    if file_summary.get("has_customer_pptx") and not file_summary.get(
        "has_reference_templates"
    ):
        questions.append("客户 PPTX 是待美化的原稿（D），还是内容素材？")
        return (
            "D",
            "Customer PPTX present without reference templates; defaulting to restyle (D) until confirmed.",
            questions,
        )
    if file_summary.get("has_reference_images"):
        return (
            "C",
            "Reference images present without a locked template; treat as style reference (C).",
            [],
        )
    return "A", "No template or reference assets detected; design from scratch (A).", []


def _infer_image_needs(combined: str, file_summary: dict[str, Any]) -> dict[str, Any]:
    image_count = (file_summary.get("counts_by_format") or {}).get("images", 0)
    explicit = bool(re.search(r"(?i)图片|配图|截图|实拍|photo|image", combined))
    return {
        "requested": explicit or image_count > 0,
        "available_reference_images": image_count,
        "prefer_customer_photos": bool(re.search(r"(?i)实拍|客户照片|原图", combined)),
        "allow_ai_images": not bool(re.search(r"(?i)不能用AI|禁止AI图|no ai image", combined)),
    }


def _normalize_language(value: str) -> str:
    lowered = value.lower()
    if "英" in value or "english" in lowered:
        return "en"
    if "韩" in value or "한국" in value:
        return "ko"
    if "日" in value or "日本" in value:
        return "ja"
    return "zh-CN"


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "customer requirements":
            return stripped
    return ""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("model did not return a JSON object")


def _to_markdown(analysis: dict[str, Any]) -> str:
    image_needs = analysis.get("image_needs") or {}
    defaults = analysis.get("defaults_used") or []
    questions = analysis.get("open_questions") or []
    evidence = analysis.get("evidence") or {}

    lines = [
        "# Requirement analysis",
        "",
        f"- project_id: `{analysis['project_id']}`",
        f"- analyzed_at: `{analysis['analyzed_at']}`",
        f"- analyzer: `{analysis.get('analyzer')}`",
        f"- template_situation: **{analysis['template_situation']}**",
        "",
        "## Extracted fields",
        "",
        f"1. PPT theme: {analysis['theme']}",
        f"2. Scenario: {analysis['scenario']}",
        f"3. Audience: {analysis['audience']}",
        f"4. Page count: {analysis['page_count']} ({analysis.get('page_count_source')})",
        f"5. Language: {analysis['language']} ({analysis.get('language_source')})",
        f"6. Design style: {analysis['design_style']} ({analysis.get('design_style_source')})",
        f"7. Content depth: {analysis['content_depth']}",
        (
            "8. Image needs: "
            f"requested={image_needs.get('requested')}, "
            f"available_reference_images={image_needs.get('available_reference_images')}, "
            f"prefer_customer_photos={image_needs.get('prefer_customer_photos')}, "
            f"allow_ai_images={image_needs.get('allow_ai_images')}"
        ),
        f"9. Chart needs: {analysis['chart_needs']}",
        f"10. Needs web research: {analysis['needs_web_research']}",
        f"11. Needs specified template: {analysis['needs_specified_template']}",
        "",
        "## Template notes",
        "",
        str(analysis.get("template_notes") or ""),
        "",
        "## Defaults used",
        "",
    ]
    if defaults:
        lines.extend(f"- {item}" for item in defaults)
    else:
        lines.append("- none")

    lines.extend(["", "## Open questions", ""])
    if questions:
        lines.extend(f"- {item}" for item in questions)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- brief_present: {evidence.get('brief_present')}",
            f"- manifest_present: {evidence.get('manifest_present')}",
            f"- file_counts_by_source: `{json.dumps(evidence.get('file_counts_by_source') or {}, ensure_ascii=False)}`",
            f"- file_counts_by_format: `{json.dumps(evidence.get('file_counts_by_format') or {}, ensure_ascii=False)}`",
            f"- snippet_count: {evidence.get('snippet_count')}",
            "",
            "## Recommended next step",
            "",
            str(analysis.get("recommended_next_step") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def _update_status(project_dir: Path, *, project_id: str, stamp: str) -> None:
    path = project_dir / STATUS_PATH
    if path.is_file():
        status = json.loads(path.read_text(encoding="utf-8"))
    else:
        status = {"project_id": project_id, "history": []}
    if status.get("project_id") not in {None, project_id}:
        raise ValueError("project_status.json project_id mismatch")
    status["project_id"] = project_id
    status["status"] = "ANALYZING"
    status["updated_at"] = stamp
    status["last_step"] = "requirements_analysis"
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "status": "ANALYZING",
            "at": stamp,
            "step": "requirements_analysis",
        }
    )
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "ANALYZING"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
