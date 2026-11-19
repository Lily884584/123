"""Phase 6 outline planning writes storyline pages without filler."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.ingest import ingest_project
from aippt.outline import build_outline
from aippt.requirements import analyze_requirements
from aippt.scaffold import create_project
from tests.fixtures import write_minimal_fixtures


class OutlineTest(unittest.TestCase):
    def test_builds_outline_and_slide_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Launch",
                created_on="20261119",
            )
            brief = project / "00_project_info" / "customer_requirements.md"
            brief.write_text(
                "# Customer requirements\n\n"
                "产品介绍给销售团队。页数：8。风格：简洁商务。需要图表。\n"
                "- 讲清产品是什么\n"
                "- 讲清谁该用\n"
                "- 讲清下一步怎么试点\n",
                encoding="utf-8",
            )
            write_minimal_fixtures(project / "01_input")
            ingest_project(project, batch_size=2)
            analysis = analyze_requirements(project)
            outline = build_outline(project)

            self.assertEqual(outline["project_id"], analysis["project_id"])
            self.assertEqual(outline["planner"], "local")
            self.assertEqual(outline["padding_pages"], 0)
            self.assertGreaterEqual(outline["actual_page_count"], 3)
            self.assertLessEqual(outline["actual_page_count"], 8)

            required = {
                "page",
                "title",
                "purpose",
                "core_point",
                "supporting_data",
                "image_suggestion",
                "chart_suggestion",
                "recommended_layout",
            }
            titles = []
            for page in outline["pages"]:
                self.assertTrue(required.issubset(page))
                self.assertTrue(page["supporting_data"])
                titles.append(page["title"])
            self.assertEqual(titles[0], outline["theme"])
            self.assertEqual(outline["pages"][-1]["role"], "summary")

            content_dir = project / "05_content"
            self.assertTrue((content_dir / "ppt_outline.md").is_file())
            self.assertTrue((content_dir / "ppt_outline.json").is_file())
            slide_files = sorted((content_dir / "slide_content").glob("page-*.md"))
            self.assertEqual(len(slide_files), outline["actual_page_count"])
            first_slide = slide_files[0].read_text(encoding="utf-8")
            self.assertIn("## Core point", first_slide)

            # No invented numeric claims without 待补/来源 markers on data page if present.
            md = (content_dir / "ppt_outline.md").read_text(encoding="utf-8")
            self.assertIn("padding_pages: 0", md)

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "OUTLINE_READY")
            self.assertFalse((root / "workspace").exists())
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("OUTLINED", log_text)

    def test_does_not_pad_to_huge_page_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Sparse",
                created_on="20261119",
            )
            brief = project / "00_project_info" / "customer_requirements.md"
            brief.write_text(
                "# Customer requirements\n\n页数：30。只有一句话需求：介绍 Sparse。\n",
                encoding="utf-8",
            )
            analyze_requirements(project)
            outline = build_outline(project)
            self.assertEqual(outline["padding_pages"], 0)
            self.assertLessEqual(outline["actual_page_count"], 16)
            self.assertGreaterEqual(outline["actual_page_count"], 3)


if __name__ == "__main__":
    unittest.main()
