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
        "en": "Created project \u201c{name}\u201d",
        "zh": "已创建项目\u201c{name}\u201d",
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
    "col_artifact_role": {
        "en": "Artifact",
        "zh": "产物",
    },
    "col_artifact_type": {
        "en": "Type",
        "zh": "类型",
    },
    "col_artifact_version": {
        "en": "Version",
        "zh": "版本",
    },
    "col_artifact_status": {
        "en": "Status",
        "zh": "状态",
    },
    "artifact_status_in_review": {
        "en": "In review",
        "zh": "待审批",
    },
    "artifact_status_locked": {
        "en": "Locked",
        "zh": "已锁定",
    },
    "artifact_status_approved": {
        "en": "Approved",
        "zh": "已批准",
    },
    "artifact_status_audit_passed": {
        "en": "Audit passed",
        "zh": "审计通过",
    },
    "artifact_status_revised": {
        "en": "revised",
        "zh": "已修订",
    },
    "artifact_status_complete": {
        "en": "complete",
        "zh": "已完成",
    },
    "artifact_status_draft": {
        "en": "Draft",
        "zh": "草稿",
    },
    "artifact_type_research_question": {
        "en": "Research question",
        "zh": "研究问题",
    },
    "artifact_type_protocol": {
        "en": "Protocol",
        "zh": "研究方案",
    },
    "artifact_type_guideline_mapping": {
        "en": "Guideline mapping",
        "zh": "指南映射",
    },
    "artifact_type_search_strategy": {
        "en": "Search strategy",
        "zh": "检索策略",
    },
    "artifact_type_screening_result": {
        "en": "Screening result",
        "zh": "筛选结果",
    },
    "artifact_type_evidence_ledger": {
        "en": "Evidence ledger",
        "zh": "证据台账",
    },
    "artifact_type_citation_audit": {
        "en": "Citation audit",
        "zh": "引文审计",
    },
    "artifact_type_methodology_findings": {
        "en": "Methodology findings",
        "zh": "方法学评估",
    },
    "artifact_type_analysis_plan": {
        "en": "Analysis plan",
        "zh": "分析计划",
    },
    "artifact_type_analysis_result": {
        "en": "Analysis result",
        "zh": "分析结果",
    },
    "artifact_type_argument_spine": {
        "en": "Argument spine",
        "zh": "论证骨架",
    },
    "artifact_type_manuscript": {
        "en": "Manuscript",
        "zh": "稿件",
    },
    "artifact_type_claim_audit": {
        "en": "Claim audit",
        "zh": "论点审计",
    },
    "artifact_type_compliance_audit": {
        "en": "Compliance audit",
        "zh": "合规审计",
    },
    "artifact_type_export_package": {
        "en": "Export package",
        "zh": "导出包",
    },
    "label_no_artifacts": {
        "en": "No artifacts generated yet.",
        "zh": "尚未生成任何产物。",
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
    "stage.argument_spine": {
        "en": "Argument spine",
        "zh": "论证骨架",
    },
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
    # FindingCategory enum values
    "finding_category_unsupported_claim": {
        "en": "unsupported claim",
        "zh": "无支撑论点",
    },
    "finding_category_numeric_mismatch": {
        "en": "numeric mismatch",
        "zh": "数值不一致",
    },
    "finding_category_causal_overreach": {
        "en": "causal overreach",
        "zh": "因果过度推断",
    },
    "finding_category_missing_citation": {
        "en": "missing citation",
        "zh": "缺少引用",
    },
    "finding_category_overstatement": {
        "en": "overstatement",
        "zh": "夸大",
    },
    "finding_category_scope_drift": {
        "en": "scope drift",
        "zh": "范围偏移",
    },
    "finding_category_checklist": {
        "en": "checklist",
        "zh": "清单项",
    },
    # FindingSeverity enum values
    "finding_severity_info": {"en": "info", "zh": "信息"},
    "finding_severity_warning": {
        "en": "warning",
        "zh": "警告",
    },
    "finding_severity_error": {"en": "error", "zh": "错误"},
    # FindingStatus enum values
    "finding_status_open": {"en": "open", "zh": "待处理"},
    "finding_status_accepted": {
        "en": "accepted",
        "zh": "已采纳",
    },
    "finding_status_rejected": {
        "en": "rejected",
        "zh": "已拒绝",
    },
    "finding_status_deferred": {
        "en": "deferred",
        "zh": "已延期",
    },
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
    # section_type enum values
    "section_type_title": {"en": "title", "zh": "标题"},
    "section_type_abstract": {"en": "abstract", "zh": "摘要"},
    "section_type_introduction": {
        "en": "introduction",
        "zh": "引言",
    },
    "section_type_methods": {"en": "methods", "zh": "方法"},
    "section_type_results": {
        "en": "results",
        "zh": "结果",
    },
    "section_type_discussion": {
        "en": "discussion",
        "zh": "讨论",
    },
    "section_type_conclusion": {
        "en": "conclusion",
        "zh": "结论",
    },
    "section_type_references": {
        "en": "references",
        "zh": "参考文献",
    },
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


# Workbench and theme strings
STRINGS.update(
    {
        "sidebar_tagline": {
            "en": "Research design / evidence / statistics / writing",
            "zh": "研究设计 / 证据 / 统计 / 写作",
        },
        "sidebar_workspace": {"en": "Current workspace", "zh": "当前工作区"},
        "sidebar_select_project": {
            "en": "Create or select a project to begin.",
            "zh": "新建或选择项目后开始研究。",
        },
        "sidebar_readiness": {"en": "Preparation", "zh": "准备进度"},
        "sidebar_ready_count": {"en": "{count}/4 ready", "zh": "{count}/4 已就绪"},
        "sidebar_next_steps": {"en": "Next steps", "zh": "后续流程"},
        "sidebar_flow": {
            "en": (
                "Protocol approval -> evidence extraction -> statistics -> "
                "review -> export"
            ),
            "zh": "方案审批 -> 证据提取 -> 统计分析 -> 论文审阅 -> 合规导出",
        },
        "intake_header": {
            "en": "1. Study design and data preparation",
            "zh": "1. 研究设计与数据准备",
        },
        "intake_caption": {
            "en": (
                "Complete the PECO question, literature, and dataset before "
                "starting the approval workflow."
            ),
            "zh": "先完成 PECO 问题、文献和数据集设置，再启动可审批的分析流水线。",
        },
        "tab_research_question": {"en": "Research question", "zh": "研究问题"},
        "tab_zotero_literature": {"en": "Zotero / literature", "zh": "Zotero / 文献"},
        "tab_dataset_variables": {"en": "Dataset & variables", "zh": "数据集与变量"},
        "field_objective": {"en": "Study objective *", "zh": "研究目的 *"},
        "field_population": {"en": "P - Population *", "zh": "P - 研究对象 / 总体 *"},
        "field_exposure": {
            "en": "E - Exposure / intervention *",
            "zh": "E - 暴露 / 干预 *",
        },
        "field_comparator": {"en": "C - Comparator", "zh": "C - 对照"},
        "field_outcome": {"en": "O - Primary outcome *", "zh": "O - 主要结局 *"},
        "field_hypothesis": {"en": "Prespecified hypothesis", "zh": "预设假设"},
        "button_save_question": {"en": "Save research question", "zh": "保存研究问题"},
        "error_required_fields": {
            "en": "Complete all fields marked *.",
            "zh": "请完整填写标记 * 的字段。",
        },
        "success_question_saved": {
            "en": "Research question saved for approval.",
            "zh": "研究问题已保存，将用于问题审批。",
        },
        "field_search_query": {"en": "Search query *", "zh": "检索式 *"},
        "field_databases": {"en": "Databases", "zh": "数据库"},
        "field_date_range": {"en": "Date range", "zh": "日期范围"},
        "button_save_search": {"en": "Save search strategy", "zh": "保存检索策略"},
        "button_reset_search": {
            "en": "Reset to saved",
            "zh": "重置为已保存值",
        },
        "saved_strategy_header": {
            "en": "Saved search strategy",
            "zh": "已保存的检索策略",
        },
        "saved_strategy_empty": {
            "en": "No search strategy saved yet. Fill in the form below and save.",
            "zh": "尚未保存检索策略。请在下方填写并保存。",
        },
        "saved_strategy_databases": {"en": "Databases", "zh": "数据库"},
        "saved_strategy_query": {"en": "Search query", "zh": "检索式"},
        "saved_strategy_date_range": {"en": "Date range", "zh": "日期范围"},
        "edit_strategy_header": {
            "en": "Edit search strategy",
            "zh": "编辑检索策略",
        },
        "error_search_required": {
            "en": "Enter a search query.",
            "zh": "请输入检索式。",
        },
        "success_search_saved": {
            "en": "Search strategy saved.",
            "zh": "检索策略已保存。",
        },
        "button_sync_zotero": {"en": "Sync from Zotero", "zh": "从 Zotero 同步文献"},
        "error_zotero_sync": {
            "en": "Zotero sync failed: {error}",
            "zh": "Zotero 同步失败：{error}",
        },
        "success_zotero_sync": {
            "en": "Fetched {fetched}; created {created}.",
            "zh": "已获取 {fetched} 条，新建 {created} 条。",
        },
        "info_zotero_config": {
            "en": "Configure ZOTERO_API_KEY and ZOTERO_LIBRARY_ID in .env first.",
            "zh": "请先在 .env 配置 ZOTERO_API_KEY 和 ZOTERO_LIBRARY_ID。",
        },
        "manual_entry_header": {"en": "Manual entry", "zh": "手动录入"},
        "field_literature_title": {"en": "Literature title *", "zh": "文献标题 *"},
        "button_add_literature": {"en": "Add literature", "zh": "添加文献"},
        "success_literature_added": {"en": "Literature added.", "zh": "文献已添加。"},
        "col_year": {"en": "Year", "zh": "年份"},
        "field_pdf_record": {"en": "PDF literature record", "zh": "PDF 对应文献"},
        "field_import_pdf": {"en": "Import full-text PDF", "zh": "导入全文 PDF"},
        "button_archive_pdf": {"en": "Archive PDF", "zh": "归档 PDF"},
        "success_pdf_archived": {
            "en": "PDF archived, SHA-256: {hash}...",
            "zh": "PDF 已归档，SHA-256：{hash}...",
        },
        "warning_no_literature": {
            "en": "No literature imported. Sync Zotero or enter a record manually.",
            "zh": "尚未导入文献。可同步 Zotero 或手动录入。",
        },
        "field_upload_csv": {
            "en": "Upload clinical CSV dataset *",
            "zh": "上传 CSV 临床数据集 *",
        },
        "error_empty_csv": {
            "en": "CSV is empty or has no header.",
            "zh": "CSV 为空或缺少表头。",
        },
        "dataset_dimensions": {
            "en": "{rows} rows x {columns} columns: {names}",
            "zh": "{rows} 行 x {columns} 列：{names}",
        },
        "field_outcome_variable": {"en": "Outcome variable *", "zh": "结局变量 *"},
        "field_exposure_variable": {"en": "Exposure variable *", "zh": "暴露变量 *"},
        "field_id_variable": {"en": "ID variable", "zh": "ID 变量"},
        "option_none": {"en": "None", "zh": "无"},
        "button_save_dataset": {"en": "Save dataset settings", "zh": "保存数据集设置"},
        "success_dataset_saved": {
            "en": "Dataset summary and variable roles saved.",
            "zh": "数据集摘要与变量角色已保存。",
        },
        "success_dataset_ready": {
            "en": "Dataset {name} ready with {rows} rows.",
            "zh": "已准备数据集 {name}，{rows} 行。",
        },
        "readiness_search": {"en": "Search strategy", "zh": "检索策略"},
        "readiness_literature": {"en": "Literature", "zh": "文献"},
        "readiness_dataset": {"en": "Dataset", "zh": "数据集"},
        "label_ready": {"en": "Ready", "zh": "已就绪"},
        "label_incomplete": {"en": "Incomplete", "zh": "待完成"},
        "start_approval_header": {"en": "2. Start and approve", "zh": "2. 启动与审批"},
        "start_disabled_help": {
            "en": "Complete the four inputs above first.",
            "zh": "请先完成上方四项输入。",
        },
        "new_project_expander": {
            "en": "+ New research project",
            "zh": "+ 新建研究项目",
        },
        "hero_eyebrow": {
            "en": "Evidence to manuscript - auditable research workspace",
            "zh": "Evidence to manuscript - 可审计科研工作台",
        },
        "hero_description": {
            "en": (
                "A human-approved, traceable workflow for research questions, "
                "evidence, statistics, writing, and STROBE-Vet compliance."
            ),
            "zh": (
                "将研究问题、文献证据、统计分析、论文写作和 STROBE-Vet "
                "合规审查组织为一条可暂停、可追溯、需人工批准的工作流。"
            ),
        },
        "hero_safety": {
            "en": (
                "Research assistance only - scientific judgment, statistics, "
                "ethics, and final sign-off remain the team's responsibility."
            ),
            "zh": "研究辅助工具 - 科学判断、统计解释、伦理与最终签署始终由研究团队负责",
        },
        "phase_design": {"en": "Study design", "zh": "研究设计"},
        "phase_evidence": {"en": "Literature evidence", "zh": "文献证据"},
        "phase_statistics": {"en": "Statistical analysis", "zh": "统计分析"},
        "phase_writing": {"en": "Manuscript writing", "zh": "论文写作"},
        "phase_export": {"en": "Compliance & export", "zh": "合规导出"},
        "phase_done": {"en": "Complete", "zh": "已完成"},
        "phase_active": {"en": "In progress", "zh": "进行中"},
        "phase_pending": {"en": "Pending", "zh": "待开始"},
        "metric_current_stage": {"en": "Current stage", "zh": "当前阶段"},
        "metric_run_status": {"en": "Run status", "zh": "运行状态"},
        "metric_audit_events": {"en": "Audit events", "zh": "审计事件"},
        "metric_run_id": {"en": "Run ID", "zh": "运行 ID"},
    }
)

STRINGS.update(
    {
        # W1: per-finding review disposition UI
        "review_disposition_header": {
            "en": "Dispose review findings",
            "zh": "处置审阅发现",
        },
        "review_disposition_caption": {
            "en": (
                "Accept, reject, or defer each finding. Accepted "
                "findings trigger a revision cycle."
            ),
            "zh": "对每条发现选择采纳、驳回或挂起。采纳的发现将触发修订循环。",
        },
        "decision_accept": {"en": "accept", "zh": "采纳"},
        "decision_reject": {"en": "reject", "zh": "驳回"},
        "decision_defer": {"en": "defer", "zh": "挂起"},
        "field_finding_reason": {"en": "Reason (optional)", "zh": "理由（可选）"},
        "button_submit_review": {
            "en": "Submit all decisions",
            "zh": "提交全部决定",
        },
        "review_no_findings": {
            "en": "No findings to dispose.",
            "zh": "没有需要处置的发现。",
        },
        "label_finding_id": {"en": "Finding", "zh": "发现 ID"},
        # W2: revision diff view
        "section_revision_diff": {
            "en": "Section revision diff",
            "zh": "章节修订对比",
        },
        "col_before": {"en": "Before", "zh": "修改前"},
        "col_after": {"en": "After", "zh": "修改后"},
        "label_resolved_findings": {
            "en": "Resolved findings",
            "zh": "已解决发现",
        },
        "label_no_changes": {"en": "No changes", "zh": "无变化"},
        # W3: claim traceability chain
        "section_traceability": {
            "en": "Claim traceability",
            "zh": "论点追溯链",
        },
        "label_support_type": {"en": "Support type", "zh": "支撑类型"},
        "label_source_evidence": {
            "en": "Evidence source",
            "zh": "证据来源",
        },
        "label_source_result": {
            "en": "Statistical result source",
            "zh": "统计结果来源",
        },
        "label_no_support": {
            "en": "No supporting evidence",
            "zh": "缺少支撑证据",
        },
        "label_span_page": {"en": "Page", "zh": "页码"},
        "label_span_section": {"en": "Section", "zh": "章节"},
        "label_citation_locator": {
            "en": "Locator",
            "zh": "定位符",
        },
        "label_claim_unsupported_warning": {
            "en": (
                "This factual claim lacks supporting evidence and may violate policy."
            ),
            "zh": "该事实性论点缺少支撑证据，可能违反策略。",
        },
        "label_relation": {"en": "Relation", "zh": "关系"},
        "label_audit_status": {"en": "Audit status", "zh": "审计状态"},
        "label_quote_hash": {"en": "Quote hash", "zh": "引用哈希"},
        # claim_type enum values
        "claim_type_factual": {"en": "factual", "zh": "事实性"},
        "claim_type_statistical": {
            "en": "statistical",
            "zh": "统计性",
        },
        "claim_type_interpretation": {
            "en": "interpretation",
            "zh": "解释性",
        },
        "claim_type_recommendation": {
            "en": "recommendation",
            "zh": "建议性",
        },
        # certainty enum values
        "certainty_high": {"en": "high", "zh": "高"},
        "certainty_medium": {"en": "medium", "zh": "中"},
        "certainty_low": {"en": "low", "zh": "低"},
        # support_type enum values
        "support_type_statistical_result": {
            "en": "statistical result",
            "zh": "统计结果",
        },
        "support_type_evidence_item": {
            "en": "evidence item",
            "zh": "证据项",
        },
        "support_type_literature": {
            "en": "literature",
            "zh": "文献",
        },
        # relation enum values
        "relation_supports": {"en": "supports", "zh": "支持"},
        "relation_contradicts": {
            "en": "contradicts",
            "zh": "反对",
        },
        "relation_partially_supports": {
            "en": "partially supports",
            "zh": "部分支持",
        },
        # audit_status enum values
        "audit_status_verified": {
            "en": "verified",
            "zh": "已验证",
        },
        "audit_status_unverified": {
            "en": "unverified",
            "zh": "未验证",
        },
        "audit_status_flagged": {
            "en": "flagged",
            "zh": "已标记",
        },
        "audit_status_pending": {
            "en": "pending",
            "zh": "待审核",
        },
        # additional role labels for new gate types
        "role_reviewer": {"en": "reviewer", "zh": "审阅人"},
        "role_principal_investigator": {
            "en": "principal investigator",
            "zh": "主要研究者",
        },
        "role_corresponding_author": {
            "en": "corresponding author",
            "zh": "通讯作者",
        },
        # W4: reporting guideline mapping
        "section_guideline": {
            "en": "Reporting guideline",
            "zh": "报告规范",
        },
        "label_guideline_type": {
            "en": "Guideline",
            "zh": "规范类型",
        },
        "label_primary_endpoint": {
            "en": "Primary endpoint",
            "zh": "主要终点",
        },
        "label_eligibility": {
            "en": "Eligibility criteria",
            "zh": "纳入排除标准",
        },
        "label_protocol_version": {
            "en": "Protocol version",
            "zh": "方案版本",
        },
        # W5: screening override
        "label_screening_auto": {
            "en": "Auto-screened",
            "zh": "自动筛选",
        },
        "info_screening_hint": {
            "en": "Records are auto-screened by keyword matching. Toggle to override.",
            "zh": "记录由关键词匹配自动筛选。可手动切换覆盖。",
        },
        # W6: statistical provenance
        "section_provenance": {
            "en": "Reproducibility provenance",
            "zh": "可复现性追溯",
        },
        "label_script_hash": {"en": "Script hash", "zh": "脚本哈希"},
        "label_seed": {"en": "Random seed", "zh": "随机种子"},
        "label_plan_ref": {"en": "Plan reference", "zh": "计划引用"},
        "label_dataset_ref": {"en": "Dataset reference", "zh": "数据集引用"},
        "label_environment": {"en": "Environment", "zh": "运行环境"},
        "label_package_versions": {
            "en": "Package versions",
            "zh": "包版本",
        },
        "label_stdout": {"en": "stdout", "zh": "标准输出"},
        "label_stderr": {"en": "stderr", "zh": "标准错误"},
        "label_exit_code": {"en": "Exit code", "zh": "退出码"},
        # W7: figures
        "section_figures": {"en": "Effect plots", "zh": "效应图"},
        "info_no_plot_data": {
            "en": "No numeric results suitable for plotting.",
            "zh": "暂无可绘图的数值结果。",
        },
        # W8: variable editor
        "button_save_variables": {
            "en": "Save variable specs",
            "zh": "保存变量规格",
        },
        "label_var_continuous": {"en": "continuous", "zh": "连续型"},
        "label_var_categorical": {"en": "categorical", "zh": "分类型"},
        "label_var_binary": {"en": "binary", "zh": "二值型"},
        "label_var_ordinal": {"en": "ordinal", "zh": "有序型"},
        # W9: AI disclosure
        "section_ai_disclosure": {
            "en": "AI usage disclosure",
            "zh": "AI 使用披露",
        },
        "info_no_ai_usage": {
            "en": "No AI model usage recorded.",
            "zh": "未记录 AI 模型调用。",
        },
        # W10: approval timeline
        "section_timeline": {
            "en": "Approval & audit timeline",
            "zh": "审批与审计时间线",
        },
        "col_gate": {"en": "Gate", "zh": "审批门"},
        "col_decision": {"en": "Decision", "zh": "决定"},
        "col_reviewer": {"en": "Reviewer", "zh": "审批人"},
        "col_decided_at": {"en": "Decided at", "zh": "决定时间"},
        "col_lock_type": {"en": "Lock type", "zh": "锁定类型"},
        "col_locked_by": {"en": "Locked by", "zh": "锁定者"},
        "col_locked_at": {"en": "Locked at", "zh": "锁定时间"},
        "col_event_type": {"en": "Event", "zh": "事件"},
        "col_stage": {"en": "Stage", "zh": "阶段"},
        "col_occurred_at": {"en": "Occurred at", "zh": "发生时间"},
        "col_message": {"en": "Message", "zh": "消息"},
        "label_no_approvals": {
            "en": "No approvals recorded yet.",
            "zh": "尚未记录审批。",
        },
        # W11: manuscript evidence highlighting
        "label_claim_bound": {
            "en": "Claims in this section",
            "zh": "本章论点",
        },
        "label_claim_status_supported": {
            "en": "Supported",
            "zh": "有支撑",
        },
        "label_claim_status_unsupported": {
            "en": "Unsupported",
            "zh": "无支撑",
        },
        "label_claim_status_hypothesis": {
            "en": "Hypothesis",
            "zh": "假设",
        },
    }
)


STRINGS.update(
    {
        "workspace_actions_header": {
            "en": "Golden Project workspace",
            "zh": "Golden Project 工作台",
        },
        "workspace_actions_caption": {
            "en": (
                "Load the golden fixture into the main intake forms, "
                "or run it end-to-end in the standard workflow view."
            ),
            "zh": (
                "将 Golden fixture 装入主页面表单，或直接在标准工作流视图中端到端运行。"
            ),
        },
        "golden_workspace_load": {
            "en": "Load Golden inputs",
            "zh": "载入 Golden 输入",
        },
        "golden_workspace_run": {
            "en": "Run Golden in workspace",
            "zh": "在工作台运行 Golden",
        },
        "golden_workspace_loading": {
            "en": "Loading Golden Project inputs...",
            "zh": "正在载入 Golden Project 输入...",
        },
        "golden_workspace_running": {
            "en": "Running Golden Project in the main workflow...",
            "zh": "正在主工作流中运行 Golden Project...",
        },
        "golden_workspace_loaded": {
            "en": "Golden inputs loaded into workspace project {id}.",
            "zh": "Golden 输入已载入工作台项目 {id}。",
        },
        "golden_workspace_finished": {
            "en": "Golden workflow finished in workspace project {id}.",
            "zh": "Golden 工作流已在工作台项目 {id} 中运行完成。",
        },
    }
)


STRINGS.update(
    {
        "pending_action_header": {
            "en": "Action required now",
            "zh": "当前就要处理",
        },
        "pending_action_caption": {
            "en": (
                "The pipeline is paused at {stage}. Complete the "
                "approval form below to continue."
            ),
            "zh": "当前流水线停在 {stage}。直接填写下方审批表单并提交即可继续。",
        },
        "pending_action_gate": {
            "en": "Pending approval",
            "zh": "待审批事项",
        },
        "pending_action_next": {
            "en": "Submit to continue toward",
            "zh": "提交后进入",
        },
    }
)


STRINGS.update(
    {
        "button_rename_project": {
            "en": "Rename",
            "zh": "重命名",
        },
        "button_delete_project": {
            "en": "Delete",
            "zh": "删除",
        },
        "field_new_title": {
            "en": "New project title",
            "zh": "新项目标题",
        },
        "confirm_delete_project": {
            "en": (
                "Are you sure? This will permanently delete the "
                "project and all its data."
            ),
            "zh": "确定删除吗？此操作将永久删除该项目及其所有数据。",
        },
        "success_project_renamed": {
            "en": "Project renamed.",
            "zh": "项目已重命名。",
        },
        "success_project_deleted": {
            "en": "Project deleted.",
            "zh": "项目已删除。",
        },
        "sidebar_project_management": {
            "en": "Projects",
            "zh": "项目列表",
        },
        "project_item_owner": {
            "en": "Owner",
            "zh": "负责人",
        },
        "project_item_species": {
            "en": "Species",
            "zh": "物种",
        },
        "sidebar_new_project": {
            "en": "New project",
            "zh": "新建项目",
        },
        "sidebar_production_flow": {
            "en": "Production flow",
            "zh": "生产流程",
        },
        "flow_study_design": {
            "en": "Study design",
            "zh": "研究设计",
        },
        "flow_data_prep": {
            "en": "Data preparation",
            "zh": "数据准备",
        },
        "flow_protocol_approval": {
            "en": "Protocol approval",
            "zh": "方案审批",
        },
        "flow_evidence_extraction": {
            "en": "Evidence extraction",
            "zh": "证据提取",
        },
        "flow_statistical_analysis": {
            "en": "Statistical analysis",
            "zh": "统计分析",
        },
        "flow_manuscript_review": {
            "en": "Manuscript review",
            "zh": "论文审阅",
        },
        "flow_compliance_export": {
            "en": "Compliance export",
            "zh": "合规导出",
        },
        "tab_intake_question": {
            "en": "Research question",
            "zh": "研究问题",
        },
        "tab_intake_data": {
            "en": "Literature & dataset",
            "zh": "文献与数据",
        },
        "tab_pipeline_control": {
            "en": "Pipeline & approval",
            "zh": "流水线与审批",
        },
        "info_start_pipeline": {
            "en": (
                "Start the pipeline from the \u201cPipeline & "
                "approval\u201d section above to see results."
            ),
            "zh": "请先在上方\u201c流水线与审批\u201d区域启动流水线，结果将显示在此。",
        },
        "sidebar_language_header": {
            "en": "Language",
            "zh": "语言",
        },
        "ctx_rename": {
            "en": "Rename",
            "zh": "重命名",
        },
        "ctx_delete": {
            "en": "Delete",
            "zh": "删除",
        },
        "confirm_unsaved_changes": {
            "en": (
                "You have unsaved changes in the current project. "
                "Discard them and switch?"
            ),
            "zh": "当前项目有未保存的修改。是否丢弃并切换项目？",
        },
        "label_discard": {
            "en": "Discard & switch",
            "zh": "丢弃并切换",
        },
        "label_stay": {
            "en": "Stay",
            "zh": "留在此处",
        },
        # -- Phase G: Review Queue tab --------------------------------------
        "tab_review_queue": {
            "en": "Needs review",
            "zh": "待审",
        },
        "rq_header": {
            "en": "Needs Review Queue",
            "zh": "待审队列",
        },
        "rq_empty": {
            "en": "No items require attention.",
            "zh": "暂无需要处理的条目。",
        },
        "rq_total_items": {
            "en": "Total items",
            "zh": "总条目数",
        },
        "rq_critical_items": {
            "en": "Critical",
            "zh": "严重",
        },
        "rq_warning_items": {
            "en": "Warnings",
            "zh": "警告",
        },
        "rq_filter_category": {
            "en": "Filter by category",
            "zh": "按类别筛选",
        },
        "rq_items_showing": {
            "en": "Showing {shown} of {total} items",
            "zh": "显示 {shown} / {total} 条",
        },
        "rq_source_type": {
            "en": "Source type",
            "zh": "来源类型",
        },
        "rq_source_id": {
            "en": "Source ID",
            "zh": "来源 ID",
        },
        "rq_related": {
            "en": "Related",
            "zh": "关联",
        },
        "rq_category_evidence_low_confidence": {
            "en": "Evidence: low confidence",
            "zh": "证据：低置信度",
        },
        "rq_category_evidence_no_span": {
            "en": "Evidence: no source span",
            "zh": "证据：无来源段落",
        },
        "rq_category_evidence_needs_review": {
            "en": "Evidence: needs review",
            "zh": "证据：需人工审核",
        },
        "rq_category_claim_high_risk": {
            "en": "Claim: high risk",
            "zh": "论点：高风险",
        },
        "rq_category_claim_unsupported": {
            "en": "Claim: unsupported",
            "zh": "论点：无支撑",
        },
        "rq_category_methodology_finding": {
            "en": "Methodology finding",
            "zh": "方法学发现",
        },
        "rq_category_review_finding": {
            "en": "Review finding",
            "zh": "审阅发现",
        },
        "rq_category_compliance_finding": {
            "en": "Compliance finding",
            "zh": "合规发现",
        },
        "rq_category_section_over_limit": {
            "en": "Section: over word limit",
            "zh": "章节：超字数限制",
        },
        "rq_category_exploratory_in_abstract": {
            "en": "Exploratory result in Abstract",
            "zh": "探索性结果进入摘要",
        },
        "rq_category_other": {
            "en": "Other",
            "zh": "其他",
        },
        "rq_detail_evidence_no_span": {
            "en": "This evidence item has no linked source span.",
            "zh": "此证据条目未关联来源段落。",
        },
        "rq_detail_evidence_missing_span": {
            "en": "One or more referenced spans are missing.",
            "zh": "引用的来源段落缺失。",
        },
        "rq_detail_evidence_needs_review": {
            "en": "Flagged for human review.",
            "zh": "已标记需人工审核。",
        },
        "rq_detail_evidence_low_confidence": {
            "en": "Extraction confidence is low.",
            "zh": "抽取置信度较低。",
        },
        "rq_detail_claim_unsupported": {
            "en": "Factual claim has no supporting evidence or result.",
            "zh": "事实性论点缺少支撑证据或结果。",
        },
        "rq_detail_claim_hypothesis_abstract": {
            "en": "Hypothesis-type claim appears in the Abstract.",
            "zh": "假设性论点出现在摘要中。",
        },
        "rq_detail_claim_overcertain": {
            "en": "High-certainty claim without support.",
            "zh": "高确定性论点缺少支撑。",
        },
        "rq_detail_section_over_limit": {
            "en": "Section exceeds the recommended word limit.",
            "zh": "章节超出建议字数限制。",
        },
        # Provenance Inspector
        "rq_provenance_header": {
            "en": "Provenance Inspector",
            "zh": "溯源检视器",
        },
        "rq_provenance_select_type": {
            "en": "Trace from",
            "zh": "从何处溯源",
        },
        "rq_type_claim": {
            "en": "Claim",
            "zh": "论点",
        },
        "rq_type_evidence": {
            "en": "Evidence item",
            "zh": "证据条目",
        },
        "rq_type_result": {
            "en": "Statistical result",
            "zh": "统计结果",
        },
        "rq_provenance_select_claim": {
            "en": "Select a claim",
            "zh": "选择论点",
        },
        "rq_provenance_select_evidence": {
            "en": "Select an evidence item",
            "zh": "选择证据条目",
        },
        "rq_provenance_select_result": {
            "en": "Select a statistical result",
            "zh": "选择统计结果",
        },
        "rq_provenance_no_claims": {
            "en": "No claims available.",
            "zh": "无可用论点。",
        },
        "rq_provenance_no_evidence": {
            "en": "No evidence items available.",
            "zh": "无可用证据条目。",
        },
        "rq_provenance_no_results": {
            "en": "No statistical results available.",
            "zh": "无可用统计结果。",
        },
        "rq_provenance_no_support": {
            "en": "This claim has no support links.",
            "zh": "此论点无支撑链接。",
        },
        "rq_provenance_support_chain": {
            "en": "Support chain",
            "zh": "支撑链",
        },
        "rq_provenance_span_missing": {
            "en": "span not found",
            "zh": "段落缺失",
        },
        "rq_provenance_analysis_run": {
            "en": "Analysis run",
            "zh": "分析运行",
        },
        "rq_provenance_status": {
            "en": "status",
            "zh": "状态",
        },
        "rq_provenance_claims_using": {
            "en": "Claims referencing this object",
            "zh": "引用此对象的论点",
        },
        "rq_evidence_type": {
            "en": "Evidence type",
            "zh": "证据类型",
        },
        "rq_analysis_class": {
            "en": "Analysis class",
            "zh": "分析类别",
        },
        "rq_exploratory_result_flag": {
            "en": "This result is exploratory; do not present as confirmatory.",
            "zh": "此结果为探索性分析，不可作为确证性结论呈现。",
        },
        "rq_run_id": {
            "en": "Run ID",
            "zh": "运行 ID",
        },
        "rq_reproducible": {
            "en": "Reproducible",
            "zh": "可复现",
        },
    }
)


# ---------------------------------------------------------------------------
# Phase H3: Clinical-research-workbench UI strings
# ---------------------------------------------------------------------------
STRINGS.update(
    {
        # -- Five top-level workspaces ---------------------------------------
        "workspace_dashboard": {
            "en": "Dashboard",
            "zh": "仪表盘",
        },
        "workspace_setup": {
            "en": "Study Setup",
            "zh": "研究设置",
        },
        "workspace_evidence": {
            "en": "Evidence & Analysis",
            "zh": "证据与分析",
        },
        "workspace_manuscript": {
            "en": "Manuscript",
            "zh": "稿件",
        },
        "workspace_audit": {
            "en": "Audit & Export",
            "zh": "审计与导出",
        },
        # -- Dashboard --------------------------------------------------------
        "dash_project_status": {
            "en": "Project status",
            "zh": "项目状态",
        },
        "dash_next_action": {
            "en": "Next action",
            "zh": "下一步动作",
        },
        "dash_next_stage": {
            "en": "Submit to continue toward",
            "zh": "提交后进入",
        },
        "dash_risk_summary": {
            "en": "Risk summary",
            "zh": "风险摘要",
        },
        "dash_cost_summary": {
            "en": "Cost summary",
            "zh": "成本摘要",
        },
        "dash_recent_artifacts": {
            "en": "Recent artifacts",
            "zh": "最近产物",
        },
        "dash_audit_log": {
            "en": "Audit log",
            "zh": "审计日志",
        },
        "dash_approval_needed": {
            "en": "Approval required",
            "zh": "需要审批",
        },
        "dash_artifact": {
            "en": "Artifact",
            "zh": "产物",
        },
        "dash_no_thread": {
            "en": "No pipeline run yet. Start one to see results here.",
            "zh": "尚未运行流水线。启动后结果将显示在此。",
        },
        "dash_continue_pipeline": {
            "en": "Continue pipeline",
            "zh": "继续流水线",
        },
        "dash_pipeline_idle": {
            "en": "Pipeline is idle. Set up your study and start the analysis.",
            "zh": "流水线尚未启动。请完成研究设置并启动分析。",
        },
        "dash_risk_none": {
            "en": "No risks detected.",
            "zh": "未检测到风险。",
        },
        "dash_open_review_queue": {
            "en": "Open review queue",
            "zh": "打开待审队列",
        },
        # -- Onboarding / empty state ----------------------------------------
        "onboard_welcome": {
            "en": "Welcome to Vet Research Manuscript Lab",
            "zh": "欢迎使用兽医科研稿件实验室",
        },
        "onboard_golden_title": {
            "en": "Try the Golden Project",
            "zh": "体验 Golden Project",
        },
        "onboard_golden_body": {
            "en": (
                "Use built-in synthetic data to experience the full pipeline "
                "in one click."
            ),
            "zh": "使用内置合成数据，一键体验完整流程。",
        },
        "onboard_golden_button": {
            "en": "Run Golden Project",
            "zh": "运行 Golden Project",
        },
        "onboard_new_title": {
            "en": "Create a new project",
            "zh": "创建新项目",
        },
        "onboard_new_body": {
            "en": "Start from a research question, case data, and Zotero library.",
            "zh": "从研究问题、病例数据和 Zotero 文献库开始。",
        },
        "onboard_new_button": {
            "en": "New project",
            "zh": "新建项目",
        },
        "onboard_import_title": {
            "en": "Import existing project",
            "zh": "导入已有项目",
        },
        "onboard_import_body": {
            "en": "Load a previous artifact / provenance package.",
            "zh": "载入已有的产物/溯源包。",
        },
        "onboard_import_button": {
            "en": "Import project",
            "zh": "导入项目",
        },
        # -- Collapsible details / technical noise ---------------------------
        "show_details": {
            "en": "Show details",
            "zh": "展开详情",
        },
        "hide_details": {
            "en": "Hide details",
            "zh": "收起详情",
        },
        "show_provenance_details": {
            "en": "Show provenance details",
            "zh": "展开溯源详情",
        },
        "show_technical_info": {
            "en": "Technical information",
            "zh": "技术信息",
        },
        "copy": {
            "en": "Copy",
            "zh": "复制",
        },
        "copy_to_clipboard": {
            "en": "Copy to clipboard",
            "zh": "复制到剪贴板",
        },
        "label_copied": {
            "en": "Copied",
            "zh": "已复制",
        },
        # -- Cost / budget ----------------------------------------------------
        "dash_budget": {
            "en": "Budget",
            "zh": "预算",
        },
        "dash_budget_used": {
            "en": "{used} / {budget}",
            "zh": "{used} / {budget}",
        },
        "dash_no_cost": {
            "en": "No cost recorded yet.",
            "zh": "尚无成本记录。",
        },
        # -- Provenance inspector enhanced ------------------------------------
        "rq_provenance_claim_card": {
            "en": "Claim",
            "zh": "论点",
        },
        "rq_provenance_evidence_card": {
            "en": "Evidence item",
            "zh": "证据条目",
        },
        "rq_provenance_result_card": {
            "en": "Statistical result",
            "zh": "统计结果",
        },
        "rq_provenance_span_card": {
            "en": "Source span",
            "zh": "来源段落",
        },
        "rq_provenance_analysis_card": {
            "en": "Analysis run",
            "zh": "分析运行",
        },
        "rq_provenance_no_analysis": {
            "en": "No analysis run recorded.",
            "zh": "未记录分析运行。",
        },
        # -- Audit event types -----------------------------------------------
        "audit_stage_started": {
            "en": "Stage started",
            "zh": "阶段开始",
        },
        "audit_stage_completed": {
            "en": "Stage completed",
            "zh": "阶段完成",
        },
        "audit_gate_approved": {
            "en": "Gate approved",
            "zh": "审批通过",
        },
        "audit_gate_rejected": {
            "en": "Gate rejected",
            "zh": "审批驳回",
        },
        "audit_artifact_created": {
            "en": "Artifact created",
            "zh": "产物创建",
        },
        "audit_artifact_locked": {
            "en": "Artifact locked",
            "zh": "产物锁定",
        },
        "audit_run_started": {
            "en": "Run started",
            "zh": "运行开始",
        },
        "audit_run_completed": {
            "en": "Run completed",
            "zh": "运行完成",
        },
        # -- Additional labels referenced by dashboard ------------------------
        "label_argument_spine": {
            "en": "Argument spine",
            "zh": "论证主线",
        },
        "label_analysis_run": {
            "en": "Analysis run",
            "zh": "分析运行",
        },
        "section_revision": {
            "en": "Revision",
            "zh": "修订",
        },
        "section_search_strategy": {
            "en": "Search strategy",
            "zh": "检索策略",
        },
        "label_protocol_version": {
            "en": "Protocol",
            "zh": "研究方案",
        },
        # -- Dashboard product polish ----------------------------------------
        "project_header_type": {
            "en": "Study type",
            "zh": "研究类型",
        },
        "project_header_guideline": {
            "en": "Reporting guideline",
            "zh": "报告规范",
        },
        "project_header_status": {
            "en": "Status",
            "zh": "状态",
        },
        # Next Action hero buttons
        "button_view_details": {
            "en": "View details",
            "zh": "查看详情",
        },
        "button_request_changes": {
            "en": "Request changes",
            "zh": "要求修改",
        },
        "button_approve_continue": {
            "en": "Approve & continue",
            "zh": "批准并继续",
        },
        "button_open_approval": {
            "en": "Open approval",
            "zh": "打开审批",
        },
        "button_start_pipeline": {
            "en": "Run to next approval",
            "zh": "运行至下一审批点",
        },
        # Next Action lock label
        "next_action_lock_label": {
            "en": "Will be locked upon approval:",
            "zh": "提交后将锁定：",
        },
        # Readiness compact header
        "readiness_header": {
            "en": "Readiness",
            "zh": "准备进度",
        },
        # Artifacts empty state
        "artifacts_empty_title": {
            "en": "No artifacts yet",
            "zh": "暂无产物",
        },
        "artifacts_empty_body": {
            "en": "Artifacts will appear here after the first approval.",
            "zh": "首次审批通过后，产物将在此显示。",
        },
        # Cost compact (right sidebar)
        "label_budget_total": {
            "en": "Budget",
            "zh": "预算",
        },
    }
)


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


# Map approval-gate short names to the workflow-stage label that best
# describes the paused state shown to the user.
_GATE_TO_STAGE: dict[str, str] = {
    "question": "question_approval",
    "protocol": "protocol_approval",
    "search_strategy": "search_approval",
    "analysis_plan": "analysis_plan_approval",
    "results_interpretation": "results_approval",
    "argument_spine": "argument_spine",
    "review": "review",
    "final_sign_off": "final_sign_off",
}


def gate_stage_label(gate: str | None, *, lang: str | None = None) -> str:
    """Return a human-readable stage name for an approval *gate*.

    Gate short names (e.g. ``"question"``, ``"protocol"``) differ from the
    workflow-stage enum values used in :func:`stage_label`.  This helper bridges
    that gap so the UI never shows a raw key like ``"question"``.
    """

    if not gate:
        return ""
    stage = _GATE_TO_STAGE.get(gate, gate)
    return stage_label(stage, lang=lang)


def gate_field(gate: str, field: str, *, lang: str | None = None) -> str:
    """Translate an approval gate's dynamic ``title``/``summary`` payload."""

    return translate(f"gate.{gate}.{field}", lang=lang)


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "STRINGS",
    "SUPPORTED_LANGUAGES",
    "gate_field",
    "gate_stage_label",
    "stage_label",
    "status_label",
    "translate",
]
