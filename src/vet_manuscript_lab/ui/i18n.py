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
        "en": "Literature & evidence pipeline: search → screen → extract → audit",
        "zh": "文献与证据流水线：检索 → 筛选 → 提取 → 审计",
    },
    "button_start_full_run": {
        "en": "Start literature & evidence run",
        "zh": "启动文献与证据工作流",
    },
    "workflow_header_full": {
        "en": "Literature & evidence workflow",
        "zh": "文献与证据工作流",
    },
    "success_pipeline_complete": {
        "en": "Pipeline complete: evidence extracted and audited.",
        "zh": "流水线完成：证据已提取并审计。",
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
