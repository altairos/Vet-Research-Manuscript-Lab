"""Visual helpers for the Streamlit workspace."""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.i18n import translate

WORKFLOW_PHASES = (
    (
        "phase_design",
        (
            "project_init",
            "research_question",
            "question_approval",
            "guideline_mapping",
            "protocol_approval",
            "protocol_lock",
        ),
    ),
    (
        "phase_evidence",
        (
            "literature_search",
            "search_approval",
            "screening",
            "evidence_extraction",
            "evidence_audit",
        ),
    ),
    (
        "phase_statistics",
        (
            "methodology_critic",
            "analysis_plan_approval",
            "analysis_plan_lock",
            "statistics_execution",
            "results_approval",
        ),
    ),
    ("phase_writing", ("writing", "claim_audit", "review", "revision")),
    (
        "phase_export",
        ("final_compliance_audit", "final_sign_off", "export", "complete"),
    ),
)


def apply_theme() -> None:
    st.markdown(
        """<style>
        :root {
          --ink:#1d2a26; --muted:#66736e; --line:#dce5e1;
          --brand:#176b57; --brand-soft:#e8f3ee; --surface:#ffffff;
        }
        .stApp { background:#f6f8f7; color:var(--ink); }
        [data-testid="stSidebar"] {
          background:#edf3f0; border-right:1px solid #d6e1dc;
        }
        [data-testid="stSidebar"] * { color:#263832; }
        [data-testid="stSidebar"] .stMarkdown p { color:#65756f; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
          background:#fff; border-color:#c8d6d0; min-height:1.95rem;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] > div * {
          color:#1d2a26 !important; fill:#1d2a26 !important;
        }
        .sidebar-brand {
          padding:.3rem 0 .9rem; margin-bottom:.4rem;
          border-bottom:1px solid #d6e1dc;
        }
        .sidebar-brand strong {
          display:block; color:#155b4b; font-size:1rem; line-height:1.35;
        }
        .sidebar-brand span {
          color:#71807a; font-size:.82rem; line-height:1.5;
        }
        .sidebar-card {
          background:rgba(255,255,255,.72); border:1px solid #d7e2dd;
          border-radius:12px; padding:.8rem .9rem; margin:.35rem 0 .8rem;
        }
        .sidebar-card strong { display:block; margin-bottom:.25rem; }
        .side-step {
          font-size:.86rem; line-height:1.45; margin:.36rem 0; color:#53645e;
        }
        .block-container {
          max-width:1240px; padding-top:3.55rem; padding-bottom:1.2rem;
        }
        [data-testid="stMainBlockContainer"] {
          font-size:15px; line-height:1.55;
        }
        [data-testid="stMainBlockContainer"] p {
          font-size:.94rem; line-height:1.58;
        }
        h1,h2,h3,h4,h5 {
          letter-spacing:-.018em; color:var(--ink); line-height:1.3;
        }
        h1 { font-size:2rem !important; }
        h2 {
          font-size:1.4rem !important; margin-top:.5rem !important;
          margin-bottom:.3rem !important;
        }
        h3 {
          font-size:1.1rem !important; margin-top:.4rem !important;
          margin-bottom:.25rem !important;
        }
        h4 { font-size:1rem !important; margin:.7rem 0 .4rem !important; }
        h5 { font-size:.9rem !important; margin:.6rem 0 .35rem !important; }
        [data-testid="stSidebar"] h4 { font-size:1rem !important; }
        [data-testid="stSidebar"] h5 { font-size:.88rem !important; }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label p {
          font-size:.86rem; line-height:1.48;
        }
        [data-testid="stCaptionContainer"] p {
          font-size:.82rem !important; line-height:1.5 !important;
        }
        .hero {
          padding:1rem 1.15rem; border:1px solid var(--line);
          border-radius:14px; background:linear-gradient(120deg,#fff,#eef6f2);
          box-shadow:0 6px 22px rgba(28,71,59,.05); margin-bottom:.55rem;
        }
        .hero h1 { margin:0 0 .42rem; font-size:2rem !important; }
        .hero p {
          color:var(--muted); max-width:850px; margin:0;
          font-size:.95rem !important; line-height:1.58 !important;
        }
        .eyebrow {
          color:var(--brand); font-size:.7rem; font-weight:800;
          line-height:1.35; letter-spacing:.11em; text-transform:uppercase;
          margin-bottom:.28rem;
        }
        .safety {
          margin-top:.42rem; color:#65746e; font-size:.8rem; line-height:1.45;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap:.35rem; background:#e8eeeb; padding:.28rem;
          border-radius:10px; margin:.55rem 0 .7rem;
        }
        .stTabs [data-baseweb="tab"] {
          min-height:2.25rem; padding:.42rem .8rem; border-radius:8px;
        }
        .stTabs [data-baseweb="tab"] p {
          margin:0 !important; font-size:.88rem !important;
          line-height:1.4 !important;
        }
        .stTabs [aria-selected="true"] {
          background:#fff; color:var(--brand);
          box-shadow:0 1px 5px rgba(32,67,57,.1);
        }
        .stTabs [data-baseweb="tab-highlight"] {
          display:none !important;
        }
        .stTabs [data-baseweb="tab-border"] {
          display:none !important;
        }
        .stTabs [role="tab"][aria-selected="true"]::after {
          display:none !important;
        }
        .stTabs [data-baseweb="tab-panel"] { padding-top:.18rem; }
        [data-testid="stForm"] {
          background:var(--surface); border:1px solid var(--line);
          border-radius:12px; padding:.78rem .85rem .68rem;
        }
        [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap:.3rem; }
        [data-testid="stForm"] label p,
        [data-testid="stWidgetLabel"] p {
          font-size:.86rem; line-height:1.4; font-weight:650;
          color:#41514b; margin-bottom:.18rem;
        }
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div { min-height:2.15rem; }
        textarea { min-height:2.8rem !important; }
        .stButton > button,.stFormSubmitButton > button {
          border-radius:9px; font-weight:700; min-height:2.15rem;
        }
        div[data-testid="stMetric"] {
          background:#fff; border:1px solid var(--line);
          padding:.35rem .55rem; border-radius:9px;
        }
        [data-testid="stExpander"] {
          background:#fff; border-color:var(--line); border-radius:12px;
        }
        .phase-row {
          display:grid; grid-template-columns:repeat(5,1fr);
          gap:6px; margin:.4rem 0 .65rem;
        }
        .phase {
          border:1px solid var(--line); border-radius:10px;
          padding:.48rem .58rem; background:#fff;
        }
        .phase strong { display:block; font-size:.82rem; line-height:1.4; }
        .phase span { color:var(--muted); font-size:.75rem; line-height:1.4; }
        .phase.done { background:#e8f6ef; }
        .phase.active { background:#276d5c; color:#fff; }
        .phase.active span { color:#d9eee7; }
        .approval-card {
          border-left:4px solid #d79346; background:#fff8ef;
          padding:.72rem .88rem; border-radius:10px; margin:.35rem 0 .75rem;
        }
        @media(max-width:800px) {
          .phase-row { grid-template-columns:1fr 1fr; }
          .block-container { padding:2.6rem .9rem .9rem; }
          .hero h1 { font-size:1.55rem !important; }
        }
        </style>""",
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        f"""<section class="hero">
        <div class="eyebrow">{translate("hero_eyebrow")}</div>
        <h1>{translate("app_title")}</h1>
        <p>{translate("hero_description")}</p>
        <div class="safety">{translate("hero_safety")}</div></section>""",
        unsafe_allow_html=True,
    )


