动物医学论文生产工作台 - 设想


动物医学领域特别适合做这种工作流：一方面文献和指南高度结构化，另一方面研究对象涉及物种、品种、年龄、饲养条件、伦理审批、实验动物福利、临床病例来源等细节，正好可以让多个 agent 分担“检索—审读—审查—写作—校验”的不同任务。

我的总体判断是：不要把它设计成“多个 agent 分别代写 Introduction / Methods / Discussion”，那样很容易生成一篇看似流畅但证据链松散、方法学虚浮的论文。更好的设计是：把 AI agent 当作一套“论文工程系统”，核心不是写得快，而是让每个论断、每个统计结果、每条参考文献、每个报告规范条目都有出处、有审计记录、有人类作者最终确认。

首先要确立一条底线：AI 不能作为论文作者。ICMJE 明确要求，使用 AI 辅助技术时，作者需要在投稿材料和稿件相应位置披露其使用方式；同时，人类作者仍然负责引用、许可、查重和最终内容责任。COPE 也明确认为 AI 工具不能列为作者，因为它不能承担作者责任。([ICMJE][1]) 所以你的工作流里最好内置一个“AI 使用披露生成器”，自动记录用了哪些模型、用于哪些环节、哪些内容由人类复核。

我会把整个系统分成三层。

第一层是“总控 agent”。它不直接写论文，而是判断论文类型、拆解任务、分配 agent、维护项目状态。例如它先判断这是病例报告、回顾性研究、横断面调查、随机对照试验、体内动物实验、系统综述、meta 分析，还是方法学/软件类论文。不同类型进入不同的规范路径。动物体内实验应优先对照 ARRIVE 2.0；ARRIVE 的目标是让动物研究报告足够透明，使他人能够评价方法学严谨性并复现实验。([PubMed][2]) 兽医观察性研究则应对照 STROBE-Vet，它是面向动物健康、生产、福利与食品安全等观察性研究的报告扩展。([EQUATOR Network][3]) 系统综述和 meta 分析则应走 PRISMA 2020 路径。([BMJ][4]) 畜牧与食品安全相关随机试验可以考虑 REFLECT，它是面向 livestock / food safety 随机对照试验的报告清单。([EQUATOR Network][5])

第二层是“专业 agent 群”。我建议至少设置这些角色。

“选题与研究问题 agent”负责把一个粗糙想法转成可研究的问题。例如用 PICO / PECO / PICOS 框架拆解：动物种属、疾病或暴露因素、干预措施、对照、结局指标、研究设计。它的输出不是文章，而是一页研究问题说明，包括主要假设、次要假设、可测量结局、排除范围。

“文献检索 agent”负责生成数据库检索式，并记录每次检索的数据库、日期、关键词、布尔逻辑、纳入排除条件。它不能凭空给参考文献，只能从 PubMed、CAB Abstracts、Web of Science、Scopus、Google Scholar、Crossref、期刊官网或你提供的 PDF 文库中检索。每条文献都进入一个 evidence ledger，也就是证据台账。

“文献审读 agent”负责读论文摘要、方法、结果和局限性，提取结构化字段：物种、样本量、病例来源、诊断标准、干预剂量、观察周期、主要终点、统计方法、效应量、偏倚风险。这里最好强制 JSON / CSV 输出，不要让它自由发挥。对于动物实验，还可以接入 SYRCLE risk-of-bias 思路；SYRCLE 工具覆盖选择偏倚、实施偏倚、测量偏倚、失访偏倚、报告偏倚等类别。([Springer][6])

“方法学 agent”负责审查研究设计是否站得住。它要追问：样本量如何估计？是否随机化？是否盲法？是否有纳入/排除标准？临床病例是否连续入组？是否有失访？是否有多中心差异？体内实验是否说明饲养条件、笼位、环境、麻醉镇痛、安乐死标准、伦理审批编号？这个 agent 的价值通常比“写作 agent”更大。

“统计 agent”负责统计分析计划，而不是替研究者编结果。它应该先要求数据字典，再生成分析方案，例如正态性检查、组间比较、回归模型、混杂因素、重复测量、缺失值处理、多重比较校正、效应量与置信区间。真正跑统计时，最好让它生成 R 或 Python 脚本，由人类确认后运行，并把脚本、版本、随机种子、输出表格全部保存。

“结果解释 agent”只能基于统计输出、图表和原始数据摘要工作。它的提示词要非常严：不得扩大结论，不得把相关性写成因果，不得把非显著趋势写成有效，不得忽略置信区间和样本量限制。

