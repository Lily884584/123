"""Tiny synthetic fixtures for Phase 2 tests. No real customer data."""

from __future__ import annotations

from pathlib import Path


def write_minimal_fixtures(input_root: Path) -> dict[str, Path]:
    """Create one small file per supported format under 01_input."""

    customer = input_root / "customer_files"
    images = input_root / "reference_images"
    templates = input_root / "reference_templates"
    for folder in (customer, images, templates):
        folder.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    paths["txt"] = customer / "notes.txt"
    paths["txt"].write_text("line one\nline two\n", encoding="utf-8")

    paths["md"] = customer / "brief.md"
    paths["md"].write_text("# Brief\n\nA short markdown note.\n", encoding="utf-8")

    paths["docx"] = customer / "memo.docx"
    _write_docx(paths["docx"])

    paths["xlsx"] = customer / "numbers.xlsx"
    _write_xlsx(paths["xlsx"])

    paths["pdf"] = customer / "page.pdf"
    _write_pdf(paths["pdf"])

    paths["pptx"] = templates / "deck.pptx"
    _write_pptx(paths["pptx"])

    paths["png"] = images / "swatch.png"
    _write_png(paths["png"], color=(220, 90, 70))

    paths["jpg"] = images / "swatch.jpg"
    _write_jpg(paths["jpg"], color=(40, 40, 40))

    # Duplicate of notes.txt under another input folder.
    paths["txt_dup"] = templates / "notes-copy.txt"
    paths["txt_dup"].write_bytes(paths["txt"].read_bytes())

    # Unsupported extension should be listed and skipped.
    paths["unsupported"] = customer / "ignore.bin"
    paths["unsupported"].write_bytes(b"\x00\x01\x02\x03")

    return paths


def _write_docx(path: Path) -> None:
    import docx

    document = docx.Document()
    document.add_heading("Memo", level=1)
    document.add_paragraph("Hello from the fixture.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "A"
    table.cell(0, 1).text = "B"
    table.cell(1, 0).text = "1"
    table.cell(1, 1).text = "2"
    document.save(path)


def _write_xlsx(path: Path) -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet["A1"] = "item"
    sheet["B1"] = "count"
    sheet["A2"] = "alpha"
    sheet["B2"] = 3
    workbook.save(path)


def _write_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((40, 80), "Fixture PDF page 1")
    page2 = doc.new_page(width=300, height=200)
    page2.insert_text((40, 80), "Fixture PDF page 2")
    doc.save(path)
    doc.close()


def _write_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    presentation = Presentation()
    presentation.slide_width = Inches(10)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    frame = box.text_frame
    frame.text = "Fixture slide"
    frame.paragraphs[0].font.size = Pt(28)
    presentation.save(path)


def _write_png(path: Path, *, color: tuple[int, int, int]) -> None:
    from PIL import Image

    Image.new("RGB", (32, 24), color=color).save(path, format="PNG")


def _write_jpg(path: Path, *, color: tuple[int, int, int]) -> None:
    from PIL import Image

    Image.new("RGB", (16, 16), color=color).save(path, format="JPEG", quality=90)
