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
