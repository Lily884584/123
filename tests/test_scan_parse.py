"""Phase 2 scan and parse stay inside one project tree."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from aippt.ingest import ingest_project
from aippt.parse import parse_project
from aippt.scaffold import create_project
from aippt.scan import scan_project
from tests.fixtures import write_minimal_fixtures


class ScanParseTest(unittest.TestCase):
    def test_scan_and_parse_project_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Check",
                created_on="20261119",
            )
            info = json.loads(
                (project / "00_project_info" / "project_info.json").read_text(
                    encoding="utf-8"
                )
            )
            project_id = info["project_id"]
            fixtures = write_minimal_fixtures(project / "01_input")
            original_hashes = {
                key: hashlib.sha256(path.read_bytes()).hexdigest()
                for key, path in fixtures.items()
            }
            original_mtimes = {key: path.stat().st_mtime_ns for key, path in fixtures.items()}

            manifest = scan_project(project)
            self.assertEqual(manifest["project_id"], project_id)
            self.assertGreaterEqual(manifest["supported_count"], 8)
            self.assertEqual(len(manifest["duplicate_groups"]), 1)

            by_name = {item["original_filename"]: item for item in manifest["files"]}
            self.assertEqual(by_name["notes.txt"]["parse_status"], "pending")
            self.assertTrue(by_name["notes.txt"]["duplicate"])
            self.assertEqual(by_name["ignore.bin"]["parse_status"], "skipped_unsupported")
            for item in manifest["files"]:
                self.assertEqual(item["project_id"], project_id)

            parsed = parse_project(project, batch_size=1)
            self.assertEqual(parsed["parser"]["parsed_count"], manifest["supported_count"])
            self.assertEqual(parsed["parser"]["failed_count"], 0)

            pdf_item = next(
                item
                for item in parsed["files"]
                if item["original_filename"] == "page.pdf"
            )
            self.assertEqual(pdf_item["parse_status"], "parsed")
            pdf_result = json.loads(
                (project / pdf_item["result_path"] / "content.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(pdf_result["project_id"], project_id)
            self.assertEqual(pdf_result["original_filename"], "page.pdf")
            self.assertEqual(pdf_result["page_count"], 2)
            self.assertEqual(pdf_result["pages"][0]["page"], 1)
            self.assertTrue((project / pdf_item["result_path"] / "pages" / "page-001.png").is_file())

            pptx_item = next(
                item
                for item in parsed["files"]
                if item["original_filename"] == "deck.pptx"
            )
            pptx_result = json.loads(
                (project / pptx_item["result_path"] / "content.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(pptx_result["slides"][0]["page"], 1)
            self.assertIn("Fixture slide", pptx_result["slides"][0]["texts"])
            self.assertIn(pptx_result["render"]["status"], {"available", "missing"})

            image_item = next(
                item
                for item in parsed["files"]
                if item["original_filename"] == "swatch.png"
            )
            image_result = json.loads(
                (project / image_item["result_path"] / "content.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(image_result["width"], 32)
            self.assertEqual(image_result["height"], 24)
            self.assertIsNone(image_result["vision_analysis"])

            # Originals stay bit-for-bit identical.
            for key, path in fixtures.items():
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    original_hashes[key],
                )
                self.assertEqual(path.stat().st_mtime_ns, original_mtimes[key])

            # No shared customer input folder at the fake repo root.
            self.assertFalse((root / "input").exists())
            self.assertFalse((root / "workspace").exists())
            customer_dirs = [
                path for path in root.rglob("customer_files") if path.is_dir()
            ]
            self.assertEqual(customer_dirs, [project / "01_input" / "customer_files"])

            # Extracted outputs stay under this project only.
            for path in (project / "02_extracted_content").rglob("content.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["project_id"], project_id)

    def test_ingest_cli_path_runs_scan_then_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Demo",
                topic="Ingest",
                created_on="20261119",
            )
            write_minimal_fixtures(project / "01_input")
            manifest = ingest_project(project, batch_size=2)
            self.assertTrue((project / "02_extracted_content" / "file_manifest.json").is_file())
            self.assertGreater(manifest["parser"]["parsed_count"], 0)
            log_text = (project / "project.log").read_text(encoding="utf-8")
            self.assertIn("SCANNED", log_text)
            self.assertIn("PARSED", log_text)


if __name__ == "__main__":
    unittest.main()
