# 开发流程

## 1. 文档目的

本文定义 Vet Research Manuscript Lab 从空项目到可验收 MVP 的实施流程。
首发范围固定为：

- 犬猫回顾性观察性临床研究；
- STROBE-Vet 报告规范；
- CSV/Excel 病例表、Zotero 文献库和少量 PDF；
- SQLite 单机版本；
- Streamlit 前端；
- Quarto/Pandoc 导出 DOCX；
- 统计模块先接模拟 runner，再接隔离的 R/Python runner。

开发期间必须遵守 `AGENT.md`、`domain_model.md` 和
`agent_contracts.md`。如果实现与这些文档冲突，应先记录架构决策并更新文档，
不能在代码里静默改变约束。

## 2. 总体开发策略

采用“纵向切片优先”的增量开发方式。每个切片必须同时覆盖：

```text
领域模型 -> 持久化 -> LangGraph 节点/路由 -> Policy 校验
         -> Streamlit 最小界面 -> 自动化测试 -> 审计记录
```

不能先写完全部 Agent 再补审批、版本和审计。这些能力属于系统主路径，必须从
第一个可运行切片开始存在。

实现顺序遵循以下原则：

1. 先确定 schema 和状态转换，再实现模型提示词。
2. 先使用确定性 stub/mock 跑通流程，再接外部服务和 LLM。
3. 先实现审批、锁定和不可变版本，再处理复杂检索与统计。
4. 每个 Agent 先实现输入/输出验证器，再实现生成逻辑。
5. 每个阶段结束必须形成可演示、可回归、可中断恢复的版本。

## 3. 开发环境与项目结构

计划采用以下目录：

```text
src/vet_manuscript_lab/
  domain/
    models/          # 领域实体和枚举
    policies/        # 审批、锁定、证据和转换规则
    schemas/         # Agent 输入输出 schema
  workflow/
    graph.py         # LangGraph 构建入口
    state.py         # WorkflowState
    routing.py       # 纯函数路由
    nodes/           # 薄节点，只负责编排
  services/
    zotero/
    retrieval/
    documents/
    analysis/
    export/
  infrastructure/
    database/
    artifacts/
    checkpoints/
    model_gateway/
  ui/
    app.py
    pages/
    presenters/
tests/
  unit/
  integration/
  e2e/
  adversarial/
fixtures/
  golden_project/
artifacts/           # 本地运行产物，不提交 Git
```

初始工程配置应包括：

- `pyproject.toml`：Python 版本、依赖、测试和静态检查配置；
- `.env.example`：仅列变量名和说明，不包含密钥；
- `.gitignore`：忽略密钥、数据库、索引、缓存和运行产物；
- Alembic：数据库迁移；
- pytest：单元、集成和端到端测试；
- Ruff 或同类工具：格式、lint 和 import 检查；
- mypy/pyright：核心 domain、policy、workflow 模块类型检查。

## 4. 阶段化实施流程

### 阶段 0：工程基线与决策冻结 ✅

目标：把讨论结论转成可执行的工程边界。

状态：**已完成。** Python 3.12 + src layout、pyproject.toml、Alembic、Ruff、
mypy、pytest 均已配置；ADR-0001 至 ADR-0005 已建立；golden project fixture
已就位。

任务：

1. 确认 Python 最低版本和依赖管理方式。
2. 建立目录、配置、测试入口和本地运行命令。
3. 将 `workflow_state_schema.py` 移入正式包并补充测试。
4. 建立 ADR（Architecture Decision Record）目录。
5. 定义 ID、UTC 时间、hash、错误码和 artifact 类型规范。
6. 建立不含真实病例或隐私信息的 golden project fixture。

交付物：可安装的空包、测试基线、CI 基线、ADR-0001 至 ADR-005。

退出门槛：

- 新环境可以通过一条命令安装并运行测试；
- schema 可导入且状态可 JSON 序列化；
- 非法主流程转换被拒绝；
- 仓库中不存在密钥或真实病例数据。

### 阶段 1：Foundation 纵向切片 ✅

目标：不依赖真实 LLM 和外部 API，跑通项目创建、审批、锁定和恢复。

状态：**已完成。** Foundation graph 从 Project Init 运行到 Protocol Lock，
支持 interrupt/resume、版本化 artifact、审批与锁定策略、checkpoint 恢复。
迁移 0001_foundation 已就位。

任务：

1. 实现 `Project`、`WorkflowRun`、`Artifact/ArtifactVersion`、`Approval`、
   `Lock`、`AuditEvent` 的数据库模型。
2. 实现本地 artifact store：内容寻址、原子写入、hash 校验、不可变版本。
3. 实现 Policy 层：审批前置、锁定、版本过期、角色校验。
4. 构建 LangGraph mock 主链：Project Init 到 Protocol Lock。
5. 使用 `interrupt()` 实现问题审批与方案审批。
6. 建立 Streamlit 项目页、运行状态页、审批页和 artifact 预览页。
7. 测试关闭进程后从 checkpoint 恢复。

