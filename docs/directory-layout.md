# Directory layout

Phase 1 maps every global path in [SOP 1.0](sop-1.0-automated-production.md) onto the per-project tree in [SOP 1.1](sop-1.1-client-projects.md) section 1.

`<project>` means `projects/<Client>_<Topic>_<YYYYMMDD>/`. The folder name is the client label, the topic label, and the creation date joined with underscores, for example `Client_A_AI_Business_20261119`.

Per-project folders hold client data. A file that SOP 1.0 placed in `input/`, `workspace/`, or `output/` is written under that client's `<project>` path in the table below. Phase 1 does not create `input/`, `workspace/`, or `output/` at the repository root, so there is no second shared customer input folder beside `01_input/`.

Shared assets live only in `templates/public/`, and only when the template is explicitly public. That directory is empty in Phase 1. Client uploads, reference images, and reference templates stay in the project's `01_input/`.

API keys and passwords stay in environment variables. `project_info.json`, `project_status.json`, `customer_requirements.md`, `project.log`, and the rest of `<project>/` do not store them.

## SOP 1.0 paths

| SOP 1.0 global path | Per-project path |
| --- | --- |
| `input/customer_files/` | `<project>/01_input/customer_files/` |
| `input/reference_images/` | `<project>/01_input/reference_images/` |
| `input/reference_templates/` | `<project>/01_input/reference_templates/` |
| `workspace/extracted_content/` | `<project>/02_extracted_content/` |
| PPTX parse results | `<project>/02_extracted_content/pptx/` |
| PDF parse results | `<project>/02_extracted_content/pdf/` |
| DOCX parse results | `<project>/02_extracted_content/docx/` |
| XLSX parse results | `<project>/02_extracted_content/xlsx/` |
| Image parse results | `<project>/02_extracted_content/images/` |
| `workspace/requirements/requirement_analysis.md` | `<project>/00_project_info/requirement_analysis.md` |
| `workspace/template_candidates/` | `<project>/03_research/template_candidates/` |
| `workspace/design_system/` | `<project>/04_design/design_system/` |
| `workspace/design_system/design_tokens.json` | `<project>/04_design/design_system/design_tokens.json` |
| `workspace/design_system/color_palette.json` | `<project>/04_design/color_palette.json` |
| `workspace/design_system/typography.json` | `<project>/04_design/typography.json` |
| `workspace/design_system/layouts.json` | `<project>/04_design/layouts.json` |
| `workspace/design_system/template_rules.md` | `<project>/04_design/design_system/template_rules.md` |
| `workspace/outlines/ppt_outline.md` | `<project>/05_content/ppt_outline.md` |
| Dual-engine intermediate PPTX (Phase 7) | `<project>/05_content/generated/` (`engine_b.pptx` / `engine_c.pptx`, `generation_report.md`) |
| `output/proposal_A/` | `<project>/06_proposals/proposal_A/` |
| `output/proposal_A/sample.pptx` | `<project>/06_proposals/proposal_A/sample.pptx` |
| `output/proposal_A/preview/` | `<project>/06_proposals/proposal_A/preview/` |
| `output/proposal_A/design_description.md` | `<project>/06_proposals/proposal_A/design_description.md` |
| `output/proposal_B/` | `<project>/06_proposals/proposal_B/` |
| `output/proposal_B/sample.pptx` | `<project>/06_proposals/proposal_B/sample.pptx` |
| `output/proposal_B/preview/` | `<project>/06_proposals/proposal_B/preview/` |
| `output/proposal_B/design_description.md` | `<project>/06_proposals/proposal_B/design_description.md` |
| `output/proposal_C/` | `<project>/06_proposals/proposal_C/` |
| `output/proposal_C/sample.pptx` | `<project>/06_proposals/proposal_C/sample.pptx` |
| `output/proposal_C/preview/` | `<project>/06_proposals/proposal_C/preview/` |
| `output/proposal_C/design_description.md` | `<project>/06_proposals/proposal_C/design_description.md` |
| `output/final/` | `<project>/07_final/` |
| `output/final/final_presentation.pptx` | `<project>/07_final/final_presentation.pptx` |
| `output/final/final_presentation.pdf` | `<project>/07_final/final_presentation.pdf` |
| `output/final/production_report.md` | `<project>/09_reports/production_report.md` |

`00_project_info/` holds requirements because SOP 1.1 keeps the customer brief next to project metadata. `customer_requirements.md` is the brief. `requirement_analysis.md` is the SOP 1.0 analysis, written later into the same folder.

SOP 1.1 lists `color_palette.json`, `typography.json`, and `layouts.json` beside `04_design/design_system/`, so those three files use that location. `design_tokens.json` and `template_rules.md` stay inside `design_system/`.

`production_report.md` lives in `09_reports/` with the other project reports.

Parse results keep the original filename, source, and page information inside the format folder for that project.

## SOP 1.1 paths with no SOP 1.0 global folder

These paths exist only on the per-project tree:

| Path | Role |
| --- | --- |
| `<project>/00_project_info/project_info.json` | Client, topic, project id, dates, owner, status, special requirements |
| `<project>/00_project_info/customer_requirements.md` | Customer brief |
| `<project>/00_project_info/project_status.json` | Status and the timestamped history |
| `<project>/03_research/research_report.md` | Research notes |
| `<project>/03_research/data_sources.md` | Source list for research data |
| `<project>/05_content/slide_content/` | Per-slide content written with the outline |
| `<project>/08_versions/v001/` | First archived version |
| `<project>/08_versions/v002/` | Next archived version |
| `<project>/08_versions/v003/` | Next archived version |
| `<project>/09_reports/quality_report.md` | Quality check report |
| `<project>/09_reports/revision_history.md` | Revision history |
| `<project>/project.log` | Project log |

Later version numbers continue as `v004` and upward under `08_versions/`. A confirmed version keeps its PPTX, PDF, notes, and check results. Phase 1 creates the `v001`, `v002`, and `v003` directories empty.

## What the scaffold creates

`aippt/scaffold.py` copies `aippt/project_tree/` into `projects/<Client>_<Topic>_<YYYYMMDD>/`. Every directory in the SOP 1.1 section 1 tree is in that template, with an empty `.gitkeep` so Git can store it. The command also writes:

- `project.log`, with one `CREATED` line
- `00_project_info/project_info.json`
- `00_project_info/project_status.json` with status `CREATED`
- `00_project_info/customer_requirements.md`

`project_info.json` records the project id, client, project name, topic, creation time, optional due date, optional owner, status, and optional special requirements. The project id is a new UUID. Deliverable filenames in the mapping table, including proposal `preview/` folders, parse results, research notes, design JSON, outlines, sample decks, and final PPTX and PDF files, are written by later phases. Phase 1 ships the directories, the creation records, and `project.log`, with no sample client and no customer files.

`projects/.gitkeep` keeps the projects root in Git before any client exists. `templates/public/.gitkeep` marks the only shared asset directory.
