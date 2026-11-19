# 123

This heading was the original stub: the repository used to contain only this line.

AI PPT Studio. Production rules and the per-project directory map are in the SOP docs. Each client gets one folder, `projects/<Client>_<Topic>_<YYYYMMDD>/`, from `00_project_info` through `09_reports`. Shared assets live only in `templates/public/`, and only when a template is explicitly public.

- [SOP 1.0, automated production](docs/sop-1.0-automated-production.md)
- [SOP 1.1, client projects](docs/sop-1.1-client-projects.md)
- [Directory layout](docs/directory-layout.md)
- [PPT order handbook](docs/ppt-order-handbook.md)

Create a project directory:

```bash
python -m aippt.scaffold --client <Client> --topic <Topic>
```

Put files in that project's `01_input/` folders, then scan and parse:

```bash
python -m aippt.ingest --project projects/<Client>_<Topic>_<YYYYMMDD>
```

Or run the stages alone:

```bash
python -m aippt.scan --project projects/<Client>_<Topic>_<YYYYMMDD>
python -m aippt.parse --project projects/<Client>_<Topic>_<YYYYMMDD>
python -m aippt.requirements --project projects/<Client>_<Topic>_<YYYYMMDD>
```

Requirement analysis writes `00_project_info/requirement_analysis.md`. It runs offline by default. Optional model calls use `AIPPT_MODEL_BASE_URL`, `AIPPT_MODEL_API_KEY`, and `AIPPT_MODEL_NAME`.

Install parser dependencies with `pip install -r requirements.txt`.

Run tests:

```bash
python -m unittest discover -s tests -t . -v
```
