"""Phase 5 design analysis builds a unified design system from local PPTX."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.design import analyze_design
from aippt.scaffold import create_project


def _write_styled_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.util import Inches, Pt

    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    slide = presentation.slides.add_slide(blank)

    title = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(10), Inches(1))
    title_frame = title.text_frame
    title_frame.text = "Design Anchor"
    title_run = title_frame.paragraphs[0].runs[0]
    title_run.font.name = "Arial"
    title_run.font.size = Pt(36)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x11, 0x11, 0x11)

    body = slide.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(8), Inches(1))
    body_frame = body.text_frame
    body_frame.text = "Body copy for spacing and typography."
    body_run = body_frame.paragraphs[0].runs[0]
    body_run.font.name = "Calibri"
    body_run.font.size = Pt(16)
    body_run.font.color.rgb = RGBColor(0x4A, 0x4A, 0x4A)

    accent = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(0.8),
        Inches(3.2),
        Inches(2.5),
        Inches(0.4),
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = RGBColor(0xDF, 0x77, 0x5A)
    accent.line.fill.background()

    presentation.save(path)


class DesignTest(unittest.TestCase):
    def test_builds_design_system_from_reference_pptx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Design",
                created_on="20261119",
            )
            template = (
                project / "01_input" / "reference_templates" / "anchor.pptx"
            )
            _write_styled_pptx(template)

            design = analyze_design(project)

            self.assertEqual(
                design["project_id"],
                json.loads(
                    (project / "00_project_info" / "project_info.json").read_text(
                        encoding="utf-8"
                    )
                )["project_id"],
            )
            self.assertEqual(design["sources"][0]["original_filename"], "anchor.pptx")
            self.assertAlmostEqual(
                design["design_tokens"]["page"]["aspect_ratio"], 1.7777, places=3
            )

            design_root = project / "04_design"
            for relative in (
                "design_system/design_tokens.json",
                "color_palette.json",
                "typography.json",
                "layouts.json",
                "design_system/template_rules.md",
                "design_analysis.json",
            ):
                self.assertTrue((design_root / relative).is_file(), relative)

            palette = json.loads(
                (design_root / "color_palette.json").read_text(encoding="utf-8")
            )
            self.assertEqual(palette["project_id"], design["project_id"])
            self.assertTrue(palette["primary"].startswith("#"))
            self.assertIn("#DF775A", {palette["primary"], palette["secondary"], palette["accent"]} | {
                item["hex"] for item in palette["candidates"]
            })

            typography = json.loads(
                (design_root / "typography.json").read_text(encoding="utf-8")
            )
            self.assertIn(typography["title"]["font"], {"Arial", "Calibri"})
            self.assertGreaterEqual(typography["title"]["size_pt"], 24)

            rules = (design_root / "design_system" / "template_rules.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("anchor.pptx", rules)
            self.assertIn("Keep one visual hierarchy", rules)

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "DESIGNING")
            self.assertEqual(status["last_step"], "template_design_analysis")
            self.assertFalse((root / "workspace").exists())

            # Original template stays in place.
            self.assertTrue(template.is_file())
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("DESIGNED", log_text)

    def test_requires_local_pptx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Empty",
                created_on="20261119",
            )
            with self.assertRaises(FileNotFoundError):
                analyze_design(project)


if __name__ == "__main__":
    unittest.main()
