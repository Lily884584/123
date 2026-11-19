# AI PPT Studio

客户项目管理与版本管理模块

版本：1.1

本模块正式加入 AI PPT Studio 核心系统，加在 SOP 1.0 之上。

## 目标

建立完整的客户项目管理机制，实现客户项目独立、资料隔离、制作过程记录、样稿管理、版本管理和最终文件归档。

用户只需要创建客户项目、上传资料、输入需求，系统自动管理后续所有文件和制作流程。

## 一、客户项目管理

每个客户必须建立一个独立项目。

项目命名规则：客户名称_项目主题_创建日期

例如：Client_A_AI_Business_20261119

每个项目必须拥有独立的工作目录。

目录结构：

```
projects/
└── Client_A_AI_Business_20261119/
    ├── 00_project_info/
    │   ├── project_info.json
    │   ├── customer_requirements.md
    │   └── project_status.json
    ├── 01_input/
    │   ├── customer_files/
    │   ├── reference_images/
    │   └── reference_templates/
    ├── 02_extracted_content/
    │   ├── pptx/
    │   ├── pdf/
    │   ├── docx/
    │   ├── xlsx/
    │   └── images/
    ├── 03_research/
    │   ├── research_report.md
    │   ├── data_sources.md
    │   └── template_candidates/
    ├── 04_design/
    │   ├── design_system/
    │   ├── color_palette.json
    │   ├── typography.json
    │   └── layouts.json
    ├── 05_content/
    │   ├── ppt_outline.md
    │   └── slide_content/
    ├── 06_proposals/
    │   ├── proposal_A/
    │   ├── proposal_B/
    │   └── proposal_C/
    ├── 07_final/
    │   ├── final_presentation.pptx
    │   └── final_presentation.pdf
    ├── 08_versions/
    │   ├── v001/
    │   ├── v002/
    │   └── v003/
    ├── 09_reports/
    │   ├── production_report.md
    │   ├── quality_report.md
    │   └── revision_history.md
    └── project.log
```

SOP 1.0 里的全局路径映射到上述目录：input 对应 01_input，extracted_content 对应 02_extracted_content，研究与模板候选对应 03_research，design_system 对应 04_design，大纲对应 05_content，三套样稿对应 06_proposals，最终文件对应 07_final。

## 二、项目创建功能

系统必须支持创建新客户项目。

创建时记录：

1. 客户名称或客户代号。
2. 项目名称。
3. PPT 主题。
4. 创建时间。
5. 预计完成时间（可选）。
6. 项目负责人（可选）。
7. 项目状态。
8. 客户特殊要求。

每个项目自动生成唯一 project_id。

如果客户没有提供名称，可以使用客户编号。

禁止不同客户项目共用临时文件夹。

## 三、客户资料管理

用户可以将以下资料放入项目输入目录：PPTX、PDF、DOCX、XLSX、PNG、JPG、TXT、MD。

系统自动：

1. 扫描文件。
2. 识别格式。
3. 记录文件大小。
4. 计算文件哈希值。
5. 检查重复文件。
6. 建立文件清单。
7. 记录解析状态。

原始文件必须保持只读。不得擅自删除或覆盖客户原始文件。新上传的文件必须关联到正确的 project_id。

## 四、项目状态管理

每个项目使用以下状态：

- CREATED：项目已创建。
- FILES_RECEIVED：客户资料已接收。
- ANALYZING：正在解析客户资料。
- RESEARCHING：正在搜索资料和模板。
- DESIGNING：正在制定设计方案。
- OUTLINE_READY：PPT 大纲已完成。
- SAMPLE_GENERATING：正在生成三套样稿。
- WAITING_APPROVAL：等待用户选择样稿。
- PRODUCING：正在生成完整 PPT。
- QUALITY_CHECK：正在进行质量检查。
- REVISION：正在修改。
- COMPLETED：项目已完成。
- ARCHIVED：项目已归档。

