"""Phase 7: dual-engine PPT generation (ENGINE B / ENGINE C).

Chooses template fill when an authorized local PPTX is usable; otherwise
redesigns from the Design System. Writes intermediate decks under
``05_content/generated/`` — full proposal triplets stay in Phase 8.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aippt.engine_b import generate_engine_b
from aippt.engine_c import generate_engine_c
from aippt.paths import append_project_log, load_project_id, project_info_path

GENERATED_DIR = "05_content/generated"


def generate_pptx(
    project_dir: Path | str,
    *,
    engine: str = "auto",
) -> dict[str, Any]:
    """Run Engine B and/or C for one project and write generation artifacts."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"project directory not found: {root}")
    engine_choice = (engine or "auto").strip().lower()
    if engine_choice not in {"auto", "b", "c"}:
        raise ValueError("engine must be one of: auto, b, c")

    project_id = load_project_id(root)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outline = _load_outline(root)
    design = _load_design(root)
    research = _load_json(root / "03_research" / "template_search.json")
    reference_images = _discover_reference_images(root)

    selection = _select_engine(
        root,
        engine_choice=engine_choice,
        research=research,
    )
    out_dir = root / GENERATED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    chosen = selection["engine"]

    if chosen == "B":
        template = Path(selection["template_path"])
        result = generate_engine_b(
            template_path=template,
            outline=outline,
            design=design,
            output_path=out_dir / "engine_b.pptx",
            reference_images=reference_images,
        )
        result["selection_reason"] = selection["reason"]
        result["commercial_delivery_allowed"] = selection["commercial_delivery_allowed"]
        results.append(result)
        primary_path = result["output_path"]
    else:
        if design is None:
            raise FileNotFoundError(
                "ENGINE C needs 04_design/design_analysis.json; run design analysis first"
            )
        result = generate_engine_c(
            outline=outline,
            design=design,
            output_path=out_dir / "engine_c.pptx",
            reference_images=reference_images,
        )
        result["selection_reason"] = selection["reason"]
        result["commercial_delivery_allowed"] = selection.get(
            "commercial_delivery_allowed"
        )
        results.append(result)
        primary_path = result["output_path"]

    report = {
        "project_id": project_id,
        "created_at": stamp,
        "requested_engine": engine_choice,
        "selected_engine": chosen,
        "selection_reason": selection["reason"],
        "outline_pages": len(outline.get("pages") or []),
        "primary_pptx": str(Path(primary_path).relative_to(root).as_posix()),
        "commercial_delivery_allowed": selection.get("commercial_delivery_allowed"),
        "template_path": selection.get("template_path"),
        "image_as_full_background": any(
            item.get("image_as_full_background") for item in results
        ),
        "engines": results,
        "artifacts": [
            f"{GENERATED_DIR}/generation.json",
            f"{GENERATED_DIR}/generation_report.md",
            str(Path(primary_path).relative_to(root).as_posix()),
        ],
        "notes": [
            "Intermediate draft only; Phase 8 produces proposal_A/B/C samples.",
            "Original files under 01_input/ were not modified.",
            "Unauthorized templates are never selected for commercial delivery.",
        ],
    }
    _write_report(out_dir, report)
    _update_status(root, project_id=project_id, stamp=stamp, engine=chosen)
    append_project_log(
        root,
        f"{stamp} GENERATED project_id={project_id} engine={chosen} "
        f"pages={report['outline_pages']} pptx={report['primary_pptx']}",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an intermediate PPTX with Engine B or Engine C."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    parser.add_argument(
        "--engine",
        choices=("auto", "b", "c"),
        default="auto",
        help="Force an engine, or auto-select (default).",
    )
    args = parser.parse_args(argv)
    try:
        report = generate_pptx(args.project, engine=args.engine)
    except (
        OSError,
        ValueError,
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
    ) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(Path(args.project).resolve() / GENERATED_DIR / "generation_report.md")
    print(
        f"engine={report['selected_engine']} "
        f"pages={report['outline_pages']} "
        f"pptx={report['primary_pptx']}"
    )
    return 0


