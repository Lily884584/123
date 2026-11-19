"""Project path helpers for Phase 2."""

from __future__ import annotations

import json
from pathlib import Path


def project_info_path(project_dir: Path) -> Path:
    return project_dir / "00_project_info" / "project_info.json"


def input_dir(project_dir: Path) -> Path:
    return project_dir / "01_input"


def extracted_dir(project_dir: Path) -> Path:
    return project_dir / "02_extracted_content"


def manifest_path(project_dir: Path) -> Path:
    return extracted_dir(project_dir) / "file_manifest.json"


def load_project_id(project_dir: Path) -> str:
    path = project_info_path(project_dir)
    if not path.is_file():
        raise FileNotFoundError(f"project_info.json missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    project_id = data.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError(f"project_id missing in {path}")
    return project_id.strip()


def append_project_log(project_dir: Path, line: str) -> None:
    log_path = project_dir / "project.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else line + "\n")
