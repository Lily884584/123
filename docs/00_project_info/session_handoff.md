# AIPPT 流水线 Session Handoff

- written_at: `2026-11-19`（续 Phase 7 完成后）
- repo: `Lily884584/123`
- tip_branch: `cursor/phase-7-dual-engine-039d`
- worker: `bc-ea468fd9-cfe0-5cf5-9f1f-889ac87e039d`
- project_store: `/cursor/stores/bc-28121e62-915d-493d-8222-11c571411c9f`

上下文将满或新会话时，请先读本文件，再继续 **Phase 8**。

## 当前状态（一句话）

AI PPT Studio 已完成 Phase 1–7（含 B/C 双引擎中间稿生成）；**下一步是 Phase 8：三套样稿 → `06_proposals/proposal_{A,B,C}/`**。尚未做质检、用户确认、最终交付。

## 已完成 Phase

| Phase | 内容 | 分支 | PR |
| --- | --- | --- | --- |
| 1 | SOP + 项目目录脚手架 | `cursor/phase-1-sop-project-dirs-29ae` | https://github.com/Lily884584/123/pull/1 → `main` |
| 2 | 本地文件扫描与解析 | `cursor/phase-2-file-scan-parse-29ae` | https://github.com/Lily884584/123/pull/2 → Phase1 |
| 3 | 客户需求分析 | `cursor/phase-3-requirement-analysis-29ae` | https://github.com/Lily884584/123/pull/4 → Phase2 |
| 4 | 模板搜索与授权记录 | `cursor/phase-4-template-research-29ae` | https://github.com/Lily884584/123/pull/5 → Phase3 |
| 5 | PPTX 模板解析与设计分析 | `cursor/phase-5-template-design-29ae` | https://github.com/Lily884584/123/pull/6 → Phase4 |
| 6 | PPT 大纲与页面内容 | `cursor/phase-6-ppt-outline-29ae` | https://github.com/Lily884584/123/pull/7 → Phase5 |
| 7 | B/C 双引擎 PPT 生成 | `cursor/phase-7-dual-engine-039d` | https://github.com/Lily884584/123/pull/8 → Phase6 |

Stack 顺序（底→顶）：`#1 → #2 → #4 → #5 → #6 → #7 → #8`。

## 待办 Phase（按 SOP 1.0）

### 下一步：Phase 8 — 三套样稿

- 方案 A/B/C（高端极简 / 商业咨询 / 科技创意，可按需求调整定位）
- 每套 3–5 页，相同核心内容；含封面、目录/章节、内容分析、数据图表、总结
- 输出：`06_proposals/proposal_{A,B,C}/` → `sample.pptx` + `preview/` + `design_description.md`
- 新分支从 `cursor/phase-7-dual-engine-039d` 拉出；PR base = Phase7 分支

### 更后面

| Phase | 内容 |
| --- | --- |
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
8. **大纲不灌水**：禁止为凑页数制造无意义页。
9. **Git**：新工作从上一 Phase 分支拉出；PR base 为上一 Phase 分支；**不要把后续 Phase 提交推进已有父 PR**。
10. **分支名**：本 worker 使用 `cursor/<descriptive-name>-039d`（与 cloud agent 后缀一致）。
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
python -m aippt.generate --project projects/<...>          # 可选 --engine auto|b|c
python -m unittest discover -s tests -t . -v               # tip：14 tests OK
```

可选模型：`AIPPT_MODEL_BASE_URL` / `AIPPT_MODEL_API_KEY` / `AIPPT_MODEL_NAME`。

## 关键文件路径

### 规格与手册

| 路径 | 用途 |
| --- | --- |
| `/cursor/stores/self/docs/sop-1.0-automated-production.md` | 自动化生产 SOP |
| `/cursor/stores/self/docs/sop-1.1-client-projects.md` | 客户项目/隔离 SOP |
| `/cursor/stores/self/docs/00_project_info/session_handoff.md` | **本 handoff（Context）** |
| `/agent/repos/123/docs/sop-1.0-automated-production.md` | 仓库内 SOP 1.0 |
| `/agent/repos/123/docs/directory-layout.md` | 全局路径 → 每项目路径映射 |

### 代码模块（`/agent/repos/123/aippt/`）

| 文件 | Phase |
| --- | --- |
| `scaffold.py` | 1 |
| `scan.py` / `parse.py` / `ingest.py` / `formats.py` / `paths.py` | 2 |
| `requirements.py` / `model.py` | 3 |
| `research.py` / `data/public_template_catalog.json` | 4 |
| `design.py` | 5 |
| `outline.py` | 6 |
| `generate.py` / `engine_b.py` / `engine_c.py` | 7 |
| `project_tree/` | 1 |

### Phase 7 输出

```
<project>/05_content/generated/
  engine_b.pptx | engine_c.pptx
  generation.json
  generation_report.md
```

## 给下一会话的启动提示

1. 读本 handoff + SOP 1.0 第九节（三套样稿）。
2. `git fetch` 并 checkout `cursor/phase-7-dual-engine-039d`。
3. 拉 Phase 8 分支，只实现 `06_proposals/proposal_{A,B,C}/`；PR base=Phase7。
4. 跑全量 `python -m unittest discover -s tests -t . -v`，勿破坏既有测试。
5. 不要把 Phase8 提交推到 Phase7 或更早 PR。
