"""Phase 3 requirement analysis stays inside one project."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.ingest import ingest_project
from aippt.requirements import analyze_requirements
from aippt.scaffold import create_project
from tests.fixtures import write_minimal_fixtures


class RequirementsTest(unittest.TestCase):
    def test_analyzes_brief_and_extracted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Product_Launch",
                created_on="20261119",
                special_requirements="产品介绍，中文，页数：12，风格：杂志风，需要图表",
            )
            brief = project / "00_project_info" / "customer_requirements.md"
            brief.write_text(
                "# Customer requirements\n\n"
                "产品介绍给销售团队。参考这个风格重新设计。"
                "页数：12。风格：杂志风。需要图表，不要联网研究。\n",
                encoding="utf-8",
            )
            write_minimal_fixtures(project / "01_input")
            ingest_project(project, batch_size=2)

            analysis = analyze_requirements(project)

            self.assertEqual(
                analysis["project_id"],
                json.loads(
                    (project / "00_project_info" / "project_info.json").read_text(
                        encoding="utf-8"
                    )
                )["project_id"],
            )
            self.assertEqual(analysis["analyzer"], "local")
            self.assertEqual(analysis["template_situation"], "C")
            self.assertEqual(analysis["page_count"], 12)
            self.assertEqual(analysis["language"], "zh-CN")
            self.assertIn("杂志", analysis["design_style"])
            self.assertTrue(analysis["chart_needs"])
            self.assertFalse(analysis["needs_web_research"])

            md_path = project / "00_project_info" / "requirement_analysis.md"
            json_path = project / "00_project_info" / "requirement_analysis.json"
            self.assertTrue(md_path.is_file())
            self.assertTrue(json_path.is_file())
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("template_situation: **C**", md_text)
            self.assertIn("PPT theme:", md_text)

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "ANALYZING")
            self.assertEqual(status["last_step"], "requirements_analysis")
            self.assertEqual(status["history"][-1]["step"], "requirements_analysis")

            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("REQUIREMENTS_ANALYZED", log_text)

            # No shared workspace/requirements at repo root.
            self.assertFalse((root / "workspace").exists())
            self.assertFalse((root / "workspace" / "requirements").exists())

    def test_defaults_when_brief_is_sparse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Sparse",
                created_on="20261119",
            )
            analysis = analyze_requirements(project)
            self.assertEqual(analysis["template_situation"], "A")
            self.assertEqual(analysis["page_count"], 10)
            self.assertEqual(analysis["page_count_source"], "default")
            self.assertTrue(analysis["defaults_used"])
            self.assertEqual(analysis["theme"], "Sparse")


if __name__ == "__main__":
    unittest.main()