退出门槛：

- 任意审批点可以中断并恢复；
- 拒绝和“要求修改”会产生新版本，不覆盖旧版本；
- 未批准 artifact 无法进入下游节点；
- locked protocol 的任何原地修改都会失败并写入审计日志。

### 阶段 2：文献与证据纵向切片

目标：实现从 Zotero 条目到可定位 EvidenceItem 的完整证据链。

状态：**文献与证据纵向切片（mock）已就绪，外部集成开发中。**

已完成的准备（ADR-0005、迁移 0002_literature_evidence）：

- `literature_records`、`attachment_versions`、`source_spans`、`evidence_items`、
  `screening_decisions`、`provenance_links` 六张关系表；
- DOI/PMID 项目内去重唯一约束；
- `LiteratureRepository` 事务仓库（CRUD + 去重 + 筛选计数 + 溯源链接）；
- `domain/policies/evidence.py` 策略层（源跨度前置、检索审批前置、筛选完成
  前置、引用去重）；
- `WorkflowState` 扩展 `LiteratureSummary` 和 `EvidenceSummary` 引用字段；
- `ArtifactType` 补充 `SCREENING_RESULT`、`LITERATURE_BATCH`、
  `DATASET_DICTIONARY`、`REVIEWER_CRITIQUE`、`GUIDELINE_CHECKLIST`、
  `CITATION_AUDIT`、`AI_USAGE_LOG` 七个类型；
- 20 个新增测试覆盖仓库操作与策略不变量。

待实现任务：

1. 实现 Zotero API v3 只读同步和增量版本记录。
2. 实现 PDF 附件导入、hash、解析状态和失败重试。
3. 实现文本分块元数据；保留页码、章节、字符位置和附件版本。
4. 接入 LlamaIndex 混合检索与 rerank，但只输出候选 chunk。
5. ✅ 实现 `SourceSpan`、`EvidenceItem` 和 screening decision 的 LangGraph
   节点（mock 确定性版本，基于已就绪的数据库表和策略层）。
6. ✅ 实现搜索策略审批、纳排原因和冲突人工处理（mock 版本，
   含 species-scope 纳排逻辑和审批拒绝回退）。
7. ✅ 实现第一版 citation/evidence audit（source-span 关联校验、
   hash 校验、adversarial citation 检查）。
8. ✅ 扩展 Foundation graph 到 `LITERATURE_SEARCH` → `EVIDENCE_AUDIT` 阶段
   （`build_evidence_pipeline_graph`，全流程可中断恢复）。

MVP 限制：复杂表格、扫描件、无法可靠定位页码的内容必须标记
`needs_human_review`，不承诺自动提取。

退出门槛：

- EvidenceItem 必须至少关联一个有效 SourceSpan；
- SourceSpan 能回到 Zotero item、具体附件版本和 PDF 位置；
- top-k 检索结果不能直接成为正式证据；
- 修改附件后旧 source span 的 hash 校验会失败并阻断使用；
- adversarial citation fixture 不会把语义相似但不支持结论的片段判为支持。

### 阶段 3：方法学与统计纵向切片

目标：锁定分析计划和数据版本，并生成可重复的统计结果。

任务：

1. 实现病例表导入、数据字典、变量类型、单位和缺失编码验证。
2. 实现 `DatasetVersion` 内容 hash 和锁定机制。
3. 实现 Methodology Critic 的结构化 findings。
4. 实现 `AnalysisPlanVersion`、审批和 Analysis Plan Lock。
5. 先接确定性 mock runner，验证执行合同和产物结构。
6. 再接隔离的 Python/R runner，固定输入目录和只写输出目录。
7. 记录脚本、数据、计划、包版本、seed、环境、stdout/stderr 和退出码。

退出门槛：

- runner 只接受 approved/locked plan 和 locked dataset；
- 同一输入、脚本和环境可复现核心结果；
- 计划外分析必须标记为 `exploratory`；
- 统计 Agent 无法在执行阶段修改模型、变量或排除规则；
- 失败运行保留日志，但不能产生 approved result。

### 阶段 4：写作、审阅与修订纵向切片

目标：让每个正文主张具备结构化支持关系，并形成受控修订闭环。

任务：

1. 实现 `Manuscript`、section version、`Claim`、`ClaimSupport`、`Citation`。
2. 按章节生成草稿，不允许一次生成整篇后再追溯证据。
3. 对事实、统计结果、解释和建议使用不同 claim 类型与规则。
4. 实现 claim/citation audit：存在性、蕴含、过度外推、数字一致性。
5. Reviewer 只产生 findings，不直接修改稿件。
6. 人工接受/拒绝 finding 后，Revision Agent 才可生成新版本。
7. 修订后重新抽取 claim 并再次审计；默认最多三轮。