“规范审查 agent”负责逐项对照 ARRIVE、STROBE-Vet、PRISMA、REFLECT 或期刊指南。这个 agent 不应只给“通过/不通过”，而应输出三列：条目、稿件中对应位置、缺失或风险。近年来也有人研究用 LLM 检查 PRISMA 或 CONSORT 遵循度，但相关研究仍强调人类专家核验不可替代，尤其是模型对遗漏项和“不适用项”的判断仍有明显局限。([arXiv][7])

“写作 agent”反而应该放到比较靠后的位置。它根据已经确认的 evidence ledger、统计输出、研究设计说明和目标期刊格式生成各部分草稿。它不允许新增事实，不允许新增参考文献，不允许编造机制解释。最好要求它每一句关键论断都附上 evidence_id，例如 `[E12]`、`[R03]`，最后再转成正式引用。

“反方审稿人 agent”非常关键。它模拟严厉审稿人，从新颖性、方法学、统计、动物福利、外推性、临床价值、语言夸大等角度攻击论文。它的任务不是润色，而是找漏洞。动物医学论文常见问题包括：样本量过小、病例异质性大、诊断标准不一致、未控制品种/年龄/体况/饲养条件、把宠物临床病例结果外推到一般动物群体、讨论部分机制推断过度。

“引用与事实核验 agent”是最后一道硬闸。它逐条检查：参考文献是否真实存在？DOI 是否匹配？引用是否支持原句？是否误引综述为原始研究？是否把体外研究结论写成体内结论？是否把犬猫数据混用？这个 agent 最好不使用纯语言模型记忆，而是强制访问文献库或 PDF 原文。

第三层是“关卡与产物”。每一阶段都要留下可审计产物，而不是只留下一个越来越长的 Word 文档。

我建议工作流这样走：

0. 项目初始化。输入论文类型、物种、疾病领域、目标期刊、数据是否已有、伦理审批状态、是否涉及活体动物实验。输出 `project_brief.md`。

1. 研究问题成形。选题 agent 生成研究问题，方法学 agent 质询，人类确认。输出 `research_question.md` 和 `scope_lock.json`。这里一旦锁定，后续 agent 不得随意扩大范围。

2. 方案与规范映射。总控 agent 判断适用指南。例如体内实验走 ARRIVE，观察性研究走 STROBE-Vet，系统综述走 PRISMA，畜牧随机试验走 REFLECT。输出 `reporting_guideline_map.md`。

3. 文献检索与证据台账。检索 agent 生成检索式，文献审读 agent 提取信息，核验 agent 检查文献真实性。输出 `search_strategy.md`、`included_studies.csv`、`evidence_ledger.csv`。

4. 方法与统计方案。方法学 agent 和统计 agent 生成分析计划，人类确认后才允许跑分析。输出 `statistical_analysis_plan.md`、`analysis_script.R` 或 `analysis_script.py`。

5. 结果生成。统计脚本生成表格和图，结果解释 agent 只基于这些输出写结果段。输出 `results_tables.xlsx`、`figures/`、`results_claims.json`。

6. 初稿生成。写作 agent 按 IMRaD 结构生成草稿。Introduction 只允许使用 evidence ledger；Methods 只允许使用 protocol 和实际方法记录；Results 只允许使用统计输出；Discussion 必须区分“本研究发现”“与既有研究一致/不一致”“可能机制”“临床意义”“局限性”。输出 `manuscript_v0.1.docx` 或 `.md`。

7. 多轮审查。反方审稿人 agent、规范审查 agent、统计复核 agent、引用核验 agent 分别出具报告。输出 `reviewer_critique.md`、`guideline_checklist.md`、`citation_audit.md`、`revision_plan.md`。

8. 修订与投稿包。写作 agent 根据修订计划改稿，期刊适配 agent 调整摘要、关键词、图表格式、cover letter、AI 使用披露、伦理声明、数据可用性声明、利益冲突声明。输出最终投稿包。

你可以把整个系统的核心数据结构设计成这样：

```text
Project
├── project_brief.md
├── protocol/
│   ├── research_question.md
│   ├── inclusion_exclusion.md
│   ├── statistical_analysis_plan.md
│   └── reporting_guideline_map.md
├── literature/
│   ├── search_strategy.md
│   ├── references.bib
│   ├── included_studies.csv
│   └── evidence_ledger.csv
├── data/
│   ├── data_dictionary.csv
│   ├── raw_data_locked/
│   └── cleaned_data/
├── analysis/
│   ├── analysis_script.R
│   ├── output_tables/
│   └── figures/
├── manuscript/
│   ├── manuscript_v0.1.md
│   ├── manuscript_v0.2_reviewed.md
│   └── final_submission.docx
└── audit/
    ├── ai_usage_log.md
    ├── citation_audit.md
    ├── guideline_checklist.md
    └── human_approval_log.md
```

