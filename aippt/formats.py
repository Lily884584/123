"""Supported input formats for Phase 2 scan and parse."""

from __future__ import annotations

INPUT_SUBDIRS = (
    "customer_files",
    "reference_images",
    "reference_templates",
)

# Extension -> format folder under 02_extracted_content/
EXTENSION_TO_FORMAT = {
    ".pptx": "pptx",
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".txt": "text",
    ".md": "text",
    ".png": "images",
    ".jpg": "images",
    ".jpeg": "images",
}

SUPPORTED_EXTENSIONS = frozenset(EXTENSION_TO_FORMAT)


def normalize_extension(path_name: str) -> str:
    return path_name[path_name.rfind(".") :].lower() if "." in path_name else ""


def format_for_extension(extension: str) -> str | None:
    return EXTENSION_TO_FORMAT.get(extension.lower())