退出门槛：

- 每个事实性 claim 都能回溯到 EvidenceItem 或 StatisticalResult；
- manuscript 中的数值与正式统计结果逐项一致；
- “相关”不会被改写成因果或“证明”；
- 每次修改都有 finding、diff 和人工 disposition；
- 超过修订上限、finding 冲突或涉及 protocol/SAP 变化时升级人工处理。

### 阶段 5：合规与导出纵向切片

目标：形成可提交审阅的 Word 文件和完整 provenance package。

任务：

1. 将 STROBE-Vet 项目转换成可计算 checklist。
2. 实现图表编号、正文引用、参考文献、统计值和必填章节检查。
3. Final Audit 输出 findings 和 readiness，不自行宣称合规。
4. 实现授权用户 final sign-off，并绑定所有 artifact version/hash。
5. 生成 `manuscript.qmd`、`references.bib`、figures、tables 和 audit 文件。
6. 使用 Quarto/Pandoc 与 `reference-doc.docx` 导出 Word。
7. 生成 manifest、AI usage log 和 hash-addressed export package。

退出门槛：

- 高严重度未解决 finding 会阻断 sign-off/export；
- sign-off 后任何输入版本改变都会使导出失败；
- DOCX 能稳定生成并通过人工版式检查；
- 导出包包含八项 MVP 验收标准要求的全部材料。

### 阶段 6：生产化

该阶段不属于本地 MVP 的完成条件。内容包括：

- SQLite 迁移到 PostgreSQL；
- 用户认证、项目级授权和角色分离；
- 后台任务队列与长任务状态；
- 对象存储、备份、恢复和保留策略；
- 敏感病例数据的加密、脱敏和访问审计；
- 监控、追踪、成本、速率限制和告警；
- 部署、数据库迁移、回滚和灾难恢复演练。

## 5. 单项功能开发循环

每个 issue 按以下顺序实施：

1. **定义合同：** 输入、输出、artifact、权限、审批、失败和幂等性。
2. **补充 schema：** 先写类型和确定性 validator。
3. **先写测试：** 至少包含正常路径、非法输入和策略绕过测试。
4. **实现 domain/service：** 不依赖 Streamlit，不直接耦合模型供应商。
5. **实现薄 graph node：** 只做加载、调用、持久化和状态更新。
6. **接 UI：** UI 只展示和提交决策，不复制领域规则。
7. **记录 provenance：** 验证成功、失败和人工操作均写审计事件。
8. **运行完整质量门槛：** 通过后才可合并。

Agent 功能应先用固定 fixture 输出验证流程，再接 LLM。接入 LLM 后，
结构化输出验证失败不得保存为正式 artifact。

## 6. 分支、提交和评审流程

- 每项工作使用短生命周期分支，建议 `codex/<issue>-<summary>`。
- 一个提交只表达一个可解释的变更；schema 迁移与对应代码同时提交。
- Pull Request 必须说明：目标、非目标、schema 变化、迁移、测试、风险和回滚。
- 涉及锁定、审批、引用、统计或权限的改动至少需要一次专项评审。
- 不允许以“后续补测试”为由合并主路径控制逻辑。
- 破坏性数据库变更采用 expand/migrate/contract，不直接删除仍被读取的字段。

## 7. 测试分层

### 单元测试

- schema 和枚举；
- policy 纯函数；
- 状态转换和路由；
- hash 与不可变版本；
- claim/support 和结果一致性校验。

### 集成测试

- SQLite/Alembic；
- artifact store 原子写入；
- LangGraph checkpoint/interrupt/resume；
- Zotero API adapter（使用录制响应或 mock）；
- PDF/source span；
- mock 统计 runner 和 Quarto preflight。

### 端到端测试

使用固定 golden project，从 Project Init 运行到 export，覆盖批准、拒绝、
修改请求、中断恢复和修订循环。测试数据必须是合成或明确可再分发的数据。

### 对抗测试

- **adversarial citation：** 相似文献不等于支持证据；
- **claim inflation：** 相关性、趋势和不确定性不能被夸大；
- **approval bypass：** 禁止跳过 interrupt、读取未批准版本或修改锁定对象；
- **version contamination：** 新旧 artifact 不得混用；
- **prompt/tool injection：** 文献文本不能提升工具权限或改变 policy。

## 8. 每次合并的质量门槛

至少满足：

```text
format/lint pass
type check pass
unit tests pass
relevant integration tests pass
database migration check pass
no secrets / no sensitive fixture data
documentation updated when contracts change
```

涉及工作流主路径时，还必须运行 golden project 回归测试。涉及写作或检索时，
必须运行对应的 citation/claim 对抗测试。

## 9. Definition of Done