def render_phase_tracker(current_stage: str | None) -> None:
    stage = current_stage or "project_init"
    active = next(
        (i for i, (_, values) in enumerate(WORKFLOW_PHASES) if stage in values), 0
    )
    cards = []
    for index, (label_key, _) in enumerate(WORKFLOW_PHASES):
        state = "done" if index < active else "active" if index == active else ""
        caption_key = (
            "phase_done"
            if state == "done"
            else "phase_active"
            if state == "active"
            else "phase_pending"
        )
        cards.append(
            f'<div class="phase {state}"><strong>{index + 1:02d} - '
            f"{translate(label_key)}</strong>"
            f"<span>{translate(caption_key)}</span></div>"
        )
    st.markdown(
        f'<div class="phase-row">{"".join(cards)}</div>', unsafe_allow_html=True
    )


def render_run_metrics(state: dict[str, Any], thread_id: str) -> None:
    cols = st.columns(4)
    cols[0].metric(
        translate("metric_current_stage"),
        str(state.get("current_stage", "-")).replace("_", " "),
    )
    cols[1].metric(
        translate("metric_run_status"),
        str(state.get("run_status", "-")).replace("_", " "),
    )
    cols[2].metric(translate("metric_audit_events"), len(state.get("audit_events", [])))
    cols[3].metric(translate("metric_run_id"), thread_id[:8])