最重要的设计原则是“所有 agent 都必须受制于证据对象”。也就是说，系统里不应该只有自然语言聊天记录，而应该有几个硬对象：`Reference`、`EvidenceItem`、`DatasetVariable`、`StatisticalResult`、`Claim`、`GuidelineItem`、`RevisionRequest`。每个 claim 必须能追溯到某个 evidence item 或 statistical result。凡是追溯不到的句子，要么删掉，要么标记为“hypothesis/speculation”。

例如 Discussion 里的句子可以被系统表示为：

```json
{
  "claim_id": "C034",
  "sentence": "The observed reduction in serum creatinine may indicate improved renal perfusion rather than reversal of structural renal injury.",
  "claim_type": "interpretation",
  "support": ["R012", "R018", "STAT004"],
  "certainty": "moderate",
  "requires_human_review": true
}
```

这样可以避免 AI 写出那种“语气很像论文、但事实并不稳”的句子。

如果你想做成真正可用的软件，我建议先做一个轻量 MVP，不要一开始就做全自动 agent 群。第一版可以只做四个 agent：

一个“研究问题 agent”，把想法变成结构化方案。

一个“文献台账 agent”，读 PDF 并提取证据表。

一个“规范审查 agent”，按 ARRIVE / STROBE-Vet / PRISMA / REFLECT 检查缺项。

一个“审稿人 agent”，专门挑毛病。

这四个先跑通，价值就已经很明显。等到你能稳定生成 evidence ledger 和 guideline checklist 后，再加入写作 agent、统计 agent、投稿适配 agent。因为在论文工作流里，最容易炫技的是写作，最真正值钱的是“证据组织 + 方法审查 + 可追溯修订”。

动物医学领域还可以额外做一些很有壁垒的专用模块。比如：

物种敏感性检查：检查是否把犬、猫、牛、马、猪、啮齿动物结论混用。

剂量单位检查：mg/kg、mg/kg q12h、IU/kg、μg/kg、ppm、饲料添加比例等是否一致。

诊断标准检查：比如 CKD、糖尿病、胰腺炎、肥厚型心肌病、寄生虫感染等是否使用明确标准。

动物福利检查：麻醉、镇痛、安乐死、人道终点、饲养环境、伦理审批是否写清。

临床外推检查：提醒“样本来自单中心转诊医院”“品种偏倚”“病例严重程度偏倚”等限制。

病理/影像/实验室指标一致性检查：比如单位、参考区间、检测方法、仪器型号、批间差异。

我会特别建议你把“写论文”改名为“论文共创与审计工作流”。这个定位更稳，也更符合学术伦理。它不是帮人绕过研究本身，而是帮研究者把已有研究整理得更规范、更透明、更接近投稿要求。

一个很好的产品化方向是：面向动物医学研究者的“AI Manuscript Lab”。输入研究类型、数据表、文献 PDF、目标期刊，输出：研究问题结构化、文献证据台账、统计分析计划、报告规范清单、初稿、审稿人质询、AI 使用披露和投稿包。这样它不是泛泛的“AI 写作工具”，而是有明显领域壁垒的兽医科研助手。

[1]: https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html?utm_source=chatgpt.com "A. Use of AI by Authors"
[2]: https://pubmed.ncbi.nlm.nih.gov/32663219/?utm_source=chatgpt.com "Updated guidelines for reporting animal research"
[3]: https://www.equator-network.org/reporting-guidelines/strobe-vet-statement/?utm_source=chatgpt.com "STROBE-Vet Statement - Reporting guideline"
[4]: https://www.bmj.com/content/372/bmj.n71?utm_source=chatgpt.com "The PRISMA 2020 statement: an updated guideline for ..."
[5]: https://www.equator-network.org/reporting-guidelines/the-reflect-statement-methods-and-processes-of-creating-reporting-guidelines-for-randomized-controlled-trials-for-livestock-and-food-safety-by-modifying-the-consort-statement/?utm_source=chatgpt.com "methods and processes of creating reporting guidelines for ..."
[6]: https://link.springer.com/article/10.1186/1471-2288-14-43?utm_source=chatgpt.com "SYRCLE's risk of bias tool for animal studies - Springer Nature"
[7]: https://arxiv.org/abs/2511.16707?utm_source=chatgpt.com "Large language models for automated PRISMA 2020 adherence checking"