所有状态变化必须自动记录时间。发生错误时记录错误原因，不得直接跳过失败步骤。

## 五、版本管理

必须支持完整的版本管理。

版本命名：v001、v002、v003。

每次重要修改都必须建立新版本。

例如：

- v001：第一版完整 PPT。
- v002：修改封面和目录。
- v003：修改数据图表及页面布局。

每个版本必须保存：

1. PPTX 文件。
2. PDF 预览。
3. 版本说明。
4. 修改内容。
5. 创建时间。
6. 使用的 Design System 版本。
7. 质量检查结果。

禁止覆盖已经确认的历史版本。默认保留所有正式版本。

对于临时文件和重复渲染文件，可以按照清理规则管理，但不得自动删除客户原始资料和正式交付版本。

## 六、样稿管理

每个客户项目必须支持三套独立样稿。

- proposal_A：设计方案 A。
- proposal_B：设计方案 B。
- proposal_C：设计方案 C。

每套方案必须独立保存：

- PPTX 样稿。
- PDF 预览。
- 页面预览图片。
- 设计说明。
- 模板来源。
- 素材授权记录。
- 质量检查报告。

用户选择方案后：记录用户选择的方案。将该方案的 Design System 设为正式制作基准。其他方案继续保留，方便后续参考。

## 七、客户修改与反馈管理

系统必须支持用户对 PPT 提出修改要求。例如：修改封面、修改字体、修改配色、修改某几页内容、增加页面、删除页面、替换图片、调整图表、更换设计风格。

AI 必须识别修改涉及的页面和模块。只修改必要部分。不得因为修改一页而无故重做整套 PPT。

每次正式修改生成新版本。修改前记录原始版本。

## 八、项目独立性与资料隔离

这是强制要求。

1. 不同客户之间禁止共享客户原始资料。
2. 每个项目使用独立工作目录。
3. 文件解析结果必须绑定 project_id。
4. 样稿必须绑定 project_id。
5. 最终 PPT 必须绑定 project_id。
6. 修改记录必须绑定 project_id。
7. 禁止将其他客户的资料混入当前 PPT。
8. 共享模板只能使用明确允许共享的公共模板资源。
9. API Key 和密码不得保存在客户项目目录中。

## 九、项目归档

项目完成后自动生成归档报告。

归档内容：项目需求、原始客户资料清单、模板来源、授权记录、最终 PPTX、最终 PDF、版本历史、质量检查报告、修改记录。

项目状态变为 COMPLETED。用户确认归档后变为 ARCHIVED。不得自动删除已归档项目。

## 十、用户使用流程

1. 创建客户项目。
2. 上传客户资料。
3. 输入 PPT 制作需求。
4. AI 自动分析客户资料。
5. AI 搜索模板和素材。
6. AI 生成三套设计样稿。
7. 用户选择样稿。
8. AI 生成完整 PPT。
9. AI 自动检查和优化。
10. 用户提出修改意见。
11. AI 创建新版本。
12. 用户确认最终交付。
13. 项目归档。

## 十一、开发要求

在原有 SOP 1.0 基础上增加本模块。

1. 不得破坏现有功能。
2. 不得重复创建已有模块。
3. 优先使用现有技术栈。
4. 每个项目使用独立目录。
5. 使用 project_id 管理项目。
6. 使用 JSON 或 SQLite 保存项目状态。建议优先使用 SQLite 管理项目元数据、状态和版本索引。文件本身仍保存在独立项目目录中。
7. 建立自动版本管理。
8. 建立项目日志。
9. 增加项目恢复机制。
10. 增加自动化测试。

先实现基础项目管理和文件隔离，再逐步接入完整 PPT 自动化工作流。

## 最终目标

用户只需要上传客户文件、告诉系统制作需求。

系统自动完成项目创建、资料分析、模板搜索、样稿制作、完整 PPT 生成、版本管理和最终归档。
