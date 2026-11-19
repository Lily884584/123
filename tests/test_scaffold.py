"""The Phase 1 scaffold creates one isolated project tree."""

import json
import tempfile
import unittest
from pathlib import Path

from aippt.scaffold import create_project

# SOP 1.1 section 1, every directory under the project folder.
EXPECTED_DIRECTORIES = {
    "00_project_info",
    "01_input",
    "01_input/customer_files",
    "01_input/reference_images",
    "01_input/reference_templates",
    "02_extracted_content",
    "02_extracted_content/pptx",
    "02_extracted_content/pdf",
    "02_extracted_content/docx",
    "02_extracted_content/xlsx",
    "02_extracted_content/images",
    "03_research",
    "03_research/template_candidates",
    "04_design",
    "04_design/design_system",
    "05_content",
    "05_content/slide_content",
    "06_proposals",
    "06_proposals/proposal_A",
    "06_proposals/proposal_B",
    "06_proposals/proposal_C",
    "07_final",
    "08_versions",
    "08_versions/v001",
    "08_versions/v002",
    "08_versions/v003",
    "09_reports",
}

CREATED_FILES = {
    "project.log",
    "00_project_info/project_info.json",
    "00_project_info/project_status.json",
    "00_project_info/customer_requirements.md",
}


class ScaffoldTest(unittest.TestCase):
    def test_creates_project_tree_without_shared_customer_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                root,
                client="Client",
                topic="Topic",
                created_on="20261119",
            )

            self.assertEqual(project, root / "projects" / "Client_Topic_20261119")
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["projects"])
            self.assertEqual(
                sorted(path.name for path in (root / "projects").iterdir()),
                ["Client_Topic_20261119"],
            )

            found_dirs = {
                path.relative_to(project).as_posix()
                for path in project.rglob("*")
                if path.is_dir()
            }
            self.assertEqual(found_dirs, EXPECTED_DIRECTORIES)

            found_files = {
                path.relative_to(project).as_posix()
                for path in project.rglob("*")
                if path.is_file()
            }
            gitkeeps = {f"{directory}/.gitkeep" for directory in EXPECTED_DIRECTORIES}
            self.assertEqual(found_files, gitkeeps | CREATED_FILES)
            for relative in gitkeeps:
                self.assertEqual((project / relative).read_bytes(), b"")

            self.assertFalse((root / "input").exists())
            self.assertFalse((root / "input" / "customer_files").exists())
            self.assertFalse((root / "workspace").exists())
            self.assertFalse((root / "output").exists())
            customer_dirs = [path for path in root.rglob("customer_files") if path.is_dir()]
            self.assertEqual(customer_dirs, [project / "01_input" / "customer_files"])

            log_text = (project / "project.log").read_text(encoding="utf-8")
            info = json.loads(
                (project / "00_project_info" / "project_info.json").read_text(
                    encoding="utf-8"
                )
            )
            status = json.loads(
                (project / "00_project_info" / "project_status.json").read_text(
                    encoding="utf-8"
                )
            )
            brief = (project / "00_project_info" / "customer_requirements.md").read_text(
                encoding="utf-8"
            )

            self.assertEqual(info["client"], "Client")
            self.assertEqual(info["topic"], "Topic")
            self.assertEqual(info["created_on"], "20261119")
            self.assertEqual(info["status"], "CREATED")
            self.assertEqual(info["project_name"], "Client_Topic_20261119")
            self.assertTrue(info["project_id"])
            self.assertEqual(status["project_id"], info["project_id"])
            self.assertEqual(status["status"], "CREATED")
            self.assertEqual(status["history"], [{"status": "CREATED", "at": info["created_at"]}])
            self.assertEqual(
                log_text,
                f"{info['created_at']} CREATED project_id={info['project_id']} "
                f"directory=Client_Topic_20261119\n",
            )
            self.assertEqual(brief, "# Customer requirements\n")
            for banned in ("api_key", "password", "secret", "token"):
                self.assertNotIn(banned, info)
                self.assertNotIn(banned, status)

            for path in project.rglob("*"):
                self.assertNotIn(
                    path.suffix.lower(),
                    {".pptx", ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"},
                )


if __name__ == "__main__":
    unittest.main()
