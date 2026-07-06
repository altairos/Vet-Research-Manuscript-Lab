"""Bilingual (English / Chinese) UI string catalog and lookup helper.

All user-facing text lives here so the Streamlit app can switch language at
runtime without touching workflow or domain code. Workflow stage names and
approval-gate titles/summaries are translated by their stable enum/string keys,
so graph node payloads remain English-only and serializable.
"""

from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = ("en", "zh")

# language selector display labels keyed by language code
LANGUAGE_LABELS: dict[str, str] = {"en": "English", "zh": "中文"}

# key -> {language: text}
STRINGS: dict[str, dict[str, str]] = {
    "page_title": {
        "en": "Vet Research Manuscript Lab",
        "zh": "兽医科研稿件实验室",
    },
    "app_title": {
        "en": "Vet Research Manuscript Lab",
        "zh": "兽医科研稿件实验室",
    },
    "app_caption": {
        "en": "Foundation MVP: project setup, approval gates, and protocol lock",
        "zh": "基础 MVP：项目创建、审批门与方案锁定",
    },
    "language_label": {
        "en": "Language",
        "zh": "语言",
    },
    "create_project_header": {
        "en": "Create project",
        "zh": "创建项目",
    },
    "field_project_title": {
        "en": "Project title",
        "zh": "项目标题",
    },
    "field_owner_id": {
        "en": "Owner ID",
        "zh": "负责人 ID",
    },
    "field_species_scope": {
        "en": "Species scope",
        "zh": "动物物种范围",
    },
    "button_create": {
        "en": "Create",
        "zh": "创建",
    },
    "info_no_projects": {
        "en": "No projects yet.",
        "zh": "暂无项目。",
    },
    "success_project_created": {
        "en": "Created project {id}",
        "zh": "已创建项目 {id}",
    },
    "field_active_project": {
        "en": "Active project",
        "zh": "当前项目",
    },
    "workflow_header": {
        "en": "Foundation workflow",
        "zh": "基础工作流",
    },
    "button_start_run": {
        "en": "Start new Foundation run",
        "zh": "启动新的基础工作流",
    },
    "label_thread_id": {
        "en": "Thread",
        "zh": "线程",
    },
    "label_stage": {
        "en": "Stage",
        "zh": "阶段",
    },
    "label_status": {
        "en": "Status",
        "zh": "状态",
    },
    "label_next": {
        "en": "Next",
        "zh": "下一步",
    },
    "expander_artifact_refs": {
        "en": "Artifact references",
        "zh": "产物引用",
    },
    "expander_approvals_locks": {
        "en": "Approvals and locks",
        "zh": "审批与锁定",
    },
    "success_protocol_locked": {
        "en": "Protocol is approved and locked.",
        "zh": "方案已审批并锁定。",
    },
    "field_reviewer_id": {
        "en": "Reviewer ID",
        "zh": "审批人 ID",
    },
    "field_reviewer_role": {
        "en": "Reviewer role",
        "zh": "审批人角色",
    },
    "field_decision": {
        "en": "Decision",
        "zh": "审批决定",
    },
    "field_comment": {
        "en": "Comment",
        "zh": "意见说明",
    },
    "button_submit_decision": {
        "en": "Submit decision",
        "zh": "提交决定",
    },
    "role_investigator": {
        "en": "investigator",
        "zh": "研究者",
    },
    "role_statistician": {
        "en": "statistician",
        "zh": "统计师",
    },
    "species_canine": {
        "en": "canine",
        "zh": "犬",
    },
    "species_feline": {
        "en": "feline",
        "zh": "猫",
    },
    # workflow stage display names
    "stage.project_init": {"en": "Project init", "zh": "项目初始化"},
    "stage.research_question": {"en": "Research question", "zh": "研究问题"},
    "stage.question_approval": {"en": "Question approval", "zh": "问题审批"},
    "stage.guideline_mapping": {"en": "Guideline mapping", "zh": "规范映射"},
    "stage.protocol_approval": {"en": "Protocol approval", "zh": "方案审批"},
    "stage.protocol_lock": {"en": "Protocol lock", "zh": "方案锁定"},
    "stage.literature_search": {"en": "Literature search", "zh": "文献检索"},
    "stage.search_approval": {"en": "Search approval", "zh": "检索审批"},
    "stage.screening": {"en": "Screening", "zh": "文献筛选"},
    "stage.evidence_extraction": {"en": "Evidence extraction", "zh": "证据提取"},
    "stage.evidence_audit": {"en": "Evidence audit", "zh": "证据审计"},
    "stage.methodology_critic": {"en": "Methodology critic", "zh": "方法学评审"},
    "stage.analysis_plan_approval": {
        "en": "Analysis plan approval",
        "zh": "分析计划审批",
    },
    "stage.analysis_plan_lock": {"en": "Analysis plan lock", "zh": "分析计划锁定"},
    "stage.statistics_execution": {"en": "Statistics execution", "zh": "统计执行"},
    "stage.results_approval": {"en": "Results approval", "zh": "结果审批"},
    "stage.writing": {"en": "Writing", "zh": "正文写作"},
    "stage.claim_audit": {"en": "Claim audit", "zh": "论点审计"},
    "stage.review": {"en": "Review", "zh": "审阅"},
    "stage.revision": {"en": "Revision", "zh": "修订"},
    "stage.final_compliance_audit": {
        "en": "Final compliance audit",
        "zh": "最终合规审计",
    },
    "stage.final_sign_off": {"en": "Final sign-off", "zh": "最终签署"},
    "stage.export": {"en": "Export", "zh": "导出"},
    "stage.complete": {"en": "Complete", "zh": "已完成"},
    "stage.blocked": {"en": "Blocked", "zh": "已阻断"},
    "stage.failed": {"en": "Failed", "zh": "失败"},
    # run status display names
    "status.pending": {"en": "pending", "zh": "待运行"},
    "status.running": {"en": "running", "zh": "运行中"},
    "status.waiting_for_human": {"en": "waiting for human", "zh": "等待人工"},
    "status.blocked": {"en": "blocked", "zh": "已阻断"},
    "status.failed": {"en": "failed", "zh": "失败"},
    "status.complete": {"en": "complete", "zh": "已完成"},
    "status.cancelled": {"en": "cancelled", "zh": "已取消"},
    # approval decision display names
    "decision.approved": {"en": "approved", "zh": "批准"},
    "decision.rejected": {"en": "rejected", "zh": "拒绝"},
    "decision.changes_requested": {
        "en": "changes requested",
        "zh": "要求修改",
    },
    # approval gate titles/summaries keyed by gate + field
    "gate.question.title": {
        "en": "Approve research question and study type",
        "zh": "审批研究问题与研究类型",
    },
    "gate.question.summary": {
        "en": "Review the structured PECO question before protocol mapping.",
        "zh": "在映射到方案前审阅结构化的 PECO 研究问题。",
    },
    "gate.protocol.title": {
        "en": "Approve and lock protocol scope",
        "zh": "审批并锁定研究方案范围",
    },
    "gate.protocol.summary": {
        "en": "Review endpoints, eligibility, and STROBE-Vet mapping.",
        "zh": "审阅终点、纳入排除标准与 STROBE-Vet 规范映射。",
    },
    "gate.search_strategy.title": {
        "en": "Approve search strategy and database queries",
        "zh": "审批检索策略与数据库查询",
    },
    "gate.search_strategy.summary": {
        "en": "Review databases, query strings, and date filters before screening.",
        "zh": "在筛选前审阅数据库、查询字符串与日期范围。",
    },
    # literature + evidence view labels
    "section_literature": {"en": "Literature records", "zh": "文献记录"},
    "section_evidence": {"en": "Evidence items", "zh": "证据条目"},
    "section_source_spans": {"en": "Source spans", "zh": "来源段落"},
    "col_record_id": {"en": "Record ID", "zh": "记录 ID"},
    "col_title": {"en": "Title", "zh": "标题"},
    "col_doi": {"en": "DOI", "zh": "DOI"},
    "col_decision": {"en": "Screening", "zh": "筛选"},
    "col_page": {"en": "Page", "zh": "页码"},
    "col_section": {"en": "Section", "zh": "章节"},
    "col_concept": {"en": "Concept", "zh": "概念"},
    "col_value": {"en": "Value", "zh": "值"},
    "col_review": {"en": "Needs review", "zh": "待审核"},
    "col_status": {"en": "Status", "zh": "状态"},
    "col_span_id": {"en": "Span ID", "zh": "段落 ID"},
    "label_yes": {"en": "Yes", "zh": "是"},
    "label_no": {"en": "No", "zh": "否"},
    "info_no_literature": {
        "en": "No literature records yet.",
        "zh": "暂无文献记录。",
    },
    "info_no_evidence": {
        "en": "No evidence items extracted yet.",
        "zh": "暂无提取的证据条目。",
    },
    "label_included_count": {"en": "Included", "zh": "纳入"},
    "label_excluded_count": {"en": "Excluded", "zh": "排除"},
    "label_total_evidence": {"en": "Total evidence", "zh": "证据总数"},
    "label_items_review": {
        "en": "Items requiring review",
        "zh": "待审核条目",
    },
    "app_caption_full": {
        "en": (
            "Full pipeline: research question -> literature -> "
            "evidence -> methodology -> statistics"
        ),
        "zh": "完整流水线：研究问题 → 文献 → 证据 → 方法学 → 统计分析",
    },
    "button_start_full_run": {
        "en": "Start full analysis pipeline",
        "zh": "启动完整分析流水线",
    },
    "workflow_header_full": {
        "en": "Analysis pipeline",
        "zh": "分析流水线",
    },
    "success_pipeline_complete": {
        "en": "Pipeline complete: statistical results approved.",
        "zh": "流水线完成：统计结果已审批。",
    },
    # methodology + analysis views
    "section_methodology": {"en": "Methodology findings", "zh": "方法学发现"},
    "section_analysis_plan": {"en": "Analysis plan", "zh": "分析计划"},
    "section_results": {"en": "Statistical results", "zh": "统计结果"},
    "col_category": {"en": "Category", "zh": "类别"},
    "col_severity": {"en": "Severity", "zh": "严重度"},
    "col_rationale": {"en": "Rationale", "zh": "理由"},
    "col_recommendation": {"en": "Recommendation", "zh": "建议"},
    "col_analysis_name": {"en": "Analysis", "zh": "分析名称"},
    "col_estimand": {"en": "Estimand", "zh": "估计量"},
    "col_estimate": {"en": "Estimate", "zh": "估计值"},
    "col_ci": {"en": "95% CI", "zh": "95% CI"},
    "col_p_value": {"en": "P value", "zh": "P 值"},
    "col_method": {"en": "Method", "zh": "方法"},
    "col_class": {"en": "Class", "zh": "类型"},
    "label_findings_count": {"en": "Total findings", "zh": "发现总数"},
    "label_warnings_count": {
        "en": "Warnings",
        "zh": "警告数",
    },
    "label_analysis_count": {"en": "Analyses", "zh": "分析数量"},
    "label_plan_locked": {"en": "Plan locked", "zh": "计划已锁定"},
    "label_dataset_locked": {
        "en": "Dataset locked",
        "zh": "数据集已锁定",
    },
    "label_run_status": {"en": "Run status", "zh": "运行状态"},
    "label_result_count": {"en": "Results", "zh": "结果数"},
    "label_reproducible": {
        "en": "Reproducible",
        "zh": "可复现",
    },
    "info_no_methodology": {
        "en": "No methodology findings yet.",
        "zh": "暂无方法学发现。",
    },
    "info_no_analysis_plan": {
        "en": "No analysis plan generated yet.",
        "zh": "暂无分析计划。",
    },
    "info_no_results": {
        "en": "No statistical results yet.",
        "zh": "暂无统计结果。",
    },
    "gate.analysis_plan.title": {
        "en": "Approve analysis plan and dataset lock",
        "zh": "审批分析计划并锁定数据集",
    },
    "gate.analysis_plan.summary": {
        "en": (
            "Review analyses, variable mappings, models, "
            "and exclusion criteria before locking."
        ),
        "zh": "在锁定前审阅分析项、变量映射、模型与排除标准。",
    },
    "gate.results_interpretation.title": {
        "en": "Review statistical results",
        "zh": "审阅统计结果",
    },
    "gate.results_interpretation.summary": {
        "en": "Review estimates, confidence intervals, and p-values before proceeding.",
        "zh": "在继续前审阅估计值、置信区间和 P 值。",
    },
    "section_usage": {
        "en": "AI usage & cost",
        "zh": "AI 调用与成本",
    },
    "label_total_invocations": {
        "en": "Total invocations",
        "zh": "总调用次数",
    },
    "label_total_cost": {
        "en": "Total cost",
        "zh": "总成本",
    },
    "label_input_tokens": {
        "en": "Input tokens",
        "zh": "输入 Token",
    },
    "label_output_tokens": {
        "en": "Output tokens",
        "zh": "输出 Token",
    },
    "label_fallbacks": {
        "en": "Fallbacks",
        "zh": "降级次数",
    },
    "label_failures": {
        "en": "Failures",
        "zh": "失败次数",
    },
    "col_task_kind": {
        "en": "Task type",
        "zh": "任务类型",
    },
    "col_invocations": {
        "en": "Calls",
        "zh": "调用数",
    },
    "col_cost_cents": {
        "en": "Cost",
        "zh": "费用",
    },
    "col_tokens": {
        "en": "Tokens",
        "zh": "Token 数",
    },
    # Golden Project demo view
    "view_mode_label": {
        "en": "View mode",
        "zh": "视图模式",
    },
    "view_workflow": {
        "en": "Workflow",
        "zh": "工作流",
    },
    "view_golden_demo": {
        "en": "Golden Project demo",
        "zh": "Golden Project 演示",
    },
    "golden_demo_title": {
        "en": "Golden Project demo data",
        "zh": "Golden Project 演示数据",
    },
    "golden_demo_caption": {
        "en": (
            "Browse the synthetic fixture data and run a one-click demo "
            "of the full analysis pipeline."
        ),
        "zh": "浏览合成测试数据，并一键运行完整分析流水线演示。",
    },
    "golden_demo_load_error": {
        "en": "Could not load golden project fixture: {error}",
        "zh": "无法加载 golden project 测试数据：{error}",
    },
    "golden_section_overview": {
        "en": "Project overview",
        "zh": "项目概览",
    },
    "golden_section_dataset": {
        "en": "Dataset preview",
        "zh": "数据集预览",
    },
    "golden_section_dictionary": {
        "en": "Data dictionary",
        "zh": "数据字典",
    },
    "golden_section_analysis_plan": {
        "en": "Analysis plan",
        "zh": "分析计划",
    },
    "golden_section_methodology": {
        "en": "Methodology findings",
        "zh": "方法学发现",
    },
    "golden_section_literature": {
        "en": "Literature records",
        "zh": "文献记录",
    },
    "golden_label_project_id": {"en": "Project ID", "zh": "项目 ID"},
    "golden_label_title": {"en": "Title", "zh": "标题"},
    "golden_label_study_type": {"en": "Study type", "zh": "研究类型"},
    "golden_label_species": {"en": "Species scope", "zh": "物种范围"},
    "golden_label_guideline": {
        "en": "Reporting guideline",
        "zh": "报告规范",
    },
    "golden_label_synthetic": {
        "en": "Synthetic",
        "zh": "合成数据",
    },
    "golden_label_classification": {
        "en": "Data classification",
        "zh": "数据分级",
    },
    "golden_label_peco": {
        "en": "Research question (PECO)",
        "zh": "研究问题（PECO）",
    },
    "golden_label_population": {"en": "Population", "zh": "人群/对象"},
    "golden_label_exposure": {"en": "Exposure", "zh": "暴露"},
    "golden_label_comparator": {"en": "Comparator", "zh": "对照"},
    "golden_label_outcome": {"en": "Outcome", "zh": "结局"},
    "golden_label_rows": {"en": "Rows", "zh": "行数"},
    "golden_label_columns": {"en": "Columns", "zh": "列数"},
    "col_authors": {"en": "Authors", "zh": "作者"},
    "col_year": {"en": "Year", "zh": "年份"},
    "col_journal": {"en": "Journal", "zh": "期刊"},
    "col_abstract": {"en": "Abstract", "zh": "摘要"},
    "col_tags": {"en": "Tags", "zh": "标签"},
    "col_var_name": {"en": "Variable", "zh": "变量名"},
    "col_var_type": {"en": "Type", "zh": "类型"},
    "col_var_role": {"en": "Role", "zh": "角色"},
    "col_unit": {"en": "Unit", "zh": "单位"},
    "col_missing_code": {"en": "Missing code", "zh": "缺失码"},
    "col_description": {"en": "Description", "zh": "描述"},
    "col_variables": {"en": "Variables", "zh": "变量"},
    "col_exclusion": {"en": "Exclusion criteria", "zh": "排除标准"},
    "col_population": {"en": "Population", "zh": "适用人群"},
    "golden_run_header": {
        "en": "Demo pipeline run",
        "zh": "演示流水线运行",
    },
    "golden_run_description": {
        "en": (
            "Run the full analysis pipeline (project init -> literature "
            "-> evidence -> methodology -> statistics) with all approval "
            "gates auto-approved using mock providers."
        ),
        "zh": (
            "使用 mock 提供者运行完整分析流水线（项目初始化 → 文献 → 证据 → "
            "方法学 → 统计分析），所有审批门自动通过。"
        ),
    },
    "golden_button_run": {
        "en": "Run demo pipeline",
        "zh": "运行演示流水线",
    },
    "golden_button_clear": {
        "en": "Clear demo run",
        "zh": "清除演示运行",
    },
    "golden_run_started": {
        "en": "Demo pipeline finished.",
        "zh": "演示流水线已完成。",
    },
    "golden_run_stage": {
        "en": "Reached stage",
        "zh": "到达阶段",
    },
    "golden_run_no_thread": {
        "en": "No demo run yet. Click the button above to start.",
        "zh": "尚未运行演示。请点击上方按钮启动。",
    },
    "golden_pipeline_results": {
        "en": "Pipeline-derived results",
        "zh": "流水线衍生结果",
    },
    # manuscript / writing views
    "section_manuscript": {
        "en": "Manuscript draft",
        "zh": "稿件草稿",
    },
    "section_claims": {"en": "Claims & support", "zh": "论点与支撑"},
    "section_citations": {"en": "Citations", "zh": "引用"},
    "section_claim_audit": {"en": "Claim audit", "zh": "论点审计"},
    "section_review": {"en": "Reviewer critique", "zh": "审阅批评"},
    "section_revision": {"en": "Revision summary", "zh": "修订摘要"},
    "section_compliance": {"en": "STROBE-Vet compliance", "zh": "STROBE-Vet 合规"},
    "section_export": {"en": "Export package", "zh": "导出包"},
    "label_section_count": {"en": "Sections", "zh": "章节数"},
    "label_claim_count": {"en": "Claims", "zh": "论点数"},
    "label_word_count": {"en": "Words", "zh": "词数"},
    "label_manuscript_version": {"en": "Version", "zh": "版本"},
    "label_manuscript_status": {"en": "Status", "zh": "状态"},
    "label_revision_round": {"en": "Revision round", "zh": "修订轮次"},
    "col_section_type": {"en": "Section", "zh": "章节"},
    "col_claim_type": {"en": "Type", "zh": "类型"},
    "col_claim_text": {"en": "Claim text", "zh": "论点文本"},
    "col_certainty": {"en": "Certainty", "zh": "确信度"},
    "col_has_support": {"en": "Support", "zh": "支撑"},
    "col_support_count": {"en": "Support count", "zh": "支撑数"},
    "col_ref_numbers": {"en": "Numbers cited", "zh": "引用数字"},
    "col_citation_key": {"en": "Citation key", "zh": "引用键"},
    "col_lit_record": {"en": "Literature record", "zh": "文献记录"},
    "col_support_type": {"en": "Support type", "zh": "支撑类型"},
    "col_source": {"en": "Source", "zh": "来源"},
    "col_check": {"en": "Check", "zh": "检查项"},
    "col_audit_result": {"en": "Result", "zh": "结果"},
    "label_audit_passed": {"en": "Audit passed", "zh": "审计通过"},
    "label_audit_errors": {"en": "Errors", "zh": "错误数"},
    "info_no_manuscript": {
        "en": "No manuscript generated yet.",
        "zh": "尚未生成稿件。",
    },
    "info_no_claims": {"en": "No claims yet.", "zh": "暂无论点。"},
    "info_no_citations": {
        "en": "No citations yet.",
        "zh": "暂无引用。",
    },
    "info_no_claim_audit": {
        "en": "No claim audit performed yet.",
        "zh": "尚未执行论点审计。",
    },
    "info_no_review": {
        "en": "No review findings yet.",
        "zh": "暂无审阅发现。",
    },
    "info_no_revision": {
        "en": "No revision performed.",
        "zh": "未执行修订。",
    },
    "info_no_compliance": {
        "en": "No compliance audit yet.",
        "zh": "尚未执行合规审计。",
    },
    "info_no_export": {
        "en": "No export package generated yet.",
        "zh": "尚未生成导出包。",
    },
    "col_location": {"en": "Location", "zh": "位置"},
    "label_review_findings": {
        "en": "Review findings",
        "zh": "审阅发现",
    },
    "label_accepted": {"en": "Accepted", "zh": "采纳"},
    "label_rejected": {"en": "Rejected", "zh": "驳回"},
    "label_deferred": {"en": "Deferred", "zh": "挂起"},
    "label_passed": {"en": "Passed", "zh": "通过"},
    "label_failed": {"en": "Failed", "zh": "失败"},
    "label_not_applicable": {
        "en": "N/A",
        "zh": "不适用",
    },
    "label_needs_review": {
        "en": "Needs review",
        "zh": "待审核",
    },
    "label_export_readiness": {
        "en": "Export readiness",
        "zh": "导出就绪度",
    },
    "col_rule_id": {"en": "Rule ID", "zh": "规则 ID"},
    "col_evidence": {"en": "Evidence", "zh": "证据"},
    "col_filename": {"en": "File", "zh": "文件"},
    "col_media_type": {"en": "Media type", "zh": "媒体类型"},
    "col_components": {"en": "Components", "zh": "组件数"},
    "col_package_uri": {"en": "Package URI", "zh": "包 URI"},
    "label_download_docx": {
        "en": "Download DOCX",
        "zh": "下载 DOCX",
    },
    "label_download_qmd": {
        "en": "Download manuscript (QMD)",
        "zh": "下载稿件（QMD）",
    },
    "label_download_bib": {
        "en": "Download references (BibTeX)",
        "zh": "下载参考文献（BibTeX）",
    },
    "label_download_manifest": {
        "en": "Download manifest (JSON)",
        "zh": "下载清单（JSON）",
    },
    "label_regenerating": {
        "en": "Regenerating export package...",
        "zh": "正在重新生成导出包…",
    },
    "golden_run_description_full": {
        "en": (
            "Run the full end-to-end pipeline (project -> literature -> "
            "evidence -> methodology -> statistics -> writing -> review -> "
            "compliance audit -> sign-off -> DOCX export) with all approval "
            "gates auto-approved using mock providers."
        ),
        "zh": (
            "使用 mock 提供者运行完整端到端流水线（项目 → 文献 → 证据 → "
            "方法学 → 统计 → 写作 → 审阅 → 合规审计 → 签署 → DOCX 导出），"
            "所有审批门自动通过。Fixture 数据将作为流水线输入。"
        ),
    },
    # tab labels for production-ready demo layout
    "tab_data_inputs": {
        "en": "Data inputs",
        "zh": "数据输入",
    },
    "tab_lit_evidence": {
        "en": "Literature & evidence",
        "zh": "文献与证据",
    },
    "tab_method_stats": {
        "en": "Methodology & statistics",
        "zh": "方法学与统计",
    },
    "tab_manuscript": {
        "en": "Manuscript",
        "zh": "稿件",
    },
    "tab_review_compliance": {
        "en": "Review & compliance",
        "zh": "审阅与合规",
    },
    "tab_export": {
        "en": "Export",
        "zh": "导出",
    },
    "golden_data_reference": {
        "en": "Golden project fixture data (pipeline inputs)",
        "zh": "Golden Project 测试数据（流水线输入）",
    },
    "golden_data_reference_hint": {
        "en": (
            "These are the synthetic fixture files that will be fed into "
            "the pipeline when you click Run. The pipeline will process "
            "them through all stages and produce derived outputs."
        ),
        "zh": (
            '这些合成测试数据文件将在点击"运行演示流水线"后作为输入送入流水线。'
            "流水线将经过所有阶段处理这些数据，产出衍生结果。"
        ),
    },
    "pipeline_stage_count": {
        "en": "Stages completed",
        "zh": "已完成阶段",
    },
    "label_download_ai_usage": {
        "en": "Download AI usage (JSON)",
        "zh": "下载 AI 用量（JSON）",
    },
}