def _select_engine(
    project_dir: Path,
    *,
    engine_choice: str,
    research: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = _find_fillable_template(project_dir, research=research)

    if engine_choice == "b":
        if candidate is None:
            raise FileNotFoundError(
                "ENGINE B requested but no authorized local PPTX template was found"
            )
        if candidate["commercial_delivery_allowed"] is not True:
            raise PermissionError(
                "ENGINE B refused: template is not commercial_delivery_allowed"
            )
        return {
            "engine": "B",
            "reason": "forced Engine B with authorized local template",
            **candidate,
        }

    if engine_choice == "c":
        return {
            "engine": "C",
            "reason": "forced Engine C redesign from design system",
            "template_path": candidate.get("template_path") if candidate else None,
            "commercial_delivery_allowed": (
                candidate.get("commercial_delivery_allowed") if candidate else None
            ),
        }

    # auto
    if candidate and candidate["commercial_delivery_allowed"] is True:
        return {
            "engine": "B",
            "reason": (
                "authorized local PPTX available for smart fill "
                f"({candidate.get('source')})"
            ),
            **candidate,
        }
    if candidate and candidate["commercial_delivery_allowed"] is not True:
        return {
            "engine": "C",
            "reason": (
                "local template present but commercial_delivery_allowed is false; "
                "redesign with Engine C instead of delivering unauthorized fill"
            ),
            "template_path": candidate.get("template_path"),
            "commercial_delivery_allowed": False,
        }
    return {
        "engine": "C",
        "reason": "no suitable authorized local PPTX; redesign with Engine C",
        "template_path": None,
        "commercial_delivery_allowed": None,
    }


def _find_fillable_template(
    project_dir: Path,
    *,
    research: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Pick a local PPTX that may be filled.

    Customer-supplied files under ``01_input/`` are treated as authorized for
    that project. Catalog / public templates require
    ``commercial_delivery_allowed=true`` from research records.
    """

    # 1) Customer / reference uploads — project-scoped authorization.
    for source_name, folder in (
        ("reference_templates", project_dir / "01_input" / "reference_templates"),
        ("customer_files", project_dir / "01_input" / "customer_files"),
    ):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.pptx")):
            if path.name.startswith("~"):
                continue
            return {
                "template_path": str(path),
                "source": source_name,
                "original_filename": path.name,
                "commercial_delivery_allowed": True,
                "authorization": "customer_supplied_project_input",
            }

    # 2) Shared public templates only when research marks them commercial-ready.
    public_root = Path(__file__).resolve().parents[1] / "templates" / "public"
    allowed_names = {
        str(item.get("name") or "").strip().lower()
        for item in (research or {}).get("candidates") or []
        if item.get("commercial_delivery_allowed") is True
    }
    if public_root.is_dir():
        for path in sorted(public_root.rglob("*.pptx")):
            stem = path.stem.lower()
            name = path.name.lower()
            if allowed_names and not (
                stem in allowed_names or name in allowed_names
            ):
                # Public file without a matching commercial-ready record: skip.
                continue
            if not allowed_names:
                # No commercial-ready research hit → cannot use shared public copy.
                continue
            return {
                "template_path": str(path),
                "source": "templates/public",
                "original_filename": path.name,
                "commercial_delivery_allowed": True,
                "authorization": "research_commercial_delivery_allowed",
            }

    # 3) Local PPTX exists under public but unauthorized — surface for Engine C path.
    if public_root.is_dir():
        for path in sorted(public_root.rglob("*.pptx")):
            return {
                "template_path": str(path),
                "source": "templates/public",
                "original_filename": path.name,
                "commercial_delivery_allowed": False,
                "authorization": "public_without_verified_license",
            }
    return None


def _load_outline(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "05_content" / "ppt_outline.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"ppt_outline.json missing: {path} (run outline planning first)"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ppt_outline.json must be an object")
    return data


def _load_design(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "04_design" / "design_analysis.json"
    if not path.is_file():
        # Fall back to assembling from token files when analysis summary is absent.
        tokens = _load_json(project_dir / "04_design" / "design_system" / "design_tokens.json")
        palette = _load_json(project_dir / "04_design" / "color_palette.json")
        typography = _load_json(project_dir / "04_design" / "typography.json")
        layouts = _load_json(project_dir / "04_design" / "layouts.json")
        if not any([tokens, palette, typography, layouts]):
            return None
        return {
            "design_tokens": tokens or {},
            "color_palette": palette or {},
            "typography": typography or {},
            "layouts": layouts or {},
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("design_analysis.json must be an object")
    # design_analysis.json is a summary; merge sibling token files when present.
    merged = dict(data)
    for key, relative in (
        ("design_tokens", "design_system/design_tokens.json"),
        ("color_palette", "color_palette.json"),
        ("typography", "typography.json"),
        ("layouts", "layouts.json"),
    ):
        payload = _load_json(project_dir / "04_design" / relative)
        if payload:
            merged[key] = payload
    return merged


def _discover_reference_images(project_dir: Path) -> list[Path]:
    folder = project_dir / "01_input" / "reference_images"
    if not folder.is_dir():
        return []
    images: list[Path] = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"} and path.is_file():
            images.append(path)
    return images


def _write_report(out_dir: Path, report: dict[str, Any]) -> None:
    (out_dir / "generation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "generation_report.md").write_text(
        _report_markdown(report),
        encoding="utf-8",
    )


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Generation report",
        "",
        f"- project_id: `{report['project_id']}`",
        f"- created_at: `{report['created_at']}`",
        f"- requested_engine: `{report['requested_engine']}`",
        f"- selected_engine: `{report['selected_engine']}`",
        f"- selection_reason: {report['selection_reason']}",
        f"- outline_pages: {report['outline_pages']}",
        f"- primary_pptx: `{report['primary_pptx']}`",
        f"- commercial_delivery_allowed: `{report.get('commercial_delivery_allowed')}`",
        f"- image_as_full_background: `{report.get('image_as_full_background')}`",
        "",
        "## Engine results",
        "",
    ]
    for item in report.get("engines") or []:
        lines.append(f"### Engine {item.get('engine')}")
        lines.append("")
        for key, value in item.items():
            if key == "engine":
                continue
            lines.append(f"- {key}: `{value}`")
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
    engine: str,
) -> None:
    path = project_dir / "00_project_info" / "project_status.json"
    if path.is_file():
        status = json.loads(path.read_text(encoding="utf-8"))
    else:
        status = {"project_id": project_id, "history": []}
    if status.get("project_id") not in {None, project_id}:
        raise ValueError("project_status.json project_id mismatch")
    # Phase 7 drafts precede Phase 8 sample triplets; keep OUTLINE_READY lineage
    # but record the dual-engine step for audit.
    status["project_id"] = project_id
    status["status"] = "OUTLINE_READY"
    status["updated_at"] = stamp
    status["last_step"] = "dual_engine_generate"
    status["last_engine"] = engine
    history = status.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "status": "OUTLINE_READY",
            "at": stamp,
            "step": "dual_engine_generate",
            "engine": engine,
        }
    )
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


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
