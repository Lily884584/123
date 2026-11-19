# AIPPT 流水线 Session Handoff

- written_at: `2026-11-19 13:13`（Asia/Shanghai）
- repo: `Lily884584/123`
- tip_branch: `cursor/phase-6-ppt-outline-29ae`
- tip_commit: `66471ea`
- worker: `bc-0a4afeb3-0fdc-51b2-8e8f-7aed77a529ae`
- project_store: `/cursor/stores/bc-28121e62-915d-493d-8222-11c571411c9f`

上下文将满，下一会话请先读本文件，再继续 **Phase 7**。

## 当前状态（一句话）

AI PPT Studio 已完成 Phase 1–6（目录/扫描解析/需求分析/模板研究/设计系统/大纲），代码在 stacked PRs 上；**下一步是 Phase 7：B/C 双引擎 PPT 生成**。尚未做样稿三套、质检、用户确认、最终交付。

## 已完成 Phase

| Phase | 内容 | 分支 | PR |
| --- | --- | --- | --- |
| 1 | SOP + 项目目录脚手架 | `cursor/phase-1-sop-project-dirs-29ae` | https://github.com/Lily884584/123/pull/1 → `main` |
| 2 | 本地文件扫描与解析 | `cursor/phase-2-file-scan-parse-29ae` | https://github.com/Lily884584/123/pull/2 → Phase1 |
| 3 | 客户需求分析 | `cursor/phase-3-requirement-analysis-29ae` | https://github.com/Lily884584/123/pull/4 → Phase2 |
| 4 | 模板搜索与授权记录 | `cursor/phase-4-template-research-29ae` | https://github.com/Lily884584/123/pull/5 → Phase3 |
| 5 | PPTX 模板解析与设计分析 | `cursor/phase-5-template-design-29ae` | https://github.com/Lily884584/123/pull/6 → Phase4 |
| 6 | PPT 大纲与页面内容 | `cursor/phase-6-ppt-outline-29ae` | https://github.com/Lily884584/123/pull/7 → Phase5 |

Stack 顺序（底→顶）：`#1 → #2 → #4 → #5 → #6 → #7`（无 #3）。

用户侧 Phase1 目录验收已通过（`projects/Demo_Check_20261119`）。Phase2 起多为代码+单测验收；PRs 仍多为 open，合并时需自下而上 restack。

## 待办 Phase（按 SOP 1.0）

### 下一步：Phase 7 — B/C 双引擎 PPT 生成

依据 `/cursor/stores/self/docs/sop-1.0-automated-production.md` 第八节：

- **ENGINE B**：模板智能填充（有合适且授权允许的 PPTX 时）
- **ENGINE C**：设计语言提取后重新设计（模板不适合直接填，或需要更自由版式）
- 输入：`05_content/` 大纲 + `04_design/` Design System +（B）本地/已授权模板
- 输出：可编辑页面/中间 PPTX（完整三套样稿属于 Phase 8）
- 约束：保留可编辑元素优先；不得把参考图直接当整页背景；**未授权模板不得进入商业交付**

建议实现落点：

- 新分支从 `cursor/phase-6-ppt-outline-29ae` 拉出：`cursor/phase-7-...-29ae`
- 新 PR base = Phase6 分支，`stack_on: 7`
- 模块建议：`aippt/engine_b.py` / `aippt/engine_c.py` 或 `aippt/generate.py`
- 测试用合成 PPTX/大纲 fixture，不写真实客户文件

### 更后面

| Phase | 内容 |
| --- | --- |
| 8 | 三套样稿 → `06_proposals/proposal_{A,B,C}/` |
| 9 | 自动质量检查 |
| 10 | 用户选择 + 最终 PPT → `07_final/` |

## 关键约束（下一会话必须遵守）

1. **只做当前 Phase**，不要一次做完后面所有阶段。
2. **每客户一目录**：`projects/<Client>_<Topic>_<YYYYMMDD>/`；禁止仓库根共享 `input/customer_files/`。
3. **原始客户文件只读**：永不删除/覆盖 `01_input/`。
4. **密钥不进项目目录**：API Key/密码只用环境变量（如 `AIPPT_MODEL_*`）。
5. **不编造事实/数据/案例/引用**；缺证据写「待补」。
6. **大文件分批**；不要把全部文件内容一次性塞进模型上下文。
7. **模板授权**：未核实 license 的候选 `commercial_delivery_allowed=false`；不绕过登录/付费/反爬。
8. **大纲不灌水**：禁止为凑页数制造无意义页（Phase6 已校验 `padding_pages=0`）。
9. **Git**：新工作从上一 Phase 分支拉出；PR base 为上一 Phase 分支；**不要把后续 Phase 提交推进已有父 PR**。
10. **分支名**：`cursor/<descriptive-name>-29ae`。
11. **手册**：接单审美/样稿门禁见 `docs/ppt-order-handbook.md`（与自动化 SOP 并存；自动化 Phase 仍按 1.0/1.1）。