一项功能只有在以下条件全部成立时才算完成：

1. 合同、schema 和状态转换明确且有文档。
2. 正常路径、失败路径和权限绕过路径均有测试。
3. 所有正式输出不可变、带 hash 和 provenance。
4. 重试是有界且幂等的，不产生重复正式产物。
5. 人工审批绑定具体 version/hash，并验证 reviewer 权限。
6. UI、日志和错误信息不暴露密钥或敏感数据。
7. 可以从最近 checkpoint 恢复。
8. 对应 README/设计文档/ADR 已更新。

## 10. MVP 发布验收

发布候选版本必须使用 golden project 现场验证：

1. 任意审批点中断并恢复；
2. 正式产物具有不可变版本、hash 和来源；
3. 未审批产物无法进入下游正式写作；
4. 正文事实 claim 可回溯到 evidence/result；
5. citation 可回溯到 Zotero 和可用 PDF source span；
6. 统计结果可回溯到数据、脚本、环境和分析计划；
7. 修订具有 finding、diff 和人工 disposition；
8. 导出包包含稿件、文献、图表、checklist、AI 日志和 provenance。

其中任一项失败，都不应将版本标记为 MVP 完成。

## 11. 推荐的首批开发任务

按依赖顺序建立首批 issue：

1. ✅ 初始化 Python 包、测试和静态检查配置。
2. ✅ 整理 `WorkflowState` 并编写转换/序列化测试。
3. ✅ 实现 Artifact/ArtifactVersion 和本地 artifact store。
4. ✅ 实现 Approval/Lock/AuditEvent 与 policy 校验。
5. ✅ 实现 SQLite schema 和首个 Alembic migration。
6. ✅ 构建 Project Init -> Question Approval 的 mock LangGraph 切片。
7. ✅ 扩展到 Protocol Approval -> Protocol Lock。
8. ✅ 添加 Streamlit 项目、运行和审批页面。
9. ✅ 添加 checkpoint 中断恢复与 approval bypass 集成测试。
10. ✅ 建立不含真实病例数据的 golden project fixture。

完成这十项后，再进入 Zotero、PDF 和 LlamaIndex 集成。

### Phase 2 前置任务（数据结构层）

1. ✅ 评估 Phase 2 所需的领域表结构（对照 IDEA.md 与 domain_model.md）。
2. ✅ 创建迁移 0002_literature_evidence（6 张关系表 + 唯一约束 + 索引）。
3. ✅ 添加 ORM 模型（LiteratureRecord、AttachmentVersionRecord、
   SourceSpanRecord、EvidenceItemRecord、ScreeningDecisionRecord、
   ProvenanceLinkRecord）。
4. ✅ 补充 ArtifactType 枚举（7 个新类型）。
5. ✅ 创建 domain/policies/evidence.py（4 个策略函数 + 3 个 dataclass）。
6. ✅ 创建 LiteratureRepository（CRUD + 去重 + 筛选 + 溯源）。
7. ✅ 扩展 WorkflowState（LiteratureSummary、EvidenceSummary）。
8. ✅ 编写测试（20 个新测试覆盖仓库 + 策略 + 迁移）。
9. ✅ 记录 ADR-0005。

### Phase 2 业务逻辑开发任务（mock 切片已完成）

已完成的 mock 纵向切片覆盖了任务 5–8（确定性 stub 版本），
先跑通从 `PROTOCOL_LOCK` 到 `EVIDENCE_AUDIT` 的完整证据链，
所有策略不变量（source-span 前置、search-gate 前置、
screening 完整性、hash 校验）均在节点内强制执行。

新增文件与改动：

- `src/vet_manuscript_lab/workflow/literature_graph.py`：5 个节点
  （literature_search、search_approval、screening、evidence_extraction、
  evidence_audit）+ 路由 + `build_evidence_pipeline_graph`。
- `src/vet_manuscript_lab/workflow/state.py`：扩展 `LiteratureRecordDraft`、
  `SourceSpanDraft`、`EvidenceDraft` 三个 TypedDict 及对应 state 字段。
- `src/vet_manuscript_lab/domain/policies/__init__.py`：修复重复
  `__all__` 导致 evidence 策略导出丢失的缺陷。
- `tests/test_literature_graph.py`：9 个测试（3 集成 + 6 对抗），
  覆盖完整流程、跨实例 checkpoint 恢复、审批拒绝回退、
  source-span 缺失拒绝、未知 span 引用拒绝、hash 篡改拒绝。

下一步（外部集成层）：

1. 将 `literature_search_node` 的 mock records 替换为 Zotero API v3
   只读同步。
2. 将 `evidence_extraction_node` 的 mock spans/evidence 替换为
   PDF 解析 + LlamaIndex 检索的候选 chunk。
3. 保持现有节点合同和策略校验不变，只替换数据来源。

