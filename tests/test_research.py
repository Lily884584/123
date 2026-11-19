"""Phase 4 template research records licenses without inventing facts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aippt.requirements import analyze_requirements
from aippt.research import research_project
from aippt.scaffold import create_project


class ResearchTest(unittest.TestCase):
    def test_offline_template_search_writes_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Product_Launch",
                created_on="20261119",
            )
            brief = project / "00_project_info" / "customer_requirements.md"
            brief.write_text(
                "# Customer requirements\n\n"
                "产品介绍路演，风格简洁商务，需要模板参考。\n",
                encoding="utf-8",
            )
            analysis = analyze_requirements(project)
            report = research_project(project, allow_network=False, max_candidates=4)

            self.assertEqual(report["project_id"], analysis["project_id"])
            self.assertFalse(report["allow_network"])
            self.assertGreaterEqual(report["candidate_count"], 1)
            self.assertEqual(report["commercial_delivery_ready_count"], 0)
            self.assertTrue(report["needs_user_action"])
            self.assertEqual(
                (report.get("topic_research") or {}).get("status"), "not_gathered"
            )

            research_dir = project / "03_research"
            self.assertTrue((research_dir / "research_report.md").is_file())
            self.assertTrue((research_dir / "data_sources.md").is_file())
            self.assertTrue((research_dir / "template_search.json").is_file())
            candidate_files = list((research_dir / "template_candidates").glob("*.json"))
            self.assertGreaterEqual(len(candidate_files), 1)

            for path in candidate_files:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["project_id"], report["project_id"])
                self.assertIn("license_type", payload)
                self.assertIn("commercial_delivery_allowed", payload)
                self.assertFalse(payload["commercial_delivery_allowed"])
                self.assertIn(
                    payload["source_site"],
                    {"slidesgo", "slidescarnival", "canva", "envato_elements"},
                )

            plan_sites = {item["source_site"] for item in report["search_plan"]}
            self.assertEqual(
                plan_sites,
                {"slidesgo", "slidescarnival", "canva", "envato_elements"},
            )

            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(status["status"], "RESEARCHING")
            self.assertEqual(status["last_step"], "template_research")

            data_sources = (research_dir / "data_sources.md").read_text(encoding="utf-8")
            self.assertIn("Do not invent statistics", data_sources)
            self.assertFalse((root / "workspace").exists())

            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("RESEARCHED", log_text)

    def test_network_login_wall_is_paused_not_bypassed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Pitch",
                created_on="20261119",
            )
            analyze_requirements(project)

            def fake_get(url: str):
                return (
                    200,
                    url,
                    "<html><body>Please sign in to continue. Log in. Subscribe now. Checkout.</body></html>",
                )

            with mock.patch("aippt.research._http_get", side_effect=fake_get):
                report = research_project(
                    project, query="pitch deck", allow_network=True, max_candidates=8
                )

            self.assertTrue(report["allow_network"])
            blocked = [
                item
                for item in report["candidates"]
                if item.get("discovery") == "network_login_wall"
            ]
            self.assertGreaterEqual(len(blocked), 1)
            self.assertTrue(
                any("login" in (item.get("action") or "").lower() or "Log in" in (item.get("action") or "")
                for item in report["needs_user_action"])
                or any(
                    "login" in str(item.get("needs_user_action") or "").lower()
                    for item in report["candidates"]
                )
            )
            for item in report["candidates"]:
                self.assertIsNot(item.get("commercial_delivery_allowed"), True)


if __name__ == "__main__":
    unittest.main()
