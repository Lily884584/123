# 123

This heading was the original stub: the repository used to contain only this line.

AI PPT Studio, Phase 1. Production rules and the per-project directory map are in the SOP docs. Each client gets one folder, `projects/<Client>_<Topic>_<YYYYMMDD>/`, from `00_project_info` through `09_reports`. Shared assets live only in `templates/public/`, and only when a template is explicitly public.

- [SOP 1.0, automated production](docs/sop-1.0-automated-production.md)
- [SOP 1.1, client projects](docs/sop-1.1-client-projects.md)
- [Directory layout](docs/directory-layout.md)
- [PPT order handbook](docs/ppt-order-handbook.md)

Create a project directory:

```bash
python -m aippt.scaffold --client <Client> --topic <Topic>
```

Run the scaffold test:

```bash
python -m unittest discover -s tests -t . -v
```
