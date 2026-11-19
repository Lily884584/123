"""Run Phase 2 scan then parse for one project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aippt.parse import DEFAULT_BATCH_SIZE, parse_project
from aippt.paths import manifest_path
from aippt.scan import scan_project


def ingest_project(
    project_dir: Path | str,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    scan_project(project_dir)
    return parse_project(project_dir, batch_size=batch_size)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan and parse one AI PPT Studio project (Phase 2)."
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Path to projects/<Client>_<Topic>_<YYYYMMDD>/",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Pages or rows processed per batch for large files.",
    )
    args = parser.parse_args(argv)
    try:
        manifest = ingest_project(args.project, batch_size=args.batch_size)
    except (OSError, ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 1
    info = manifest.get("parser", {})
    print(manifest_path(Path(args.project).resolve()))
    print(
        f"files={manifest['file_count']} parsed={info.get('parsed_count', 0)} "
        f"failed={info.get('failed_count', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
