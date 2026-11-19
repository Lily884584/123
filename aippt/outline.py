"""Phase 6: PPT outline and per-slide content planning.

Writes ``05_content/ppt_outline.md`` and ``05_content/slide_content/``.
Does not generate PPTX, invent facts, or call template engines.
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

MAX_SNIPPETS = 12
MAX_SNIPPET_CHARS = 240


def build_outline(
    project_dir: Path | str,
    *,
    model_client: ModelClient | None = None,
) -> dict[str, Any]:
    """Build a storyline outline for one project."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")

    project_id = load_project_id(root)
    info = json.loads(project_info_path(root).read_text(encoding="utf-8"))
    analysis = _load_json(root / "00_project_info" / "requirement_analysis.json")
    research = _load_json(root / "03_research" / "template_search.json")
    design = _load_json(root / "04_design" / "design_analysis.json")
    brief = _read_text(root / "00_project_info" / "customer_requirements.md")
    snippets = _load_snippets(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    client = model_client if model_client is not None else get_model_client()
    if client is not None:
        outline = _outline_with_model(
            client=client,
            project_id=project_id,
            info=info,
            analysis=analysis,
            research=research,
            design=design,
            brief=brief,
            snippets=snippets,
            created_at=stamp,
        )
        outline["planner"] = "model"
    else:
        outline = _outline_locally(
            project_id=project_id,
            info=info,
            analysis=analysis,
            research=research,
            design=design,
            brief=brief,
            snippets=snippets,
            created_at=stamp,
        )
        outline["planner"] = "local"

    _validate_outline(outline)
    _write_outline(root, outline)
    _update_status(root, project_id=project_id, stamp=stamp)
    append_project_log(
        root,
        f"{stamp} OUTLINED project_id={project_id} pages={len(outline['pages'])} "
        f"planner={outline['planner']}",
    )
    return outline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a PPT outline and slide content plan for one project."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    args = parser.parse_args(argv)
    try:
        outline = build_outline(args.project)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    out = Path(args.project).resolve() / "05_content" / "ppt_outline.md"
    print(out)
    print(f"pages={len(outline['pages'])} planner={outline['planner']}")
    return 0


def _outline_locally(
    *,
    project_id: str,
    info: dict[str, Any],
    analysis: dict[str, Any],
    research: dict[str, Any],
    design: dict[str, Any],
    brief: str,
    snippets: list[dict[str, str]],
    created_at: str,
) -> dict[str, Any]:
    theme = str(analysis.get("theme") or info.get("topic") or "Untitled").strip()
    scenario = str(analysis.get("scenario") or "通用汇报").strip()
    audience = str(analysis.get("audience") or "未指定受众").strip()
    language = str(analysis.get("language") or "zh-CN").strip()
    style = str(analysis.get("design_style") or "简洁商务").strip()
    requested_pages = int(analysis.get("page_count") or 10)
    chart_needs = bool(analysis.get("chart_needs"))
    image_needs = analysis.get("image_needs") or {}
    template_situation = str(analysis.get("template_situation") or "A")

    # Meaningful skeleton only — never pad with empty filler pages.
    skeleton = _skeleton_roles(
        requested_pages=requested_pages,
        chart_needs=chart_needs,
        image_needs=bool(image_needs.get("requested")),
        snippet_count=len(snippets),
    )
    content_points = _content_points(brief=brief, snippets=snippets, theme=theme)
    pages: list[dict[str, Any]] = []
    content_index = 0

    for page_number, role in enumerate(skeleton, start=1):
        if role == "cover":
            pages.append(
                _page(
                    page_number,
                    title=theme,
                    purpose="开场定调，让听众立刻知道主题与场景。",
                    core_point=f"{theme} · {scenario}",
                    supporting_data=_supporting_from_brief(brief) or ["待补：一句客户原话或目标"],
                    image_suggestion="品牌/产品主视觉，优先客户实拍；没有则留空",
                    chart_suggestion="无",
                    recommended_layout="cover_title_left_or_center",
                    role=role,
                )
            )
        elif role == "agenda":
            pages.append(
                _page(
                    page_number,
                    title="目录",
                    purpose="交代叙事顺序，方便听众跟上结构。",
                    core_point="按问题 → 方案 → 证据 → 行动推进",
                    supporting_data=["待目录定稿后同步章节名"],
                    image_suggestion="无，或极简章节图标（非装饰堆叠）",
                    chart_suggestion="无",
                    recommended_layout="agenda_list",
                    role=role,
                )
            )
        elif role == "context":
            pages.append(
                _page(
                    page_number,
                    title="背景与目标",
                    purpose="说明为什么现在做这件事，以及成功长什么样。",
                    core_point=_first_sentence(brief) or f"面向{audience}讲清{theme}",
                    supporting_data=_supporting_from_brief(brief)
                    or ["待补：目标、时限或约束"],
                    image_suggestion="场景示意或现状截图；无则留空",
                    chart_suggestion="无",
                    recommended_layout="title_body_two_column",
                    role=role,
                )
            )
        elif role == "content":
            if content_index < len(content_points):
                point = content_points[content_index]
            else:
                point = {
                    "title": f"{theme}要点 {content_index + 1}",
                    "core": "待补：本页只讲一个观点",
                    "support": ["待补：来自客户资料的证据"],
                }
            content_index += 1
            title = point["title"]
            existing_titles = {page["title"] for page in pages}
            if title in existing_titles:
                title = f"{title}（{content_index}）"
            pages.append(
                _page(
                    page_number,
                    title=title,
                    purpose="推进故事线中的一个核心观点，不重复前后页。",
                    core_point=point["core"],
                    supporting_data=point["support"],
                    image_suggestion=(
                        "相关实拍/界面截图"
                        if image_needs.get("requested")
                        else "按需；无真实图则留空"
                    ),
                    chart_suggestion="无",
                    recommended_layout="single_idea_with_evidence",
                    role=role,
                )
            )
        elif role == "data":
            pages.append(
                _page(
                    page_number,
                    title="关键数据",
                    purpose="用可核对的数据支撑判断；没有出处的数字不写死。",
                    core_point="把最重要的一个数据关系讲清楚",
                    supporting_data=_data_supports(snippets)
                    or ["待补：带出处的数据；禁止编造"],
                    image_suggestion="无",
                    chart_suggestion="柱状/折线/占比择一，并标注来源",
                    recommended_layout="chart_focus",
                    role=role,
                )
            )
        elif role == "summary":
            pages.append(
                _page(
                    page_number,
                    title="总结与下一步",
                    purpose="收束观点，给出可执行的下一步。",
                    core_point=f"记住：{theme}对{audience}意味着什么",
                    supporting_data=["待补：下一步行动、负责人或时间"],
                    image_suggestion="无",
                    chart_suggestion="无",
                    recommended_layout="summary_actions",
                    role=role,
                )
            )

    # Refresh agenda supporting data with real section titles.
    section_titles = [
        page["title"]
        for page in pages
        if page["role"] in {"context", "content", "data", "summary"}
    ]
    for page in pages:
        if page["role"] == "agenda":
            page["supporting_data"] = section_titles[:8] or ["待补：章节标题"]
            page["core_point"] = " → ".join(section_titles[:4]) or page["core_point"]

    return {
        "project_id": project_id,
        "created_at": created_at,
        "theme": theme,
        "scenario": scenario,
        "audience": audience,
        "language": language,
        "design_style": style,
        "template_situation": template_situation,
        "requested_page_count": requested_pages,
        "actual_page_count": len(pages),
        "padding_pages": 0,
        "storyline": " → ".join(page["title"] for page in pages),
        "design_anchor": (design.get("style_unification") or {}).get("anchor_template"),
        "research_query": research.get("query"),
        "pages": pages,
        "notes": [
            "No filler pages were added only to hit a page count.",
            "Supporting data without a source is marked 待补; do not invent metrics.",
            "Each content page keeps one core point.",
        ],
    }


def _outline_with_model(
    *,
    client: ModelClient,
    project_id: str,
    info: dict[str, Any],
    analysis: dict[str, Any],
    research: dict[str, Any],
    design: dict[str, Any],
    brief: str,
    snippets: list[dict[str, str]],
    created_at: str,
) -> dict[str, Any]:
    local = _outline_locally(
        project_id=project_id,
        info=info,
        analysis=analysis,
        research=research,
        design=design,
        brief=brief,
        snippets=snippets,
        created_at=created_at,
    )
    system = (
        "You plan PPT outlines. Return JSON only with keys: "
        "storyline, pages. Each page needs page, title, purpose, core_point, "
        "supporting_data (array), image_suggestion, chart_suggestion, "
        "recommended_layout, role. "
        "Do not invent facts or metrics. Use 待补 when evidence is missing. "
        "Do not add filler pages. Keep logical progression and one idea per content page."
    )
    user = json.dumps(
        {
            "brief": brief[:2000],
            "analysis": {
                "theme": analysis.get("theme"),
                "scenario": analysis.get("scenario"),
                "audience": analysis.get("audience"),
                "page_count": analysis.get("page_count"),
                "design_style": analysis.get("design_style"),
                "chart_needs": analysis.get("chart_needs"),
                "image_needs": analysis.get("image_needs"),
                "template_situation": analysis.get("template_situation"),
            },
            "snippets": snippets[:MAX_SNIPPETS],
            "local_draft": local,
        },
        ensure_ascii=False,
    )
    raw = client.complete(system=system, user=user)
    parsed = _extract_json_object(raw)
    merged = dict(local)
    if isinstance(parsed.get("storyline"), str):
        merged["storyline"] = parsed["storyline"]
    if isinstance(parsed.get("pages"), list) and parsed["pages"]:
        pages = []
        for index, item in enumerate(parsed["pages"], start=1):
            if not isinstance(item, dict):
                continue
            pages.append(
                _page(
                    int(item.get("page") or index),
                    title=str(item.get("title") or f"Page {index}"),
                    purpose=str(item.get("purpose") or "推进叙事"),
                    core_point=str(item.get("core_point") or "待补"),
                    supporting_data=_as_str_list(item.get("supporting_data"))
                    or ["待补"],
                    image_suggestion=str(item.get("image_suggestion") or "无"),
                    chart_suggestion=str(item.get("chart_suggestion") or "无"),
                    recommended_layout=str(
                        item.get("recommended_layout") or "single_idea_with_evidence"
                    ),
                    role=str(item.get("role") or "content"),
                )
            )
        if pages:
            merged["pages"] = pages
            merged["actual_page_count"] = len(pages)
            merged["padding_pages"] = 0
    merged["project_id"] = project_id
    merged["created_at"] = created_at
    merged["model_raw_present"] = True
    return merged


def _skeleton_roles(
    *,
    requested_pages: int,
    chart_needs: bool,
    image_needs: bool,
    snippet_count: int,
) -> list[str]:
    # Always meaningful roles. Cap content pages; never invent empty pads.
    target = max(3, min(requested_pages, 16))
    roles = ["cover"]
    if target >= 5:
        roles.append("agenda")
    roles.append("context")

    remaining = target - len(roles) - 1  # reserve summary
    if chart_needs and remaining > 0:
        remaining -= 1
        data_slot = True
    else:
        data_slot = False

    evidence_budget = max(1, snippet_count + (1 if image_needs else 0) + 1)
    content_count = min(remaining if remaining > 0 else 1, evidence_budget, 6)
    content_count = max(1, content_count)

    roles.extend(["content"] * content_count)
    if data_slot:
        roles.append("data")
    roles.append("summary")

    # Trim if somehow over target; never invent filler pages just to match count.
    while len(roles) > target and "content" in roles:
        for index in range(len(roles) - 1, -1, -1):
            if roles[index] == "content" and roles.count("content") > 1:
                del roles[index]
                break
        else:
            break
    return roles


def _content_points(
    *, brief: str, snippets: list[dict[str, str]], theme: str
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for snippet in snippets:
        text = snippet.get("snippet") or ""
        title = _short_title(text) or Path(snippet.get("original_filename") or "point").stem
        points.append(
            {
                "title": title[:40],
                "core": _first_sentence(text) or text[:80] or "待补：核心观点",
                "support": [f"来源文件：{snippet.get('original_filename')}"]
                + ([text[:120]] if text else ["待补：证据"]),
            }
        )
    # Pull bullet-like lines from the brief.
    for line in brief.splitlines():
        cleaned = line.strip().lstrip("-*# ").strip()
        if len(cleaned) < 6:
            continue
        if cleaned.lower().startswith("customer requirements"):
            continue
        if any(cleaned == item["core"] for item in points):
            continue
        points.append(
            {
                "title": _short_title(cleaned) or f"{theme}要点",
                "core": cleaned[:100],
                "support": ["来源：customer_requirements.md"],
            }
        )
        if len(points) >= 6:
            break
    if not points:
        points.append(
            {
                "title": f"{theme}要点",
                "core": "待补：本页只讲一个观点",
                "support": ["待补：来自客户资料的证据"],
            }
        )
    return points


def _page(
    page_number: int,
    *,
    title: str,
    purpose: str,
    core_point: str,
    supporting_data: list[str],
    image_suggestion: str,
    chart_suggestion: str,
    recommended_layout: str,
    role: str,
) -> dict[str, Any]:
    return {
        "page": page_number,
        "title": title,
        "purpose": purpose,
        "core_point": core_point,
        "supporting_data": supporting_data,
        "image_suggestion": image_suggestion,
        "chart_suggestion": chart_suggestion,
        "recommended_layout": recommended_layout,
        "role": role,
    }


def _write_outline(project_dir: Path, outline: dict[str, Any]) -> None:
    content_dir = project_dir / "05_content"
    slides_dir = content_dir / "slide_content"
    slides_dir.mkdir(parents=True, exist_ok=True)
    for old in slides_dir.glob("page-*.md"):
        old.unlink()

    (content_dir / "ppt_outline.md").write_text(
        _outline_markdown(outline), encoding="utf-8"
    )
    payload = {key: value for key, value in outline.items()}
    (content_dir / "ppt_outline.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for page in outline["pages"]:
        path = slides_dir / f"page-{int(page['page']):03d}.md"
        path.write_text(_slide_markdown(page, outline), encoding="utf-8")


def _outline_markdown(outline: dict[str, Any]) -> str:
    lines = [
        "# PPT outline",
        "",
        f"- project_id: `{outline['project_id']}`",
        f"- created_at: `{outline['created_at']}`",
        f"- planner: `{outline.get('planner')}`",
        f"- theme: {outline.get('theme')}",
        f"- scenario: {outline.get('scenario')}",
        f"- audience: {outline.get('audience')}",
        f"- requested_page_count: {outline.get('requested_page_count')}",
        f"- actual_page_count: {outline.get('actual_page_count')}",
        f"- padding_pages: {outline.get('padding_pages')}",
        f"- storyline: {outline.get('storyline')}",
        "",
        "## Pages",
        "",
    ]
    for page in outline["pages"]:
        lines.extend(
            [
                f"### Page {page['page']}: {page['title']}",
                "",
                f"- purpose: {page['purpose']}",
                f"- core_point: {page['core_point']}",
                "- supporting_data:",
            ]
        )
        for item in page["supporting_data"]:
            lines.append(f"  - {item}")
        lines.extend(
            [
                f"- image_suggestion: {page['image_suggestion']}",
                f"- chart_suggestion: {page['chart_suggestion']}",
                f"- recommended_layout: `{page['recommended_layout']}`",
                f"- role: `{page['role']}`",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    for note in outline.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _slide_markdown(page: dict[str, Any], outline: dict[str, Any]) -> str:
    lines = [
        f"# Page {page['page']}: {page['title']}",
        "",
        f"- project_id: `{outline['project_id']}`",
        f"- role: `{page['role']}`",
        "",
        "## Purpose",
        "",
        page["purpose"],
        "",
        "## Core point",
        "",
        page["core_point"],
        "",
        "## Supporting data",
        "",
    ]
    for item in page["supporting_data"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Image suggestion",
            "",
            page["image_suggestion"],
            "",
            "## Chart suggestion",
            "",
            page["chart_suggestion"],
            "",
            "## Recommended layout",
            "",
            f"`{page['recommended_layout']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_outline(outline: dict[str, Any]) -> None:
    pages = outline.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("outline must contain pages")
    if outline.get("padding_pages"):
        raise ValueError("filler/padding pages are not allowed")
    seen_titles: set[str] = set()
    for index, page in enumerate(pages, start=1):
        for key in (
            "page",
            "title",
            "purpose",
            "core_point",
            "supporting_data",
            "image_suggestion",
            "chart_suggestion",
            "recommended_layout",
        ):
            if key not in page:
                raise ValueError(f"page {index} missing {key}")
        title = str(page["title"]).strip()
        if not title:
            raise ValueError(f"page {index} has empty title")
        # Allow agenda/summary uniqueness; content titles must not repeat.
        if page.get("role") == "content":
            if title in seen_titles:
                raise ValueError(f"duplicate content title: {title}")
            seen_titles.add(title)
        if not isinstance(page["supporting_data"], list) or not page["supporting_data"]:
            raise ValueError(f"page {index} needs supporting_data")


def _update_status(project_dir: Path, *, project_id: str, stamp: str) -> None:
    path = project_dir / "00_project_info" / "project_status.json"
    if path.is_file():
        status = json.loads(path.read_text(encoding="utf-8"))
    else:
        status = {"project_id": project_id, "history": []}
    if status.get("project_id") not in {None, project_id}:
        raise ValueError("project_status.json project_id mismatch")
    status["project_id"] = project_id
    status["status"] = "OUTLINE_READY"
    status["updated_at"] = stamp
    status["last_step"] = "ppt_outline"
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append({"status": "OUTLINE_READY", "at": stamp, "step": "ppt_outline"})
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "OUTLINE_READY"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_snippets(project_dir: Path) -> list[dict[str, str]]:
    man_path = manifest_path(project_dir)
    if not man_path.is_file():
        return []
    try:
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    snippets: list[dict[str, str]] = []
    for item in manifest.get("files") or []:
        if item.get("parse_status") != "parsed" or not item.get("result_path"):
            continue
        result_dir = project_dir / item["result_path"]
        content_path = result_dir / "content.json"
        if not content_path.is_file():
            continue
        try:
            payload = json.loads(content_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        text = _snippet_text(payload)
        if not text:
            continue
        snippets.append(
            {
                "original_filename": str(item.get("original_filename") or ""),
                "source": str(item.get("source") or ""),
                "format": str(item.get("format") or ""),
                "snippet": text[:MAX_SNIPPET_CHARS],
            }
        )
        if len(snippets) >= MAX_SNIPPETS:
            break
    return snippets


def _snippet_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    if payload.get("slides"):
        for slide in payload["slides"][:3]:
            parts.extend((slide.get("texts") or [])[:2])
    elif payload.get("pages"):
        for page in payload["pages"][:3]:
            text = (page.get("text") or "").strip()
            if text:
                parts.append(text[:160])
    elif payload.get("paragraphs"):
        parts.extend(payload["paragraphs"][:6])
    elif payload.get("lines"):
        parts.extend(payload["lines"][:8])
    elif payload.get("sheets"):
        for sheet in payload["sheets"][:1]:
            for row in (sheet.get("rows") or [])[:4]:
                parts.append(" | ".join(str(cell) for cell in row))
    return " / ".join(part.strip() for part in parts if str(part).strip())


def _supporting_from_brief(brief: str) -> list[str]:
    items = []
    for line in brief.splitlines():
        cleaned = line.strip().lstrip("-*# ").strip()
        if len(cleaned) >= 6 and not cleaned.lower().startswith("customer requirements"):
            items.append(cleaned)
        if len(items) >= 3:
            break
    return items


def _data_supports(snippets: list[dict[str, str]]) -> list[str]:
    supports = []
    for snippet in snippets:
        if snippet.get("format") in {"xlsx", "pdf", "pptx", "text"}:
            supports.append(
                f"{snippet.get('original_filename')}: {snippet.get('snippet')}"
            )
        if len(supports) >= 3:
            break
    return supports


def _first_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    match = re.split(r"(?<=[。！？.!?])\s+", cleaned, maxsplit=1)
    return match[0][:120]


def _short_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    piece = re.split(r"[。！？.!?:：]", cleaned, maxsplit=1)[0].strip()
    return piece[:40]


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


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


if __name__ == "__main__":
    raise SystemExit(main())
