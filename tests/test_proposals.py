"""Phase 8 three-proposal samples share core content with distinct styles."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.design import analyze_design
from aippt.ingest import ingest_project
from aippt.outline import build_outline
from aippt.proposals import BASE_STYLES, build_proposals
from aippt.requirements import analyze_requirements
from aippt.scaffold import create_project
from tests.fixtures import write_minimal_fixtures
from tests.test_design import _write_styled_pptx


def _prepare_outlined_project(root: Path) -> Path:
    project = create_project(
        root,
        client="Demo",
        topic="Proposals",
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
    _write_styled_pptx(project / "01_input" / "reference_templates" / "anchor.pptx")
    ingest_project(project, batch_size=2)
    analyze_requirements(project)
    analyze_design(project)
    build_outline(project)
    return project


class ProposalsTest(unittest.TestCase):
    def test_builds_three_distinct_proposal_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _prepare_outlined_project(root)
            outline = json.loads(
                (project / "05_content" / "ppt_outline.json").read_text(encoding="utf-8")
            )
            report = build_proposals(project)

            self.assertEqual(report["sample_page_count"], 5)
            self.assertEqual(
                set(report["shared_core_roles"]),
                {"cover", "section", "analysis", "chart", "summary"},
            )
            self.assertEqual(len(report["proposals"]), 3)

            names = {item["name"] for item in report["proposals"]}
            self.assertEqual(
                names,
                {BASE_STYLES["A"]["name"], BASE_STYLES["B"]["name"], BASE_STYLES["C"]["name"]},
            )

            from pptx import Presentation

            decks = {}
            for key in ("A", "B", "C"):
                folder = project / "06_proposals" / f"proposal_{key}"
                pptx = folder / "sample.pptx"
                desc = folder / "design_description.md"
                preview = folder / "preview"
                self.assertTrue(pptx.is_file(), key)
                self.assertTrue(desc.is_file(), key)
                self.assertTrue((preview / "preview_manifest.json").is_file(), key)
                self.assertEqual(len(list(preview.glob("page-*.png"))), 5, key)

                deck = Presentation(str(pptx))
                self.assertEqual(len(deck.slides), 5, key)
                decks[key] = deck

                text = desc.read_text(encoding="utf-8")
                self.assertIn(f"Proposal {key}", text)
                self.assertIn("Shared sample pages", text)

            # Same core titles across packs (comparison requirement).
            titles = report["shared_core_titles"]
            self.assertEqual(len(titles), 5)
            for key in ("A", "B", "C"):
                desc = (
                    project / "06_proposals" / f"proposal_{key}" / "design_description.md"
                ).read_text(encoding="utf-8")
                for title in titles:
                    self.assertIn(title, desc)

            # Visual systems must differ (background tokens in descriptions).
            descs = {
                key: (
                    project / "06_proposals" / f"proposal_{key}" / "design_description.md"
                ).read_text(encoding="utf-8")
                for key in ("A", "B", "C")
            }
            self.assertIn(BASE_STYLES["A"]["background"], descs["A"])
            self.assertIn(BASE_STYLES["B"]["background"], descs["B"])
            self.assertIn(BASE_STYLES["C"]["background"], descs["C"])
            self.assertNotEqual(BASE_STYLES["A"]["background"], BASE_STYLES["C"]["background"])

            # Chart caption must not invent metrics as real data.
            chart_texts = []
            for slide in decks["B"].slides:
                for shape in slide.shapes:
                    if shape.has_text_frame and "待补" in shape.text_frame.text:
                        chart_texts.append(shape.text_frame.text)
            self.assertTrue(any("占位示意" in text or "待补" in text for text in chart_texts))

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "WAITING_APPROVAL")
            self.assertEqual(status["last_step"], "three_proposals")
            self.assertTrue((project / "06_proposals" / "proposals_report.json").is_file())
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("PROPOSALS", log_text)
            self.assertFalse((root / "workspace").exists())

            # Outline and input templates untouched by Phase 8.
            self.assertEqual(
                outline["actual_page_count"],
                json.loads(
                    (project / "05_content" / "ppt_outline.json").read_text(
                        encoding="utf-8"
                    )
                )["actual_page_count"],
            )
            self.assertTrue(
                (project / "01_input" / "reference_templates" / "anchor.pptx").is_file()
            )

    def test_requires_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Empty",
                created_on="20261119",
            )
            with self.assertRaises(FileNotFoundError):
                build_proposals(project)


if __name__ == "__main__":
    unittest.main()
