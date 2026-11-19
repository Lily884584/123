"""Phase 7 dual-engine generation fills or redesigns without touching originals."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.design import analyze_design
from aippt.generate import generate_pptx
from aippt.ingest import ingest_project
from aippt.outline import build_outline
from aippt.requirements import analyze_requirements
from aippt.scaffold import create_project
from tests.fixtures import write_minimal_fixtures
from tests.test_design import _write_styled_pptx


def _prepare_project(root: Path, *, client: str = "Demo", topic: str = "Gen") -> Path:
    project = create_project(
        root,
        client=client,
        topic=topic,
        created_on="20261119",
    )
    brief = project / "00_project_info" / "customer_requirements.md"
    brief.write_text(
        "# Customer requirements\n\n"
        "产品介绍给销售团队。页数：6。风格：简洁商务。需要图表。\n"
        "- 讲清产品是什么\n"
        "- 讲清谁该用\n"
        "- 讲清下一步怎么试点\n",
        encoding="utf-8",
    )
    write_minimal_fixtures(project / "01_input")
    # Richer template for design tokens + Engine B fill.
    _write_styled_pptx(
        project / "01_input" / "reference_templates" / "anchor.pptx"
    )
    ingest_project(project, batch_size=2)
    analyze_requirements(project)
    analyze_design(project)
    build_outline(project)
    return project


class GenerateTest(unittest.TestCase):
    def test_auto_selects_engine_b_for_customer_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _prepare_project(root, topic="Fill")
            template = (
                project / "01_input" / "reference_templates" / "anchor.pptx"
            )
            before = template.read_bytes()

            report = generate_pptx(project, engine="auto")

            self.assertEqual(report["selected_engine"], "B")
            self.assertTrue(report["commercial_delivery_allowed"])
            self.assertFalse(report["image_as_full_background"])
            pptx_path = project / report["primary_pptx"]
            self.assertTrue(pptx_path.is_file())
            self.assertTrue(
                (project / "05_content" / "generated" / "generation.json").is_file()
            )
            self.assertTrue(
                (project / "05_content" / "generated" / "generation_report.md").is_file()
            )

            # Original input template stays byte-identical.
            self.assertEqual(template.read_bytes(), before)

            from pptx import Presentation

            deck = Presentation(str(pptx_path))
            texts = []
            for slide in deck.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        texts.append(shape.text_frame.text)
            joined = "\n".join(texts)
            outline = json.loads(
                (project / "05_content" / "ppt_outline.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreaterEqual(len(deck.slides), outline["actual_page_count"])
            self.assertIn(outline["pages"][0]["title"], joined)

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["last_step"], "dual_engine_generate")
            self.assertEqual(status["last_engine"], "B")
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("GENERATED", log_text)
            self.assertFalse((root / "workspace").exists())

    def test_engine_c_redesign_from_design_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _prepare_project(root, topic="Redesign")
            report = generate_pptx(project, engine="c")

            self.assertEqual(report["selected_engine"], "C")
            self.assertFalse(report["image_as_full_background"])
            pptx_path = project / report["primary_pptx"]
            self.assertTrue(pptx_path.is_file())
            self.assertEqual(pptx_path.name, "engine_c.pptx")

            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            deck = Presentation(str(pptx_path))
            outline = json.loads(
                (project / "05_content" / "ppt_outline.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(deck.slides), outline["actual_page_count"])

            # No picture may cover the full slide (background abuse guard).
            slide_area = int(deck.slide_width) * int(deck.slide_height)
            for slide in deck.slides:
                for shape in slide.shapes:
                    if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
                        continue
                    area = int(shape.width) * int(shape.height)
                    self.assertLess(area / slide_area, 0.5)

            texts = []
            for slide in deck.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        texts.append(shape.text_frame.text)
            self.assertIn(outline["pages"][0]["title"], "\n".join(texts))

    def test_rejects_forced_b_without_authorized_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="NoTpl",
                created_on="20261119",
            )
            # Outline without any local PPTX.
            content = project / "05_content"
            content.mkdir(parents=True, exist_ok=True)
            (content / "ppt_outline.json").write_text(
                json.dumps(
                    {
                        "project_id": json.loads(
                            (project / "00_project_info" / "project_info.json").read_text(
                                encoding="utf-8"
                            )
                        )["project_id"],
                        "pages": [
                            {
                                "page": 1,
                                "title": "Only Page",
                                "purpose": "demo",
                                "core_point": "point",
                                "supporting_data": ["待补"],
                                "image_suggestion": "无",
                                "chart_suggestion": "无",
                                "recommended_layout": "title_body",
                                "role": "cover",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                generate_pptx(project, engine="b")


if __name__ == "__main__":
    unittest.main()
