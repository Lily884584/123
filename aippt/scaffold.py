"""Create an isolated client project directory.

Phase 1 builds the SOP 1.1 folder tree, project metadata, and project.log.
Parsing, research, design, and PPT generation stay in later phases.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_TREE = Path(__file__).resolve().parent / "project_tree"

_LABEL = re.compile(r"(?u)[\w][\w-]*\Z")
_DATE = re.compile(r"\d{8}\Z")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|password|passwd|secret|access[_-]?token)\b\s*[:=]"
)


def create_project(
    repo_root: Path | str,
    client: str,
    topic: str,
    created_on: str | None = None,
    *,
    project_name: str | None = None,
    due_on: str | None = None,
    owner: str | None = None,
    special_requirements: str | None = None,
) -> Path:
    """Create ``projects/<Client>_<Topic>_<YYYYMMDD>/`` under ``repo_root``.

    The new directory is the only path this function adds. Client files belong
    inside that tree. API keys and passwords are rejected if a text field
    tries to store them.
    """

    root = Path(repo_root)
    if not root.is_dir():
        raise NotADirectoryError(f"repository root is not a directory: {root}")

    client_label = _label(client, "client")
    topic_label = _label(topic, "topic")
    created = _date(created_on)
    folder_name = f"{client_label}_{topic_label}_{created}"
    display_name = _single_line(project_name, "project name") or folder_name
    due = _date(due_on) if due_on is not None and due_on.strip() else None
    owner_name = _single_line(owner, "owner")
    requirements = _requirements(special_requirements)

    destination = root / "projects" / folder_name
    if destination.exists():
        raise FileExistsError(f"project directory already exists: {destination}")

    project_id = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    shutil.copytree(PROJECT_TREE, destination)
    _write_metadata(
        destination,
        project_id=project_id,
        client=client_label,
        project_name=display_name,
        topic=topic_label,
        created_on=created,
        created_at=stamp,
        due_on=due,
        owner=owner_name,
        special_requirements=requirements,
        folder_name=folder_name,
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create an AI PPT Studio client project directory."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Default: current directory.",
    )
    parser.add_argument("--client", required=True, help="Client name or code.")
    parser.add_argument("--topic", required=True, help="PPT topic.")
    parser.add_argument("--date", help="Creation date, YYYYMMDD. Default: today UTC.")
    parser.add_argument(
        "--project-name",
        help="Display name. Default: the project directory name.",
    )
    parser.add_argument("--due-on", help="Optional due date, YYYYMMDD.")
    parser.add_argument("--owner", help="Optional project owner.")
    parser.add_argument(
        "--requirements",
        help="Optional special requirements. Keep API keys and passwords in environment variables.",
    )
    args = parser.parse_args(argv)
    try:
        path = create_project(
            args.root,
            args.client,
            args.topic,
            args.date,
            project_name=args.project_name,
            due_on=args.due_on,
            owner=args.owner,
            special_requirements=args.requirements,
        )
    except (ValueError, FileExistsError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(path)
    return 0


def _label(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    collapsed = "_".join(value.split())
    if not collapsed:
        raise ValueError(f"{field} is required")
    if any(mark in collapsed for mark in ("/", "\\", "\x00", "..")):
        raise ValueError(f"{field} must be a single directory name")
    if not _LABEL.fullmatch(collapsed):
        raise ValueError(
            f"{field} may contain letters, numbers, underscores, and hyphens"
        )
    _reject_secret(collapsed, field)
    return collapsed


def _date(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).strftime("%Y%m%d")
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("date must be YYYYMMDD")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("date must be YYYYMMDD") from exc
    return value


def _single_line(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    text = value.strip()
    if not text:
        return None
    if any(mark in text for mark in ("\x00", "\n", "\r")):
        raise ValueError(f"{field} must be a single line")
    _reject_secret(text, field)
    return text


def _requirements(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("special requirements must be a string")
    text = value.strip()
    if not text:
        return None
    if "\x00" in text:
        raise ValueError("special requirements must not contain null characters")
    _reject_secret(text, "special requirements")
    return text


def _reject_secret(value: str, field: str) -> None:
    if _SECRET_ASSIGNMENT.search(value):
        raise ValueError(
            f"{field} must not store API keys or passwords in a project directory"
        )


def _write_metadata(
    destination: Path,
    *,
    project_id: str,
    client: str,
    project_name: str,
    topic: str,
    created_on: str,
    created_at: str,
    due_on: str | None,
    owner: str | None,
    special_requirements: str | None,
    folder_name: str,
) -> None:
    info = {
        "project_id": project_id,
        "client": client,
        "project_name": project_name,
        "topic": topic,
        "created_on": created_on,
        "created_at": created_at,
        "due_on": due_on,
        "owner": owner,
        "status": "CREATED",
        "special_requirements": special_requirements,
    }
    status = {
        "project_id": project_id,
        "status": "CREATED",
        "updated_at": created_at,
        "history": [{"status": "CREATED", "at": created_at}],
    }
    info_dir = destination / "00_project_info"
    _write_json(info_dir / "project_info.json", info)
    _write_json(info_dir / "project_status.json", status)
    brief = "# Customer requirements\n"
    if special_requirements is not None:
        brief += "\n" + special_requirements + "\n"
    (info_dir / "customer_requirements.md").write_text(brief, encoding="utf-8")
    log_line = f"{created_at} CREATED project_id={project_id} directory={folder_name}\n"
    (destination / "project.log").write_text(log_line, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
