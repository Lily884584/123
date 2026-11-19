"""Phase 4: template search and license recording.

Writes candidates under ``03_research/template_candidates/``.
Does not bypass login, paywalls, or access controls.
Does not invent citations or generate PPT files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aippt.paths import append_project_log, load_project_id, project_info_path

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "public_template_catalog.json"

SOURCE_SITES = {
    "slidesgo": {
        "label": "Slidesgo",
        "home": "https://slidesgo.com/",
        "search": "https://slidesgo.com/search/{query}",
    },
    "slidescarnival": {
        "label": "SlidesCarnival",
        "home": "https://www.slidescarnival.com/",
        "search": "https://www.slidescarnival.com/?s={query}",
    },
    "canva": {
        "label": "Canva",
        "home": "https://www.canva.com/presentations/templates/",
        "search": "https://www.canva.com/search/templates?q={query}",
    },
    "envato_elements": {
        "label": "Envato Elements",
        "home": "https://elements.envato.com/",
        "search": "https://elements.envato.com/search/{query}",
    },
}

USER_AGENT = "AI-PPT-Studio-Research/0.1 (+Phase4; respects robots; no paywall bypass)"


def research_project(
    project_dir: Path | str,
    *,
    query: str | None = None,
    allow_network: bool = False,
    max_candidates: int = 8,
) -> dict[str, Any]:
    """Search template candidates and write research artifacts for one project."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")

    project_id = load_project_id(root)
    info = json.loads(project_info_path(root).read_text(encoding="utf-8"))
    analysis = _load_requirement_analysis(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_query = (query or _default_query(info, analysis)).strip()
    if not search_query:
        raise ValueError("search query is empty; pass --query or set a project topic")

    research_dir = root / "03_research"
    candidates_dir = research_dir / "template_candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_candidates(candidates_dir)

    search_plan = _build_search_plan(search_query)
    catalog_hits = _search_seed_catalog(search_query, max_candidates=max_candidates)
    network_hits: list[dict[str, Any]] = []
    network_errors: list[dict[str, str]] = []
    if allow_network:
        network_hits, network_errors = _search_public_pages(
            search_query, max_candidates=max_candidates
        )

    candidates = _merge_candidates(
        project_id=project_id,
        catalog_hits=catalog_hits,
        network_hits=network_hits,
        max_candidates=max_candidates,
        searched_at=stamp,
        query=search_query,
    )
    needs_user_action = _collect_user_actions(candidates, allow_network=allow_network)

    for index, candidate in enumerate(candidates, start=1):
        path = candidates_dir / f"{index:02d}_{_safe(candidate['id'])}.json"
        path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        candidate["result_path"] = path.relative_to(root).as_posix()

    report = {
        "project_id": project_id,
        "researched_at": stamp,
        "query": search_query,
        "allow_network": allow_network,
        "search_plan": search_plan,
        "candidate_count": len(candidates),
        "commercial_delivery_ready_count": sum(
            1 for item in candidates if item.get("commercial_delivery_allowed") is True
        ),
        "needs_user_action": needs_user_action,
        "network_errors": network_errors,
        "candidates": candidates,
        "topic_research": {
            "status": "not_gathered",
            "note": (
                "Phase 4 does not invent facts, cases, or citations. "
                "Add verified sources to data_sources.md before using numbers in slides."
            ),
        },
    }

    (research_dir / "template_search.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (research_dir / "research_report.md").write_text(
        _research_report_markdown(report, analysis),
        encoding="utf-8",
    )
    (research_dir / "data_sources.md").write_text(
        _data_sources_markdown(report),
        encoding="utf-8",
    )
    _update_status(root, project_id=project_id, stamp=stamp)
    append_project_log(
        root,
        f"{stamp} RESEARCHED project_id={project_id} query={search_query!r} "
        f"candidates={len(candidates)} network={allow_network} "
        f"user_actions={len(needs_user_action)}",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search PPT templates and record license status for one project."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    parser.add_argument(
        "--query",
        help="Override search query. Default: theme/topic from requirement analysis.",
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="Allow fetching public official search pages. Never bypasses login/paywalls.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=8,
        help="Maximum candidates to keep.",
    )
    args = parser.parse_args(argv)
    try:
        report = research_project(
            args.project,
            query=args.query,
            allow_network=args.network,
            max_candidates=args.max_candidates,
        )
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    out = Path(args.project).resolve() / "03_research" / "research_report.md"
    print(out)
    print(
        f"candidates={report['candidate_count']} "
        f"commercial_ready={report['commercial_delivery_ready_count']} "
        f"user_actions={len(report['needs_user_action'])}"
    )
    return 0


def _load_requirement_analysis(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "00_project_info" / "requirement_analysis.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _default_query(info: dict[str, Any], analysis: dict[str, Any]) -> str:
    parts = [
        str(analysis.get("theme") or "").strip(),
        str(analysis.get("scenario") or "").strip(),
        str(analysis.get("design_style") or "").strip(),
        str(info.get("topic") or "").strip(),
    ]
    # Prefer analysis theme; fall back through the list.
    for part in parts:
        if part and part.lower() not in {"未指定受众", "通用汇报", "简洁商务"}:
            # Keep a compact query from theme + scenario when both exist.
            theme = str(analysis.get("theme") or info.get("topic") or "").strip()
            scenario = str(analysis.get("scenario") or "").strip()
            style = str(analysis.get("design_style") or "").strip()
            bits = [theme]
            if scenario and scenario != theme:
                bits.append(scenario)
            if style and style not in bits:
                bits.append(style)
            return " ".join(bit for bit in bits if bit)
    return str(info.get("topic") or analysis.get("theme") or "").strip()


def _build_search_plan(query: str) -> list[dict[str, str]]:
    encoded = urllib.parse.quote(query)
    plan = []
    for key, meta in SOURCE_SITES.items():
        plan.append(
            {
                "source_site": key,
                "label": meta["label"],
                "home_url": meta["home"],
                "search_url": meta["search"].format(query=encoded),
            }
        )
    return plan


def _search_seed_catalog(query: str, *, max_candidates: int) -> list[dict[str, Any]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    tokens = _tokens(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in catalog:
        keywords = [str(value).lower() for value in item.get("keywords") or []]
        haystack = " ".join(
            [
                str(item.get("name") or ""),
                str(item.get("design_style") or ""),
                " ".join(keywords),
            ]
        ).lower()
        score = 0
        for token in tokens:
            if token in haystack:
                score += 2
            if token in keywords:
                score += 2
        if score <= 0 and tokens:
            # Soft fallback: keep one generic hit so offline mode still returns candidates.
            score = 1 if "general" in keywords or "business" in keywords else 0
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("id") or ""))
    hits = []
    for score, item in scored[:max_candidates]:
        hit = dict(item)
        hit["match_score"] = score
        hit["discovery"] = "seed_catalog"
        hits.append(hit)
    return hits


def _search_public_pages(
    query: str, *, max_candidates: int
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    hits: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for plan in _build_search_plan(query):
        source = plan["source_site"]
        url = plan["search_url"]
        try:
            status, final_url, body = _http_get(url)
        except Exception as exc:  # noqa: BLE001 - record and continue
            errors.append(
                {
                    "source_site": source,
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        if status in {401, 403, 407}:
            errors.append(
                {
                    "source_site": source,
                    "url": final_url,
                    "error": f"access_blocked status={status}; paused for user login/purchase",
                }
            )
            hits.append(
                {
                    "id": f"{source}-blocked-{status}",
                    "name": f"{SOURCE_SITES[source]['label']} search requires access",
                    "source_site": source,
                    "page_url": final_url,
                    "preview_image": None,
                    "design_style": None,
                    "provides_pptx": None,
                    "download_conditions": "Login, subscription, or access control detected.",
                    "license_type": "unknown_pending_verification",
                    "commercial_use_allowed": None,
                    "modification_allowed": None,
                    "attribution_required": None,
                    "discovery": "network_blocked",
                    "http_status": status,
                    "needs_user_action": "Provide login/purchase confirmation before continuing on this site.",
                }
            )
            continue

        if status >= 400:
            errors.append(
                {
                    "source_site": source,
                    "url": final_url,
                    "error": f"http_status={status}",
                }
            )
            continue

        if _looks_like_login_wall(body, final_url):
            hits.append(
                {
                    "id": f"{source}-login-wall",
                    "name": f"{SOURCE_SITES[source]['label']} login/paywall encountered",
                    "source_site": source,
                    "page_url": final_url,
                    "preview_image": None,
                    "design_style": None,
                    "provides_pptx": None,
                    "download_conditions": "Page appears to require login or payment. No bypass attempted.",
                    "license_type": "unknown_pending_verification",
                    "commercial_use_allowed": None,
                    "modification_allowed": None,
                    "attribution_required": None,
                    "discovery": "network_login_wall",
                    "http_status": status,
                    "needs_user_action": "Log in or purchase on the official site, then paste approved template URLs.",
                }
            )
            continue

        page_links = _extract_candidate_links(body, source_site=source, base_url=final_url)
        if not page_links:
            # Still record the official search page as a manual follow-up.
            hits.append(
                {
                    "id": f"{source}-search-page",
                    "name": f"{SOURCE_SITES[source]['label']} public search page",
                    "source_site": source,
                    "page_url": final_url,
                    "preview_image": None,
                    "design_style": None,
                    "provides_pptx": None,
                    "download_conditions": "Open the official search page and verify license before download.",
                    "license_type": "unknown_pending_verification",
                    "commercial_use_allowed": None,
                    "modification_allowed": None,
                    "attribution_required": None,
                    "discovery": "network_search_page",
                    "http_status": status,
                    "needs_user_action": "Review this official search page and confirm any template before commercial use.",
                }
            )
            continue

        for link in page_links[: max(1, max_candidates // 4)]:
            hits.append(
                {
                    "id": f"{source}-{_safe(link['slug'])}"[:80],
                    "name": link["title"],
                    "source_site": source,
                    "page_url": link["url"],
                    "preview_image": link.get("preview_image"),
                    "design_style": None,
                    "provides_pptx": None,
                    "download_conditions": "Verify download terms on the official page. Do not bypass login or payment.",
                    "license_type": "unknown_pending_verification",
                    "commercial_use_allowed": None,
                    "modification_allowed": None,
                    "attribution_required": None,
                    "discovery": "network_public_html",
                    "http_status": status,
                    "needs_user_action": "Verify license fields on the official page before commercial delivery.",
                }
            )
    return hits, errors


def _http_get(url: str) -> tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = getattr(response, "status", 200) or 200
            final_url = response.geturl()
            raw = response.read(500_000)
            charset = response.headers.get_content_charset() or "utf-8"
            body = raw.decode(charset, errors="replace")
            return int(status), final_url, body
    except urllib.error.HTTPError as exc:
        raw = exc.read(200_000) if hasattr(exc, "read") else b""
        body = raw.decode("utf-8", errors="replace")
        return int(exc.code), url, body


def _looks_like_login_wall(body: str, url: str) -> bool:
    lowered = body.lower()
    url_l = url.lower()
    markers = (
        "sign in",
        "log in",
        "login",
        "subscribe",
        "membership",
        "payment",
        "checkout",
        "验证",
        "登录",
        "开通会员",
    )
    if any(mark in url_l for mark in ("login", "signin", "subscribe", "checkout")):
        return True
    hits = sum(1 for mark in markers if mark in lowered)
    return hits >= 3 and len(body) < 20000


def _extract_candidate_links(
    body: str, *, source_site: str, base_url: str
) -> list[dict[str, str]]:
    # Conservative: only keep same-site absolute/relative anchors with href+text.
    hrefs = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    home = SOURCE_SITES[source_site]["home"]
    for href, text in hrefs:
        text_clean = re.sub(r"<[^>]+>", "", text)
        text_clean = re.sub(r"\s+", " ", text_clean).strip()
        if len(text_clean) < 4 or len(text_clean) > 120:
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        if not absolute.startswith(home.rstrip("/") ):
            # Allow slidescarnival/slidesgo CDN-less pages on same host.
            host = urllib.parse.urlparse(absolute).netloc
            home_host = urllib.parse.urlparse(home).netloc
            if host != home_host:
                continue
        if absolute in seen:
            continue
        if any(
            skip in absolute.lower()
            for skip in ("login", "signin", "cart", "checkout", "account", "pricing")
        ):
            continue
        seen.add(absolute)
        slug = urllib.parse.urlparse(absolute).path.strip("/").replace("/", "-") or "item"
        results.append({"url": absolute, "title": text_clean, "slug": slug})
        if len(results) >= 10:
            break
    return results


def _merge_candidates(
    *,
    project_id: str,
    catalog_hits: list[dict[str, Any]],
    network_hits: list[dict[str, Any]],
    max_candidates: int,
    searched_at: str,
    query: str,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for raw in catalog_hits + network_hits:
        page_url = str(raw.get("page_url") or "").strip()
        if not page_url or page_url in seen_urls:
            continue
        seen_urls.add(page_url)
        candidate = _normalize_candidate(
            raw,
            project_id=project_id,
            searched_at=searched_at,
            query=query,
        )
        merged.append(candidate)
        if len(merged) >= max_candidates:
            break
    return merged


def _normalize_candidate(
    raw: dict[str, Any],
    *,
    project_id: str,
    searched_at: str,
    query: str,
) -> dict[str, Any]:
    license_type = raw.get("license_type") or "unknown_pending_verification"
    commercial = raw.get("commercial_use_allowed")
    # Unauthorized / unverified templates must not enter commercial delivery.
    commercial_delivery_allowed = commercial is True and license_type not in {
        None,
        "",
        "unknown_pending_verification",
        "unknown",
    }
    return {
        "id": str(raw.get("id") or _safe(str(raw.get("name") or "candidate"))),
        "project_id": project_id,
        "searched_at": searched_at,
        "query": query,
        "name": raw.get("name"),
        "source_site": raw.get("source_site"),
        "page_url": raw.get("page_url"),
        "preview_image": raw.get("preview_image"),
        "design_style": raw.get("design_style"),
        "provides_pptx": raw.get("provides_pptx"),
        "download_conditions": raw.get("download_conditions"),
        "license_type": license_type,
        "commercial_use_allowed": commercial,
        "modification_allowed": raw.get("modification_allowed"),
        "attribution_required": raw.get("attribution_required"),
        "commercial_delivery_allowed": commercial_delivery_allowed,
        "discovery": raw.get("discovery"),
        "needs_user_action": raw.get("needs_user_action"),
        "http_status": raw.get("http_status"),
        "catalog_kind": raw.get("catalog_kind"),
        "match_score": raw.get("match_score"),
    }


def _collect_user_actions(
    candidates: list[dict[str, Any]], *, allow_network: bool
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for item in candidates:
        if item.get("needs_user_action"):
            actions.append(
                {
                    "candidate_id": str(item.get("id")),
                    "page_url": str(item.get("page_url")),
                    "action": str(item.get("needs_user_action")),
                }
            )
        elif item.get("commercial_delivery_allowed") is not True:
            actions.append(
                {
                    "candidate_id": str(item.get("id")),
                    "page_url": str(item.get("page_url")),
                    "action": (
                        "Verify license, commercial use, modification, and attribution "
                        "on the official page before commercial delivery."
                    ),
                }
            )
    if not allow_network:
        actions.insert(
            0,
            {
                "candidate_id": "*",
                "page_url": "",
                "action": (
                    "Network search was off. Re-run with --network to fetch public "
                    "official search pages, or paste user-approved template URLs."
                ),
            },
        )
    # Deduplicate by candidate_id+action
    unique = []
    seen = set()
    for item in actions:
        key = (item["candidate_id"], item["action"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _research_report_markdown(
    report: dict[str, Any], analysis: dict[str, Any]
) -> str:
    lines = [
        "# Research report",
        "",
        f"- project_id: `{report['project_id']}`",
        f"- researched_at: `{report['researched_at']}`",
        f"- query: `{report['query']}`",
        f"- allow_network: `{report['allow_network']}`",
        f"- candidate_count: {report['candidate_count']}",
        f"- commercial_delivery_ready_count: {report['commercial_delivery_ready_count']}",
        "",
        "## Requirement snapshot",
        "",
        f"- theme: {analysis.get('theme')}",
        f"- scenario: {analysis.get('scenario')}",
        f"- design_style: {analysis.get('design_style')}",
        f"- needs_web_research: {analysis.get('needs_web_research')}",
        f"- template_situation: {analysis.get('template_situation')}",
        "",
        "## Official search plan",
        "",
    ]
    for item in report.get("search_plan") or []:
        lines.append(
            f"- {item['label']}: {item['search_url']}"
        )
    lines.extend(["", "## Candidates", ""])
    if not report.get("candidates"):
        lines.append("- none")
    for item in report.get("candidates") or []:
        lines.extend(
            [
                f"### {item.get('name')}",
                "",
                f"- source_site: `{item.get('source_site')}`",
                f"- page_url: {item.get('page_url')}",
                f"- provides_pptx: {item.get('provides_pptx')}",
                f"- license_type: `{item.get('license_type')}`",
                f"- commercial_use_allowed: {item.get('commercial_use_allowed')}",
                f"- modification_allowed: {item.get('modification_allowed')}",
                f"- attribution_required: {item.get('attribution_required')}",
                f"- commercial_delivery_allowed: **{item.get('commercial_delivery_allowed')}**",
                f"- download_conditions: {item.get('download_conditions')}",
                f"- discovery: `{item.get('discovery')}`",
                "",
            ]
        )
    lines.extend(["", "## Needs user action", ""])
    actions = report.get("needs_user_action") or []
    if not actions:
        lines.append("- none")
    else:
        for item in actions:
            target = item.get("candidate_id")
            url = item.get("page_url") or ""
            lines.append(f"- `{target}` {url}: {item.get('action')}")
    lines.extend(
        [
            "",
            "## Topic research",
            "",
            str((report.get("topic_research") or {}).get("note") or ""),
            "",
            "## Policy",
            "",
            "- No login, paywall, or anti-bot bypass.",
            "- Templates with unverified licenses are not commercial-delivery ready.",
            "- Do not invent facts, cases, or citations.",
            "",
        ]
    )
    return "\n".join(lines)


def _data_sources_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Data sources",
        "",
        f"- project_id: `{report['project_id']}`",
        f"- researched_at: `{report['researched_at']}`",
        "",
        "## Template sources",
        "",
    ]
    for item in report.get("candidates") or []:
        lines.append(
            f"- {item.get('name')}: {item.get('page_url')} "
            f"(license={item.get('license_type')}, "
            f"commercial_delivery_allowed={item.get('commercial_delivery_allowed')})"
        )
    if not report.get("candidates"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Factual sources",
            "",
            "- none gathered in Phase 4",
            "- Do not invent statistics, case studies, or quotes.",
            "- When real sources are added later, record URL, title, accessed_at, and the claim they support.",
            "",
        ]
    )
    if report.get("network_errors"):
        lines.extend(["## Network errors", ""])
        for item in report["network_errors"]:
            lines.append(
                f"- {item.get('source_site')}: {item.get('url')} -> {item.get('error')}"
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
    status["status"] = "RESEARCHING"
    status["updated_at"] = stamp
    status["last_step"] = "template_research"
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {"status": "RESEARCHING", "at": stamp, "step": "template_research"}
    )
    status["history"] = history
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    info_path = project_info_path(project_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["status"] = "RESEARCHING"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _clear_generated_candidates(candidates_dir: Path) -> None:
    for path in candidates_dir.glob("*.json"):
        path.unlink()


def _tokens(query: str) -> list[str]:
    parts = re.split(r"[\s,_/-]+", query.lower())
    return [part for part in parts if len(part) >= 2]


def _safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "item"


if __name__ == "__main__":
    raise SystemExit(main())
