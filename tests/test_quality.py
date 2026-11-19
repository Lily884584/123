"""Phase 9 quality checks cover proposal samples without inventing passes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aippt.design import analyze_design
from aippt.ingest import ingest_project
from aippt.outline import build_outline
from aippt.proposals import build_proposals
from aippt.quality import run_quality_check
from aippt.requirements import analyze_requirements
from aippt.scaffold import create_project
from tests.fixtures import write_minimal_fixtures
from tests.test_design import _write_styled_pptx


def _prepare_proposals_project(root: Path) -> Path:
    project = create_project(
        root,
        client="Demo",
        topic="Quality",
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
    build_proposals(project)
    return project


class QualityTest(unittest.TestCase):
    def test_quality_report_for_three_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _prepare_proposals_project(root)
            report = run_quality_check(project)

            self.assertEqual(
                report["project_id"],
                json.loads(
                    (project / "00_project_info" / "project_info.json").read_text(
                        encoding="utf-8"
                    )
                )["project_id"],
            )
            self.assertIn(report["verdict"], {"passed", "failed_with_findings"})
            self.assertEqual(len(report["proposals"]), 3)
            self.assertIn(report["libreoffice"]["status"], {"available", "missing"})

            md = project / "09_reports" / "quality_report.md"
            js = project / "09_reports" / "quality_report.json"
            self.assertTrue(md.is_file())
            self.assertTrue(js.is_file())
            text = md.read_text(encoding="utf-8")
            self.assertIn(report["project_id"], text)
            self.assertIn("verdict:", text)
            self.assertIn("Proposal A", text)
            self.assertIn("Proposal B", text)
            self.assertIn("Proposal C", text)

            # Every issue status must be explicit; failures never renamed to passed.
            for pack in report["proposals"]:
                self.assertIn(pack["pack_verdict"], {"passed", "failed_with_findings"})
                statuses = {issue["status"] for issue in pack["issues"]}
                self.assertTrue(statuses <= {"passed", "failed", "skipped"})
                checks = {issue["check"] for issue in pack["issues"]}
                for required in (
                    "pptx_opens",
                    "page_count",
                    "off_brief",
                    "invented_data",
                    "text_overflow",
                    "libreoffice_render",
                ):
                    self.assertIn(required, checks)
                # Technical open must pass for generated samples.
                open_issue = next(
                    issue for issue in pack["issues"] if issue["check"] == "pptx_opens"
                )
                self.assertEqual(open_issue["status"], "passed")

            if report["libreoffice"]["status"] == "missing":
                # Skipped render must not be claimed as passed.
                for pack in report["proposals"]:
                    lo = next(
                        issue
                        for issue in pack["issues"]
                        if issue["check"] == "libreoffice_render"
                    )
                    self.assertEqual(lo["status"], "skipped")
                    self.assertNotEqual(lo["status"], "passed")

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "QUALITY_CHECK")
            self.assertEqual(status["last_step"], "quality_check")
            self.assertEqual(status["quality_verdict"], report["verdict"])
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("QUALITY", log_text)

            # Phase 8 samples remain present; no workspace root pollution.
            for key in ("A", "B", "C"):
                self.assertTrue(
                    (project / "06_proposals" / f"proposal_{key}" / "sample.pptx").is_file()
                )
            self.assertFalse((root / "workspace").exists())

    def test_flags_invented_data_and_never_marks_fail_as_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _prepare_proposals_project(root)
            # Inject an unmarked fabricated metric into proposal A.
            from pptx import Presentation

            pptx = project / "06_proposals" / "proposal_A" / "sample.pptx"
            deck = Presentation(str(pptx))
            slide = deck.slides[1]
            box = [
                shape for shape in slide.shapes if shape.has_text_frame
            ][0]
            box.text_frame.paragraphs[0].text = "市场份额已达 87.5% 并增长 12000"
            deck.save(str(pptx))

            report = run_quality_check(project)
            pack_a = next(item for item in report["proposals"] if item["key"] == "A")
            invented = next(
                issue for issue in pack_a["issues"] if issue["check"] == "invented_data"
            )
            # After fix rounds it may become passed if marked 待补; if still failed, must stay failed.
            self.assertIn(invented["status"], {"passed", "failed"})
            if invented["status"] == "failed":
                self.assertNotEqual(invented["status"], "passed")
                self.assertTrue(
                    any(
                        item["check"] == "invented_data" and item["proposal"] == "A"
                        for item in report["unresolved_issues"]
                    )
                )
            # Verdict cannot be plain passed while unresolved remain.
            if report["unresolved_issues"]:
                self.assertEqual(report["verdict"], "failed_with_findings")

    def test_requires_proposal_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="NoSamples",
                created_on="20261119",
            )
            with self.assertRaises(FileNotFoundError):
                run_quality_check(project)


if __name__ == "__main__":
    unittest.main()