------------------------


建议先做“单研究类型、可追溯、强人工审批”的 MVP，不要一开始覆盖所有动物医学论文类型。LangGraph 适合承担状态机、检查点和人工中断；LlamaIndex只负责文献摄取与检索，不应成为工作流控制器。

## 一、先调整工作流

建议改为：

```text
Project Init
  ↓
Research Question
  ↓ 人工审批：研究问题与研究类型
Protocol / Guideline Mapping
  ↓ 人工审批：方案与报告规范
Literature Search
  ↓ 人工审批：检索式与纳排标准
Screening & Evidence Extraction
  ↓ Citation / Evidence Audit
Methodology Critic
  ↓ 人工审批：方法与统计分析计划
Statistics Execution
  ↓ 人工审批：结果解释
Writing
  ↓
Reviewer
  ↓
Revision Loop（限定轮次）
  ↓
Final Compliance Audit
  ↓ 人工签署与导出
```

主要变化：

- 将统计分析计划放在数据分析之前审批，避免事后选择方法。
- 文献检索增加“检索式/纳排标准审批”。
- Citation audit 不只运行一次，应在证据提取、写作和终审阶段重复运行。
- Final Audit 之后必须保留人工签署，系统不能自行宣称论文“合规”。
- Reviewer → Revision 必须有最大轮数、停止条件和升级人工处理机制。