## 关键命令

```bash
pip install -r requirements.txt
python -m aippt.scaffold --client <Client> --topic <Topic>
python -m aippt.ingest --project projects/<Client>_<Topic>_<YYYYMMDD>
python -m aippt.requirements --project projects/<...>
python -m aippt.research --project projects/<...>          # 可选 --network
python -m aippt.design --project projects/<...>            # 需本地 PPTX 模板
python -m aippt.outline --project projects/<...>
python -m unittest discover -s tests -t . -v               # 当前 tip：11 tests OK
```

可选模型：`AIPPT_MODEL_BASE_URL` / `AIPPT_MODEL_API_KEY` / `AIPPT_MODEL_NAME`。

## 关键文件路径

### 规格与手册（Context + 仓库均有副本）

| 路径 | 用途 |
| --- | --- |
| `/cursor/stores/self/docs/sop-1.0-automated-production.md` | 自动化生产 SOP |
| `/cursor/stores/self/docs/sop-1.1-client-projects.md` | 客户项目/隔离 SOP |
| `/cursor/stores/self/docs/00_project_info/session_handoff.md` | **本 handoff（Context）** |
| `/agent/repos/123/docs/sop-1.0-automated-production.md` | 仓库内 SOP 1.0 |
| `/agent/repos/123/docs/sop-1.1-client-projects.md` | 仓库内 SOP 1.1 |
| `/agent/repos/123/docs/directory-layout.md` | 全局路径 → 每项目路径映射 |
| `/agent/repos/123/docs/ppt-order-handbook.md` | 接单制作手册 |
| `/agent/repos/123/docs/00_project_info/session_handoff.md` | 本 handoff（仓库副本） |

### 代码模块（`/agent/repos/123/aippt/`）

| 文件 | Phase |
| --- | --- |
| `scaffold.py` | 1 建项目树 |
| `scan.py` / `parse.py` / `ingest.py` / `formats.py` / `paths.py` | 2 扫描解析 |
| `requirements.py` / `model.py` | 3 需求分析 |
| `research.py` / `data/public_template_catalog.json` | 4 模板研究 |
| `design.py` | 5 设计系统 |
| `outline.py` | 6 大纲 |
| `project_tree/` | 1 空目录模板 + `.gitkeep` |

### 每项目目录（SOP 1.1）

```
projects/<Client>_<Topic>_<YYYYMMDD>/
  00_project_info/     project_info.json, project_status.json,
                       customer_requirements.md,
                       requirement_analysis.md/.json   (Phase3)
  01_input/            customer_files/, reference_images/, reference_templates/
  02_extracted_content/ file_manifest.json + per-file results (Phase2)
  03_research/         template_candidates/, research_report.md, data_sources.md (Phase4)
  04_design/           design_system/, color_palette.json, typography.json, layouts.json (Phase5)
  05_content/          ppt_outline.md/.json, slide_content/page-NNN.md (Phase6)
  06_proposals/        Phase8
  07_final/            Phase10
  08_versions/
  09_reports/
  project.log
```

共享模板仅允许：`/agent/repos/123/templates/public/`（明确公开模板）。

### 测试

| 路径 | 覆盖 |
| --- | --- |
| `/agent/repos/123/tests/test_scaffold.py` | Phase1 |
| `/agent/repos/123/tests/test_scan_parse.py` | Phase2 |
| `/agent/repos/123/tests/test_requirements.py` | Phase3 |
| `/agent/repos/123/tests/test_research.py` | Phase4 |
| `/agent/repos/123/tests/test_design.py` | Phase5 |
| `/agent/repos/123/tests/test_outline.py` | Phase6 |
| `/agent/repos/123/tests/fixtures.py` | 合成夹具（非真实客户） |

## 给下一会话的启动提示

1. 读本 handoff + SOP 1.0 第八节（双引擎）。
2. `git fetch` 并 checkout `cursor/phase-6-ppt-outline-29ae`。
3. 拉 `cursor/phase-7-*-29ae`，只实现 Engine B/C；开 PR base=Phase6、`stack_on=7`。
4. 跑全量 `python -m unittest discover -s tests -t . -v`，勿破坏既有测试。
5. 不要把 Phase7 提交推到 #7 或更早 PR。