def _resolve_language(lang: str | None) -> str:
    if lang is not None:
        if lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {lang}")
        return lang
    # default: read from Streamlit session state, fallback to default language
    try:
        import streamlit as st

        active = st.session_state.get("language")
        if isinstance(active, str) and active in SUPPORTED_LANGUAGES:
            return active
    except Exception:
        # streamlit may be absent during unit tests or before script run
        pass
    return DEFAULT_LANGUAGE


def translate(key: str, *, lang: str | None = None, **kwargs: Any) -> str:
    """Return the localized string for ``key`` in the active language.

    Unknown keys fall back to the key itself so missing translations never crash
    the UI. ``**kwargs`` are applied via ``str.format`` when provided.
    """

    language = _resolve_language(lang)
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(language, entry.get(DEFAULT_LANGUAGE, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def stage_label(stage: str | None, *, lang: str | None = None) -> str:
    """Translate a workflow stage enum value, falling back to the raw value."""

    if not stage:
        return ""
    key = f"stage.{stage}"
    if key not in STRINGS:
        return stage
    return translate(key, lang=lang)


def status_label(status: str | None, *, lang: str | None = None) -> str:
    """Translate a run status value, falling back to the raw value."""

    if not status:
        return ""
    key = f"status.{status}"
    if key not in STRINGS:
        return status
    return translate(key, lang=lang)


def gate_field(gate: str, field: str, *, lang: str | None = None) -> str:
    """Translate an approval gate's dynamic ``title``/``summary`` payload."""

    return translate(f"gate.{gate}.{field}", lang=lang)


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "STRINGS",
    "SUPPORTED_LANGUAGES",
    "gate_field",
    "stage_label",
    "status_label",
    "translate",
]