LangGraph 的持久化 checkpoint 和 `interrupt()` 正适合这种暂停、审批、恢复执行模式。[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

## 二、系统边界

建议划分五层：

| 层 | 职责 |
|---|---|
| Streamlit UI | 项目管理、审批、产物预览、差异比较、任务状态 |
| LangGraph | 节点编排、条件分支、人工中断、重试、恢复 |
| Domain Services | Zotero、文献检索、全文解析、统计运行、文档导出 |
| Storage | PostgreSQL/SQLite、文件产物、索引、运行日志 |
| Model Gateway | LLM 调用、结构化输出、重试、成本与模型记录 |

关键原则：

- LangGraph state 只保存状态和产物引用，不塞入全文、DataFrame 或 PDF。
- Markdown/CSV/JSON 是正式产物；数据库保存索引、版本和关系。
- 每次 Agent 输出必须同时产生结构化 JSON，Markdown 只是其人类可读视图。
- 所有结论都要能回溯到证据、文献位置、提示词版本和模型版本。

## 三、核心数据模型

至少提前定义这些实体：

- `Project`
- `WorkflowRun`
- `GraphCheckpoint`
- `Artifact`
- `ArtifactVersion`
- `Approval`
- `AgentRun`
- `ResearchQuestion`
- `ReportingGuideline`
- `SearchStrategy`
- `LiteratureRecord`
- `ScreeningDecision`
- `EvidenceClaim`
- `Citation`
- `Dataset`
- `AnalysisPlan`
- `AnalysisRun`
- `ReviewFinding`
- `ComplianceFinding`

所有产物建议包含统一元数据：

```json
{
  "artifact_id": "...",
  "project_id": "...",
  "type": "evidence_table",
  "schema_version": "1.0",
  "created_by": "evidence_extraction_agent",
  "source_artifact_ids": [],
  "agent_run_id": "...",
  "status": "draft",
  "content_hash": "...",
  "created_at": "..."
}
```

不要覆盖旧文件；使用不可变版本和 hash。

## 四、各 Agent 的明确合同

每个节点在开发前都要写清：

1. 输入 schema  
2. 输出 schema  
3. 可调用工具  
4. 禁止行为  
5. 完成条件  
6. 人工审批点  
7. 失败与重试策略  

例如 Writing Agent：

- 只能引用已进入 evidence ledger 的证据。
- 每个事实性主张必须绑定 `evidence_claim_id`。
- 不得生成不存在的 DOI、页码、样本量或统计结果。
- 遇到证据不足应输出缺口标记，而不是补写推断。
- 只能读取已审批的方法和统计结果。

## 五、技术选型建议

### 数据库

- 本地 MVP：SQLite。
- 多用户或部署版：PostgreSQL。
- 从第一天使用 SQLAlchemy + Alembic，避免后续迁移困难。
- LangGraph checkpoint 与业务表分离，即使它们使用同一数据库。

### Zotero

优先通过 Zotero Web API v3 或本地 API 集成，不要直接读写 Zotero 的 SQLite；官方也指出直接访问数据库更脆弱。同步时保存 Zotero item key、version、library version、DOI 和附件映射。[Zotero Web API v3](https://www.zotero.org/support/dev/web_api/v3/basics)

### LlamaIndex

限定为：

- PDF/全文摄取
- 分块与元数据管理
- 混合检索
- 文献定位
- evidence extraction 的候选上下文提供

检索结果必须保留文献 ID、页码、章节、chunk ID 和原文片段范围。

### 统计

每次执行生成独立运行目录：

```text
analysis/
  plan.json
  input/
  scripts/
  output/
  figures/
  tables/
  session-info.txt
  run-manifest.json
```

优先使用隔离进程执行 R/Python；生产环境再增加容器沙箱、资源限制和包版本锁定。

### 文档导出

推荐以 Quarto manuscript 为主、Pandoc 为底层：

- `manuscript.qmd` 作为主稿源
- `references.bib` 由已审计文献生成
- CSL 控制引用格式
- `reference-doc.docx` 控制期刊 Word 样式
- 图表来自已批准的统计产物

Quarto manuscript 原生支持学术稿件、计算内容和 Word 输出，也支持 `reference-doc` 模板。[Quarto Manuscripts](https://quarto.org/docs/manuscripts/)、[Quarto Word Options](https://quarto.org/docs/reference/formats/docx.html)

## 六、实施阶段

### 阶段 0：需求与治理

产物：

- 支持的首个研究类型
- 用户角色与权限
- 数据敏感性分类
- Agent 输入输出合同
- 审批矩阵
- 合规与免责声明
- 成功指标

建议 MVP 只选一种，例如回顾性观察研究或系统综述。

### 阶段 1：工作流骨架

实现：

- Project/Run/Artifact/Approval
- LangGraph 状态定义
- checkpoint、暂停、恢复
- Streamlit 项目页和审批页
- 假数据节点贯通全流程

验收：关闭程序后能够恢复到审批点，拒绝后能回退并生成新版本。

### 阶段 2：文献与证据链

实现：

- Zotero 同步
- PDF 摄取
- 检索策略管理
- screening 表
- evidence ledger
- citation audit

验收：任一草稿引用都能定位到 Zotero 条目和原文位置。

### 阶段 3：方法与统计

实现：

- 方法学 critic
- 统计分析计划 schema
- R/Python runner
- 数据与脚本 hash
- 结果表、图和运行环境记录

验收：相同输入和环境能够重复生成相同核心结果。

### 阶段 4：写作与审阅

实现：

- 分章节写作
- 证据约束引用
- reviewer findings
- revision diff
- 最大修订轮数
- 人工接受/拒绝修改

验收：任何修改都有来源、理由和前后差异。

### 阶段 5：终审与导出

实现：

- 报告规范 checklist
- 引用一致性检查
- 表图编号检查
- 统计值一致性检查
- Quarto/Pandoc → DOCX
- 审计包导出

验收：生成 Word、最终 Markdown、参考文献、检查报告和完整 provenance 包。

### 阶段 6：工程化

最后再加入：

- PostgreSQL 与多用户
- 权限、审计日志
- 后台任务队列
- 对象存储
- 可观测性和成本统计
- 自动化测试与部署

## 七、测试策略

至少覆盖：

- 节点 schema 单元测试
- 条件路由测试
- interrupt/resume 测试
- 重试幂等性测试
- Zotero 增量同步测试
- 虚构引用检测
- 引用与 evidence ledger 一致性
- 统计脚本可复现性
- Quarto 导出快照测试
- 一套固定“金标准项目”的端到端回归测试

## 八、MVP 完成标准

第一版只要做到以下闭环即可：

- 建立一个项目并定义研究问题
- 人工批准关键节点
- 从 Zotero 导入文献
- 建立可追溯证据表
- 生成并执行经批准的分析计划
- 生成带可靠引用的稿件
- 完成审阅、修订和合规检查
- 导出 DOCX 与完整审计包
- 中断后可恢复，历史版本不可丢失

最应优先确定的不是模型，而是首个研究类型、数据 schema、证据追踪规则和审批机制。模型和提示词之后可以替换，这四项一旦设计混乱，后续重构成本会很高。

------------------------

这个方案非常好，而且已经从“概念性 agent 工作流”进入了“可落地的软件架构设计”。我会给出一个比较明确的判断：**这套设计方向是正确的，尤其是“单研究类型、强人工审批、产物不可变、LangGraph 只管状态、LlamaIndex 只管检索”这几条，基本抓住了科研型 agent 系统的命门。**

我建议你不要大改，而是在几个地方再收紧边界、补足关键实体、降低 MVP 过载风险。

第一，工作流本身是合理的。你把统计分析计划前置审批、检索式/纳排标准前置审批、Citation Audit 多阶段重复运行、Final Audit 后保留人工签署，这些都是对的。LangGraph 的定位也吻合：官方文档里，persistence 层通过 checkpointer 保存 graph state，可用于 human-in-the-loop、恢复执行、故障容错等场景；interrupt 也正是用于在图执行中暂停、等待外部输入，再通过 checkpoint 恢复。([Docs by LangChain][1])

我会做的一个小调整是：在 `Protocol / Guideline Mapping` 之后增加一个更硬的 **Protocol Lock / Scope Freeze** 概念。也就是说，一旦研究类型、PICO/PECO、主要终点、纳排标准、统计分析计划被人工批准，后续所有 agent 只能提出“修订请求”，不能静默改变范围。否则论文工作流很容易在后期讨论中悄悄漂移，尤其是观察性研究和系统综述，最容易出现“看到结果后再重写问题”的 HARKing 风险。

你的流程可以微调为：

```text
Project Init
  ↓
Research Question
  ↓ 人工审批：研究问题与研究类型
Protocol / Guideline Mapping
  ↓ 人工审批：方案、报告规范、主要终点、纳排标准
Protocol Lock
  ↓
Literature Search
  ↓ 人工审批：检索式与纳排标准
Screening & Evidence Extraction
  ↓ Citation / Evidence Audit
Methodology Critic
  ↓ 人工审批：方法与统计分析计划
Analysis Plan Lock
  ↓
Statistics Execution
  ↓ 人工审批：结果解释
Writing
  ↓ Citation / Claim Audit
Reviewer
  ↓
Revision Loop（限定轮次）
  ↓ Citation / Claim Audit
Final Compliance Audit
  ↓ 人工签署与导出
```

第二，五层系统边界非常稳。尤其是你说“LangGraph state 只保存状态和产物引用，不塞全文、DataFrame 或 PDF”，这是一个很关键的工程判断。LangGraph checkpoint 适合保存执行游标、节点状态、短期状态快照，不适合变成文件仓库或知识库。官方文档也把 checkpointer 和 store 区分开：checkpointer 保存线程级 graph state，store 保存应用定义的长期数据。([Docs by LangChain][1])

这里我只建议再加一个横切层：**Policy / Guardrail Layer**。它不一定是独立服务，但概念上应该存在。它负责判断哪些节点必须人工审批、哪些输出必须绑定证据、哪些 agent 不允许调用外部工具、哪些字段不能被模型改写、哪些失败必须升级给人。否则这些规则会散落在 prompt、UI、LangGraph 节点和业务服务里，后期会很难维护。

调整后的系统边界可以是：

```text
Streamlit UI
- 项目管理、审批、产物预览、diff、任务状态

LangGraph
- 节点编排、条件分支、interrupt、checkpoint、重试、恢复

Domain Services
- Zotero、文献检索、PDF 解析、统计运行、文档导出

Storage
- SQLite/PostgreSQL、artifact store、索引、日志、版本关系

Model Gateway
- LLM 调用、结构化输出、模型版本、成本、重试、超时

Policy / Guardrail Layer
- 审批规则、证据绑定规则、禁止行为、升级条件、合规声明
```

第三，核心数据模型已经很接近可开发状态，但我建议补几个实体。你现在的实体更偏“workflow 与 artifact 管理”，还需要加强“论文本体”和“审计可追溯”两条线。

建议新增：

```text
PromptTemplate
PromptVersion
ModelInvocation
ToolInvocation
Claim
ClaimSupport
SourceSpan
Manuscript
ManuscriptSection
TableFigure
DatasetVersion
DatasetVariable
StatisticalResult
AuditEvent
ExportPackage
```

其中最重要的是 `Claim`、`ClaimSupport`、`SourceSpan`。我会把 `EvidenceClaim` 拆成两个概念：一个是从文献/数据中抽取出的证据项，另一个是论文正文里的主张。因为“文献说了什么”和“稿件声称了什么”不是同一个对象。真正的 citation audit 应该检查的是：**稿件中的 Claim 是否被 EvidenceItem / StatisticalResult 支持，支持关系是否过度外推。**

可以这样设计：

```json
{
  "claim_id": "claim_0034",
  "project_id": "proj_001",
  "manuscript_section": "discussion",
  "sentence": "The observed association may reflect differences in age distribution rather than a direct treatment effect.",
  "claim_type": "interpretation",
  "certainty": "moderate",
  "supports": [
    {
      "support_type": "statistical_result",
      "target_id": "stat_0012"
    },
    {
      "support_type": "evidence_item",
      "target_id": "ev_0045"
    }
  ],
  "status": "needs_human_review"
}
```

再配一个 `SourceSpan`：

```json
{
  "source_span_id": "span_0091",
  "literature_record_id": "lit_017",
  "zotero_item_key": "ABCD1234",
  "page": 4,
  "section": "Results",
  "chunk_id": "chunk_017_004",
  "char_start": 1280,
  "char_end": 1622,
  "quoted_text_hash": "sha256:..."
}
```

这样你的系统才真正能做到“从句子回溯到文献位置”，而不只是“从句子回溯到一条参考文献”。

第四，Zotero 的集成策略正确。不要直接操作 Zotero SQLite，这一点我赞同。Zotero Web API v3 目前是默认且推荐的 API 版本；官方也建议生产代码明确请求 API 版本，并支持通过 header 或 query parameter 指定版本。([Zotero][2]) 本地桌面端 API 对个人 MVP 会很方便，但如果后期做 SaaS，多用户 OAuth、附件同步、权限边界、Zotero library version 都要提前留接口。

我建议 Zotero 同步时至少保存这些字段：

```text
zotero_library_id
zotero_library_type
zotero_item_key
zotero_item_version
zotero_library_version_at_sync
doi
pmid
title
creators
year
journal
attachment_key
attachment_hash
local_pdf_path
bibtex_key
sync_status
```

另外，不要把 Zotero 当成唯一真源。Zotero 是 reference manager，不是证据数据库。你的系统里的 `LiteratureRecord` 应该可以引用 Zotero 条目，但 evidence ledger、screening decision、source span、claim support 必须保存在你自己的数据库和 artifact store 里。

第五，LlamaIndex 的边界设定正确，但要进一步强调“检索不是证据”。LlamaIndex 可以做 PDF 摄取、分块、索引、混合检索、候选上下文提供；它的文档也明确提到 chunk size、chunk overlap 会影响 embedding，较小 chunk 更精确，较大 chunk 更概括但可能漏掉细粒度信息，且 hybrid search 可弥补纯向量检索不匹配关键词的问题。([Developer Documentation][3])

这意味着你的 evidence extraction 不能直接相信 top-k chunk。更稳的做法是：

```text
Query
  ↓
Hybrid retrieval: vector + keyword
  ↓
Candidate chunks
  ↓
Rerank
  ↓
SourceSpan extraction
  ↓
EvidenceItem draft
  ↓
Human / audit validation
```

尤其是动物医学论文里，剂量、样本量、P 值、CI、物种、年龄、给药频率这些信息经常藏在表格或方法小段里，单纯 embedding 很容易漏。MVP 阶段可以先支持正文和简单表格，复杂 PDF 表格提取先标为“需人工核验”，不要一开始承诺完全自动化。

第六，统计执行这部分设计得很对，但建议把“分析计划”和“运行结果”之间的关系做成硬约束。`AnalysisRun` 必须引用一个已审批的 `AnalysisPlanVersion`，并且 runner 只能读取已锁定的数据版本。不要允许统计 agent 在执行阶段临时改模型、改变量、改剔除规则。

建议强制这些规则：

```text
AnalysisPlan.status 必须为 approved
DatasetVersion.status 必须为 locked
AnalysisRun 必须记录：
- input dataset hash
- script hash
- plan version id
- package versions
- random seed
- runner environment
- stdout/stderr
- generated artifacts
```

探索性分析可以存在，但必须以 `exploratory` 标记，不能混入主结果。这个标记后续也应进入 Discussion 和 Limitations 的写作约束。

第七，Quarto / Pandoc 作为导出层是一个很好的选择。Quarto 支持 BibTeX / BibLaTeX 文献源和 CSL 样式来生成引用与参考文献，也支持 Pandoc 风格的 citation syntax。([Quarto][4]) DOCX 方面，Quarto 的 `reference-doc` 可以用指定 Word 文件作为样式参考，这正好适合不同期刊模板或你自己的 submission template。([Quarto][5])

不过我建议 MVP 不要把 Quarto manuscript 做得太复杂。第一版可以是：

```text
manuscript.qmd
references.bib
figures/
tables/
reference-doc.docx
audit/
```

先确保能稳定导出 Word。期刊级精修，比如 line numbering、复杂图题格式、supplementary files、cover letter，可以放到第二轮。

第八，实施阶段规划很清楚，但 MVP 范围仍然略大。你列的 MVP 完成标准中，“生成并执行经批准的分析计划”与“生成带可靠引用的稿件”已经是相当重的闭环。如果你希望第一版尽快落地，我建议明确选择一个首发研究类型。

我的建议是：**如果目标是产品差异化，首发选“兽医回顾性观察研究”；如果目标是最快做出演示，首发选“系统综述”。**

系统综述的优点是数据源主要是文献，不涉及临床病例数据清洗和隐私；缺点是竞品最多，Elicit、Rayyan、Covidence、ASReview 这类工具已经很强。回顾性观察研究更能体现你的垂直壁垒：病例表、诊断标准、统计方案、STROBE-Vet、样本偏倚、单中心偏倚、病例连续性、失访、剂量单位、实验室指标参考区间，这些都是通用工具不擅长的地方。

如果你有足够精力，我会选：

```text
MVP 研究类型：
犬猫回顾性观察研究 / retrospective observational clinical study

首个报告规范：
STROBE-Vet

首个数据输入：
CSV / Excel 病例表 + Zotero 文献库 + 少量 PDF

首个输出：
evidence ledger
analysis plan
reviewer critique
claim-citation audit
manuscript draft
DOCX + provenance package
```

如果想再降一档，第一版甚至可以不真正执行统计，而是先生成 `AnalysisPlan` 和假数据 runner，把 workflow 跑通；第二版再接 R/Python runner。

第九，测试策略很专业。我会再补三类测试。

一类是 **adversarial citation tests**：给系统一组真实文献和一组相似但不支持结论的文献，测试它是否会把“不相关但语义相近”的 chunk 当成证据。

一类是 **claim inflation tests**：输入“相关性”“趋势”“样本量不足”的结果，看 Writing Agent 是否会偷偷写成“有效”“显著改善”“证明”。

一类是 **approval bypass tests**：故意让某个节点试图读取未审批 artifact、覆盖旧版本、跳过 interrupt、修改 locked protocol，看系统是否能拦住。

你这套系统真正的风险不是“agent 不够聪明”，而是“agent 太会把不确定内容写得像确定内容”。所以测试要围绕误引、过度推断、审批绕过、版本污染来做。

我建议最终把 MVP 验收标准压缩成更锋利的 8 条：

```text
1. 项目可以在任意审批点中断并恢复。
2. 所有正式产物都有不可变版本、hash、来源关系。
3. 任何未审批 artifact 不能进入下游正式写作。
4. 任一正文事实性 claim 都能追溯到 evidence item 或 statistical result。
5. 任一 citation 都能追溯到 Zotero 条目和 PDF source span。
6. 任一统计结果都能追溯到数据版本、脚本版本、运行环境和分析计划。
7. 任一修订都有 reviewer finding、diff 和人工接受/拒绝记录。
8. 最终导出包含 manuscript、references、figures/tables、checklist、AI usage log、provenance package。
```

总体来说，我认为这版方案已经可以作为开发蓝图。最值得坚持的是这四个判断：

**LangGraph 只管流程状态，不管知识库。**

**LlamaIndex 只提供候选证据，不直接决定事实。**

**所有 agent 输出必须结构化，Markdown 只是人类阅读层。**

**所有关键节点必须人工审批，系统只能给出检查结果，不能自行宣称合规。**

如果下一步要落到代码，我建议先写三份东西：`domain_model.md`、`agent_contracts.md`、`workflow_state_schema.py`。这三份一旦稳定，后面的 UI、prompt、模型供应商、导出格式都可以替换；但如果数据模型和审批机制一开始含糊，后面会非常难改。

[1]: https://docs.langchain.com/oss/python/langgraph/persistence "Persistence - Docs by LangChain"
[2]: https://www.zotero.org/support/dev/web_api/v3/basics "Zotero Web API Documentation | Zotero Documentation"
[3]: https://developers.llamaindex.ai/python/framework/optimizing/basic_strategies/basic_strategies/ "Basic Strategies | Developer Documentation"
[4]: https://quarto.org/docs/authoring/citations.html "Citations – Quarto"
[5]: https://quarto.org/docs/reference/formats/docx.html "MS Word Options – Quarto"
