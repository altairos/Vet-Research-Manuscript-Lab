"""Visual helpers for the Streamlit workspace.

This module owns the **design system**: colour tokens, typography,
card / badge / metric CSS primitives, and high-level layout helpers
(hero banner, phase tracker, auto-grow textareas).

All user-facing visual rules should be expressed here so individual tab
modules can focus on content rather than ad-hoc styling.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.i18n import (
    stage_label,
    status_label,
    translate,
)

# ---------------------------------------------------------------------------
# Design tokens (single source of truth)
# ---------------------------------------------------------------------------

THEME: dict[str, str] = {
    "bg": "#F6F7F9",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF2F5",
    "text": "#182230",
    "muted": "#667085",
    "border": "#D0D5DD",
    "primary": "#244C5A",
    "primary_soft": "#E6F0F2",
    "accent": "#3E6F5E",
    "warning": "#B54708",
    "warning_soft": "#FFF7E6",
    "danger": "#B42318",
    "danger_soft": "#FEF3F2",
    "success": "#16784E",
    "success_soft": "#E7F6EF",
}

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
    """Inject the global design-system CSS.

    All visual rules — colours, fonts, card / badge / metric primitives,
    sidebar styling, tab styling — live here so tab modules never emit
    raw ``<style>`` blocks.
    """

    t = THEME
    st.markdown(
        f"""<style>
        /* ---- CSS custom properties from THEME tokens ---- */
        :root {{
          --vrl-bg:{t['bg']}; --vrl-surface:{t['surface']};
          --vrl-surface-alt:{t['surface_alt']};
          --vrl-text:{t['text']}; --vrl-muted:{t['muted']};
          --vrl-border:{t['border']};
          --vrl-primary:{t['primary']}; --vrl-primary-soft:{t['primary_soft']};
          --vrl-accent:{t['accent']};
          --vrl-warning:{t['warning']}; --vrl-warning-soft:{t['warning_soft']};
          --vrl-danger:{t['danger']}; --vrl-danger-soft:{t['danger_soft']};
          --vrl-success:{t['success']}; --vrl-success-soft:{t['success_soft']};
          --vrl-shadow-sm:0 1px 2px rgba(16,24,40,.06);
          --vrl-shadow-md:0 8px 24px rgba(16,24,40,.08);
          --vrl-radius:8px;
          --vrl-space-1:.25rem;
          --vrl-space-2:.5rem;
          --vrl-space-3:.75rem;
          --vrl-space-4:1rem;
          --vrl-space-5:1.25rem;
          --vrl-space-6:1.5rem;
        }}

        /* ---- Typography ---- */
        * {{
          font-family: 'Inter','Source Sans 3','IBM Plex Sans',
          'Noto Sans SC','Source Han Sans','Microsoft YaHei',
          system-ui, sans-serif !important;
        }}
        /* Restore icon font (global * rule above overrides it) */
        [data-testid="stIconMaterial"] {{
          font-family: 'Material Symbols Rounded', 'Material Icons' !important;
        }}
        /* Material Icons: let Streamlit handle natively, don't override font */
        .stApp {{
          background:
            linear-gradient(180deg,#fbfcfd 0%,var(--vrl-bg) 220px);
          color:var(--vrl-text);
        }}

        /* ---- Layout container ---- */
        .block-container {{
          max-width:1480px;
          padding:1.125rem 1.75rem 3rem;
        }}
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {{
          gap:var(--vrl-space-4);
        }}
        [data-testid="stMainBlockContainer"] {{
          font-size:15px; line-height:1.55;
          overflow-wrap: anywhere; word-break: break-word;
        }}
        [data-testid="stMainBlockContainer"] p {{
          font-size:.94rem; line-height:1.58;
        }}
        [data-testid="stElementContainer"] {{
          margin-bottom:.35rem;
        }}
        [data-testid="stHorizontalBlock"] {{
          gap:1rem;
        }}
        [data-testid="stVerticalBlock"] {{
          gap:.85rem;
        }}

        /* ---- Headings ---- */
        h1,h2,h3,h4,h5 {{
          letter-spacing:0; color:var(--vrl-text); line-height:1.3;
        }}
        h1 {{ font-size:2rem !important; }}
        h2 {{
          font-size:1.4rem !important; margin-top:.75rem !important;
          margin-bottom:.5rem !important;
        }}
        h3 {{
          font-size:1.1rem !important; margin-top:.65rem !important;
          margin-bottom:.4rem !important;
        }}
        h4 {{ font-size:1rem !important; margin:.8rem 0 .5rem !important; }}
        h5 {{ font-size:.9rem !important; margin:.7rem 0 .45rem !important; }}

        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {{
          background:#F8FAFC; border-right:1px solid var(--vrl-border);
        }}
        [data-testid="stSidebar"] * {{ color:var(--vrl-text); }}
        [data-testid="stSidebar"] .stMarkdown p {{ color:var(--vrl-muted); }}
        [data-testid="stSidebar"] h4 {{
          font-size:.95rem !important; margin:.6rem 0 .35rem !important;
        }}
        [data-testid="stSidebar"] h5 {{
          font-size:.85rem !important; margin:.5rem 0 .3rem !important;
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label p {{
          font-size:.86rem; line-height:1.48;
        }}
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
          font-size:.84rem; margin-bottom:.12rem;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] h4,
        [data-testid="stSidebar"] .sidebar-section-header {{
          font-size:.95rem; font-weight:700; margin:.6rem 0 .35rem;
        }}
        .sidebar-brand {{
          padding:.55rem 0 1.1rem; margin-bottom:.5rem;
        }}
        .sidebar-brand strong {{
          display:block; color:var(--vrl-text); font-size:1rem; line-height:1.35;
          letter-spacing:.01em;
        }}
        .sidebar-brand span {{
          color:var(--vrl-muted); font-size:.82rem; line-height:1.5;
        }}
        .sidebar-card {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          border-radius:var(--vrl-radius); padding:1rem; margin:.5rem 0 1rem;
          box-shadow:var(--vrl-shadow-sm);
        }}
        .sidebar-card strong {{ display:block; margin-bottom:.25rem; }}
        .side-step {{
          font-size:.86rem; line-height:1.45; margin:.36rem 0;
          color:var(--vrl-muted);
        }}

        /* ---- Project list items ---- */
        .project-list-item {{
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          padding:.8rem .85rem; margin-bottom:.6rem; background:var(--vrl-surface);
          box-shadow:var(--vrl-shadow-sm); cursor:pointer;
          transition:border-color .12s, box-shadow .12s,
            transform .12s, background .12s;
        }}
        .project-list-item:hover {{
          border-color:#98A2B3; box-shadow:var(--vrl-shadow-md);
          transform:translateY(-1px);
        }}
        .project-list-item.active {{
          border-color:var(--vrl-primary); background:var(--vrl-primary-soft);
          box-shadow:0 0 0 1px rgba(36,76,90,.12), var(--vrl-shadow-sm);
        }}
        .project-list-item strong {{
          display:block; font-size:.88rem; color:var(--vrl-text);
        }}
        .project-list-item span {{ font-size:.78rem; color:var(--vrl-muted); }}

        /* ---- Context menu ---- */
        .ctx-menu-item {{
          padding:8px 18px; cursor:pointer; font-size:.86rem;
          color:#333; transition:background .12s;
        }}
        .ctx-menu-item:hover {{ background:var(--vrl-primary-soft); }}
        .ctx-menu-item.danger {{ color:var(--vrl-danger); }}
        .ctx-menu-item.danger:hover {{ background:var(--vrl-danger-soft); }}
        .ctx-sep {{ height:1px; background:#e0e5e2; margin:2px 0; }}

        /* ---- Caption ---- */
        [data-testid="stCaptionContainer"] p {{
          font-size:.82rem !important; line-height:1.5 !important;
        }}

        /* ---- Pipeline / next-action panel ---- */
        .pipeline-bar-header {{
          margin-bottom:.75rem; padding-bottom:.6rem;
          border-bottom:1px solid var(--vrl-border);
          font-size:.95rem; color:var(--vrl-primary);
          white-space: normal; word-break: break-word;
          line-height:1.4;
        }}
        .pipeline-bar-header strong {{ font-size:1rem; }}
        [data-testid="stVerticalBlockBorderContainer"]
          [data-testid="stVerticalBlock"] {{
          gap:.9rem;
        }}
        [data-testid="stVerticalBlockBorderContainer"] p {{
          line-height:1.55 !important;
        }}
        [data-testid="stVerticalBlockBorderContainer"]
          [data-testid="stMetric"] {{
          margin-bottom:.5rem;
        }}
        [data-testid="stVerticalBlockBorderContainer"] .phase-row {{
          margin:.7rem 0 .9rem;
        }}
        [data-testid="stVerticalBlockBorderContainer"]
          [data-testid="stExpander"] {{
          margin-top:.6rem;
        }}

        /* ---- Hero banner ---- */
        .hero {{
          padding:1.4rem 1.6rem; border:1px solid var(--vrl-border);
          border-radius:var(--vrl-radius);
          background:linear-gradient(135deg,var(--vrl-surface),#F2F7F8);
          box-shadow:var(--vrl-shadow-sm);
          margin-bottom:1.25rem;
        }}
        .hero h1 {{ margin:0 0 .42rem; font-size:2rem !important; }}
        .hero p {{
          color:var(--vrl-muted); max-width:850px; margin:0;
          font-size:.95rem !important; line-height:1.58 !important;
        }}
        .eyebrow {{
          color:var(--vrl-primary); font-size:.7rem; font-weight:800;
          line-height:1.35; letter-spacing:.11em; text-transform:uppercase;
          margin-bottom:.28rem;
        }}
        .safety {{
          margin-top:.42rem; color:var(--vrl-muted);
          font-size:.8rem; line-height:1.45;
        }}

        /* ---- Tabs ---- */
        .stTabs [data-baseweb="tab-list"] {{
          gap:.25rem; background:#EAECF0; padding:.25rem;
          border-radius:var(--vrl-radius); margin:.75rem 0 1rem;
          border:1px solid #D0D5DD;
        }}
        .stTabs [data-baseweb="tab"] {{
          min-height:2.35rem; padding:.5rem 1.15rem; border-radius:6px;
        }}
        .stTabs [data-baseweb="tab"] p {{
          margin:0 !important; font-size:.88rem !important;
          line-height:1.4 !important;
        }}
        .stTabs [aria-selected="true"] {{
          background:var(--vrl-surface); color:var(--vrl-primary);
          box-shadow:var(--vrl-shadow-sm);
        }}
        .stTabs [data-baseweb="tab-highlight"] {{ display:none !important; }}
        .stTabs [data-baseweb="tab-border"] {{ display:none !important; }}
        .stTabs [role="tab"][aria-selected="true"]::after {{
          display:none !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{ padding-top:.18rem; }}

        /* ---- Forms & inputs ---- */
        [data-testid="stForm"] {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          border-radius:var(--vrl-radius); padding:1.15rem;
          box-shadow:var(--vrl-shadow-sm);
        }}
        [data-testid="stForm"] [data-testid="stVerticalBlock"] {{
          gap:.75rem;
        }}
        [data-testid="stForm"] [data-testid="stHorizontalBlock"] {{
          gap:1rem;
        }}
        [data-testid="stForm"] label p,
        [data-testid="stWidgetLabel"] p {{
          font-size:.86rem; line-height:1.4; font-weight:650;
          color:#41514b; margin-bottom:.3rem;
        }}
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div {{ min-height:2.35rem; }}
        [data-baseweb="input"] input,
        [data-baseweb="select"] input {{
          padding-top:.42rem !important; padding-bottom:.42rem !important;
        }}
        textarea {{
          min-height:3.25rem !important;
          padding:.65rem .75rem !important;
          line-height:1.5 !important;
        }}
        [data-baseweb="input"]:focus-within,
        [data-baseweb="select"]:focus-within,
        [data-baseweb="textarea"]:focus-within,
        textarea:focus {{
          border-color:var(--vrl-primary) !important;
          box-shadow:0 0 0 3px rgba(36,76,90,.12) !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] [data-baseweb="select"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
          border:1px solid var(--vrl-border) !important;
          border-radius:var(--vrl-radius) !important;
          background:var(--vrl-surface) !important;
        }}
        [data-testid="stSidebar"] textarea {{
          border:1px solid var(--vrl-border) !important;
          border-radius:var(--vrl-radius) !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
          min-height:1.95rem;
        }}

        /* ---- Buttons ---- */
        .stButton > button,.stFormSubmitButton > button {{
          border-radius:var(--vrl-radius); font-weight:650; min-height:2.35rem;
          padding:.45rem .9rem;
          border:1px solid var(--vrl-border);
          transition:background .12s, border-color .12s,
            box-shadow .12s, transform .12s;
        }}

        .stButton > button:hover,.stFormSubmitButton > button:hover {{
          border-color:#98A2B3; box-shadow:var(--vrl-shadow-sm);
          transform:translateY(-1px);
        }}
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {{
          background:var(--vrl-primary); border-color:var(--vrl-primary);
          color:#fff;
        }}

        /* ---- Metric cards (upgraded) ---- */
        div[data-testid="stMetric"] {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          padding:1rem; border-radius:var(--vrl-radius);
          box-shadow:var(--vrl-shadow-sm);
        }}

        [data-testid="stMetricLabel"] p {{
          color:var(--vrl-muted); font-size:.78rem !important;
        }}
        [data-testid="stMetricValue"] {{
          color:var(--vrl-text); font-size:1.22rem !important;
          font-weight:700;
        }}

        /* ---- Expander ---- */
        [data-testid="stExpander"] {{
          background:var(--vrl-surface); border-color:var(--vrl-border);
          border-radius:var(--vrl-radius); box-shadow:var(--vrl-shadow-sm);
        }}

        /* ---- Streamlit status elements ---- */
        [data-testid="stAlert"] {{
          border-radius:var(--vrl-radius); border:1px solid var(--vrl-border);
          box-shadow:var(--vrl-shadow-sm);
          padding:.85rem 1rem;
        }}
        [data-testid="stAlert"] p {{
          line-height:1.5 !important;
        }}
        [data-testid="stExpander"] details > summary {{
          padding:.8rem 1rem !important;
        }}
        [data-testid="stExpander"] details div[data-testid="stVerticalBlock"] {{
          gap:.75rem;
          padding:.15rem .35rem .35rem;
        }}
        [data-testid="stFileUploader"] section {{
          border-radius:var(--vrl-radius);
          border-color:var(--vrl-border);
          padding:1rem;
          background:#FBFCFD;
        }}
        [data-testid="stDataEditor"] {{
          border-radius:var(--vrl-radius);
          overflow:hidden;
        }}

        /* ---- DataFrames ---- */
        [data-testid="stDataFrame"] {{
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          overflow:hidden; box-shadow:var(--vrl-shadow-sm);
          background:var(--vrl-surface);
        }}
        .vrl-html-table {{
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          overflow:hidden; box-shadow:var(--vrl-shadow-sm);
          background:var(--vrl-surface); margin-bottom:1rem;
        }}
        .vrl-html-table table {{
          width:100%; border-collapse:collapse; font-size:.86rem;
        }}
        .vrl-html-table th {{
          text-align:left; color:var(--vrl-muted); background:#F8FAFC;
          padding:.75rem .9rem; border-bottom:1px solid var(--vrl-border);
          font-weight:750;
        }}
        .vrl-html-table td {{
          padding:.75rem .9rem; border-bottom:1px solid #EAECF0;
          color:var(--vrl-text); vertical-align:top;
        }}
        .vrl-html-table tr:last-child td {{ border-bottom:0; }}

        /* ---- Phase tracker ---- */
        .phase-row {{
          display:grid;
          grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));
          gap:.5rem; margin:.55rem 0 .85rem;
        }}
        .phase {{
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          padding:.65rem .7rem; background:var(--vrl-surface);
        }}
        .phase strong {{ display:block; font-size:.82rem; line-height:1.4; }}
        .phase span {{ color:var(--vrl-muted); font-size:.75rem; line-height:1.4; }}
        .phase.done {{ background:var(--vrl-success-soft); }}
        .phase.active {{
          background:var(--vrl-primary); color:#fff;
        }}
        .phase.active span {{ color:rgba(255,255,255,.8); }}

        /* ---- Approval card ---- */
        .approval-card {{
          border-left:4px solid var(--vrl-warning);
          background:var(--vrl-warning-soft);
          padding:1rem 1.05rem; border-radius:var(--vrl-radius);
          margin:.5rem 0 1rem;
          box-shadow:var(--vrl-shadow-sm);
        }}

        /* ===== DESIGN-SYSTEM PRIMITIVES (.vrl-*) ===== */

        .vrl-card {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          border-radius:var(--vrl-radius); padding:1.15rem 1.25rem;
          box-shadow:var(--vrl-shadow-sm); margin-bottom:1rem;
        }}
        .vrl-card.success {{ border-left:4px solid var(--vrl-success); }}
        .vrl-card.warning {{ border-left:4px solid var(--vrl-warning); }}
        .vrl-card.danger {{ border-left:4px solid var(--vrl-danger); }}
        .vrl-card.primary {{ border-left:4px solid var(--vrl-primary); }}
        .vrl-card.accent {{ border-left:4px solid var(--vrl-accent); }}

        .vrl-eyebrow {{
          font-size:.75rem; letter-spacing:.08em; text-transform:uppercase;
          color:var(--vrl-muted); margin-bottom:.25rem; font-weight:600;
        }}
        .vrl-title {{
          font-size:1.15rem; font-weight:650; color:var(--vrl-text);
          margin-bottom:.35rem;
        }}
        .vrl-muted {{ color:var(--vrl-muted); font-size:.9rem; }}
        .vrl-body {{ color:var(--vrl-text); font-size:.92rem; line-height:1.5; }}
        .risk-inline-title {{
          font-size:.9rem; color:var(--vrl-text); font-weight:650;
          vertical-align:middle;
        }}

        .vrl-empty-state {{
          text-align:center; padding:2.35rem 1.6rem; min-height:11rem;
          display:flex; flex-direction:column; align-items:center;
          justify-content:center;
        }}
        .vrl-empty-icon {{
          width:2.65rem; height:2.65rem; display:inline-flex;
          align-items:center; justify-content:center; margin-bottom:.65rem;
          border-radius:var(--vrl-radius); background:var(--vrl-primary-soft);
          border:1px solid #C9DDE2; font-size:1.35rem; line-height:1;
        }}

        .vrl-section-header {{
          display:flex; align-items:flex-end; justify-content:space-between;
          gap:1rem; margin:1.1rem 0 .9rem; padding-bottom:.7rem;
          border-bottom:1px solid var(--vrl-border);
        }}
        .vrl-section-eyebrow {{
          color:var(--vrl-muted); font-size:.72rem; font-weight:700;
          letter-spacing:.08em; text-transform:uppercase; margin-bottom:.18rem;
        }}
        .vrl-section-title {{
          color:var(--vrl-text); font-size:1.05rem; font-weight:750;
          line-height:1.35;
        }}
        .vrl-section-body {{
          color:var(--vrl-muted); font-size:.86rem; line-height:1.45;
          margin-top:.14rem;
        }}
        .vrl-step-card {{
          display:grid; grid-template-columns:2.15rem minmax(0,1fr); gap:.75rem;
          align-items:start; background:var(--vrl-surface);
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          padding:.9rem .95rem; box-shadow:var(--vrl-shadow-sm);
          min-height:4.5rem;
        }}
        .vrl-step-card.done {{
          border-color:#A9DCC4; background:linear-gradient(180deg,#fff,#F3FBF7);
        }}
        .vrl-step-card.todo {{ background:#fff; }}
        .vrl-step-marker {{
          width:1.65rem; height:1.65rem; border-radius:999px;
          display:inline-flex; align-items:center; justify-content:center;
          background:#F2F4F7; color:var(--vrl-muted); font-size:.8rem;
          font-weight:750; border:1px solid var(--vrl-border);
        }}
        .vrl-step-card.done .vrl-step-marker {{
          background:var(--vrl-success); border-color:var(--vrl-success);
          color:#fff;
        }}
        .vrl-step-title {{
          color:var(--vrl-text); font-size:.88rem; font-weight:750;
          line-height:1.35;
        }}
        .vrl-step-body {{
          color:var(--vrl-muted); font-size:.78rem; line-height:1.42;
          margin-top:.12rem;
        }}

        .vrl-badge {{
          display:inline-flex; align-items:center;
          border-radius:999px; padding:.22rem .6rem;
          font-size:.78rem; font-weight:600; border:1px solid transparent;
        }}
        .vrl-badge-success {{
          background:var(--vrl-success-soft); color:var(--vrl-success);
          border-color:#BFE4CE;
        }}
        .vrl-badge-warning {{
          background:var(--vrl-warning-soft); color:var(--vrl-warning);
          border-color:#F3D27A;
        }}
        .vrl-badge-danger {{
          background:var(--vrl-danger-soft); color:var(--vrl-danger);
          border-color:#FDA29B;
        }}
        .vrl-badge-neutral {{
          background:#F2F4F7; color:#475467; border-color:#D0D5DD;
        }}
        .vrl-badge-primary {{
          background:var(--vrl-primary-soft); color:var(--vrl-primary);
          border-color:#C4DBCF;
        }}

        /* ---- Forms & inputs: ensure visible borders everywhere ---- */
        [data-baseweb="input"],
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"],
        textarea {{
          border:1px solid var(--vrl-border) !important;
          border-radius:var(--vrl-radius) !important;
          background:var(--vrl-surface) !important;
        }}

        /* Right sticky sidebar */
        [data-testid="stHorizontalBlock"]:has(.pipeline-sidebar-marker) {{
          align-items: flex-start;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker) {{
          position: sticky; top: 5.2rem;
          max-height: calc(100vh - 6rem);
          overflow-y: auto; overflow-x: hidden;
          padding-right: .3rem;
          word-break: break-word; overflow-wrap: anywhere;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker)
          [data-testid="stMetricLabel"] p {{
          font-size:.78rem; line-height:1.3; white-space: normal;
          overflow-wrap: anywhere;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker)
          [data-testid="stMetricValue"] {{
          font-size:.95rem; white-space: normal;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker)::-webkit-scrollbar {{
          width: 6px;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker
        )::-webkit-scrollbar-thumb {{
          background:#c2d1cc; border-radius:4px;
        }}

        /* ---- Project header (compact hero replacement) ---- */
        .project-header {{
          display:flex; align-items:center; justify-content:space-between;
          gap:1rem; padding:1rem 1.25rem; margin-bottom:1rem;
          border:1px solid var(--vrl-border); border-radius:var(--vrl-radius);
          background:linear-gradient(135deg,var(--vrl-surface),#F2F7F8);
          box-shadow:var(--vrl-shadow-sm);
        }}
        .project-header .ph-title-block h2 {{
          margin:0 0 .15rem; font-size:1.15rem !important; line-height:1.3;
        }}
        .project-header .ph-title-block .ph-sub {{
          color:var(--vrl-muted); font-size:.82rem; line-height:1.4;
        }}
        .project-header .ph-status-badge {{
          display:inline-flex; align-items:center; gap:.3rem;
          padding:.28rem .65rem; border-radius:999px;
          font-size:.8rem; font-weight:650; white-space:nowrap;
          background:var(--vrl-warning-soft); color:var(--vrl-warning);
          border:1px solid #F3D27A;
        }}
        .project-header .ph-status-badge.success {{
          background:var(--vrl-success-soft); color:var(--vrl-success);
          border-color:#BFE4CE;
        }}
        .project-header .ph-status-badge.neutral {{
          background:#F2F4F7; color:#475467; border-color:#D0D5DD;
        }}

        /* ---- Next Action Hero (visual centerpiece) ---- */
        .next-action-hero {{
          background:var(--vrl-warning-soft);
          border:1px solid #F3D27A; border-left:4px solid var(--vrl-warning);
          border-radius:var(--vrl-radius); padding:1.25rem 1.35rem;
          margin-bottom:1rem;
          box-shadow:var(--vrl-shadow-sm);
        }}
        .next-action-hero .vrl-eyebrow {{ color:var(--vrl-warning); }}
        .next-action-hero .nah-title {{
          font-size:1.2rem; font-weight:700; color:var(--vrl-text);
          margin-bottom:.3rem; line-height:1.35;
        }}
        .next-action-hero .nah-summary {{
          color:var(--vrl-text); font-size:.9rem; line-height:1.5; margin-bottom:.5rem;
        }}
        .next-action-hero .nah-lock-label {{
          font-size:.82rem; color:var(--vrl-muted); margin-bottom:.2rem;
        }}
        .next-action-hero .nah-lock-item {{
          font-size:.85rem; color:var(--vrl-text); line-height:1.5;
        }}

        /* ---- Metric strip (thin horizontal bar) ---- */
        .vrl-metric-strip {{
          display:flex; gap:.75rem; margin-bottom:1rem;
        }}
        .vrl-metric-strip .vrl-card {{
          flex:1; margin-bottom:0; padding:.8rem .95rem;
          border-radius:var(--vrl-radius);
        }}
        .vrl-metric-strip .vrl-eyebrow {{ font-size:.7rem; margin-bottom:.1rem; }}
        .vrl-metric-strip .vrl-title {{
          font-size:1rem; margin-bottom:0; line-height:1.3;
        }}

        /* ---- Compact phase stepper (right sidebar) ---- */
        .phase-stepper {{
          display:flex; align-items:center; gap:.18rem;
          margin:.6rem 0 .8rem; flex-wrap:wrap;
        }}
        .phase-stepper .ps-step {{
          display:inline-flex; align-items:center; gap:.22rem;
          font-size:.78rem; font-weight:600; color:var(--vrl-muted);
        }}
        .phase-stepper .ps-dot {{
          width:10px; height:10px; border-radius:50%;
          background:var(--vrl-border); flex-shrink:0;
        }}
        .phase-stepper .ps-step.done .ps-dot {{ background:var(--vrl-success); }}
        .phase-stepper .ps-step.active .ps-dot {{
          background:var(--vrl-primary);
          box-shadow:0 0 0 3px var(--vrl-primary-soft);
        }}
        .phase-stepper .ps-step.active {{ color:var(--vrl-primary); font-weight:700; }}
        .phase-stepper .ps-sep {{
          color:var(--vrl-border); font-size:.7rem; flex-shrink:0;
        }}

        /* ---- Readiness checklist (right sidebar compact) ---- */
        .readiness-line {{
          font-size:.82rem; line-height:1.7; color:var(--vrl-text);
        }}
        .readiness-line .rl-icon {{
          font-weight:700; display:inline-block; width:1.1rem;
        }}

        @media(max-width:800px) {{
          .phase-row {{ grid-template-columns:1fr 1fr; }}
          .block-container {{ padding:2.6rem 1rem 1.25rem; }}
          [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {{
            gap:.9rem;
          }}
          .hero h1 {{ font-size:1.55rem !important; }}
          .project-header {{
            align-items:flex-start; flex-direction:column; padding:1rem;
          }}
          .vrl-section-header {{ margin:.9rem 0 .75rem; }}
          .vrl-metric-strip {{ flex-direction:column; }}
        }}
        </style>""",
        unsafe_allow_html=True,
    )


def render_project_header(
    title: str,
    subtitle: str,
    status_badge: str,
    status_tone: str = "warning",
) -> None:
    """Compact project title bar — replaces large hero when in a project.

    Parameters
    ----------
    title
        Project title (e.g. study title).
    subtitle
        Study type + reporting guideline line.
    status_badge
        Short status text shown as a pill on the right.
    status_tone
        Badge colour: ``warning``, ``success``, or ``neutral``.
    """

    import html as _html

    tone_cls = status_tone if status_tone in ("success", "neutral") else ""
    badge_cls = f"ph-status-badge {tone_cls}".strip()
    st.markdown(
        f"""<div class="project-header">
        <div class="ph-title-block">
          <h2>{_html.escape(title)}</h2>
          <div class="ph-sub">{_html.escape(subtitle)}</div>
        </div>
        <span class="{badge_cls}">{_html.escape(status_badge)}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def render_phase_stepper(current_stage: str | None) -> None:
    """Compact single-row phase stepper for the right sidebar.

    Renders ``01●  02○  03○  04○  05○`` instead of the full phase cards.
    """

    stage = current_stage or "project_init"
    active = next(
        (i for i, (_, values) in enumerate(WORKFLOW_PHASES) if stage in values),
        0,
    )
    steps_html: list[str] = []
    for index, _phase in enumerate(WORKFLOW_PHASES):
        if index == active:
            state_cls = "active"
        elif index < active:
            state_cls = "done"
        else:
            state_cls = ""
        cls = f" {state_cls}" if state_cls else ""
        steps_html.append(
            f'<span class="ps-step{cls}">'
            f'<span class="ps-dot"></span>'
            f'{index + 1:02d}</span>'
        )
        if index < len(WORKFLOW_PHASES) - 1:
            steps_html.append('<span class="ps-sep">─</span>')
    st.markdown(
        f'<div class="phase-stepper">{ "".join(steps_html)}</div>',
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
        stage_label(state.get("current_stage")) or "-",
    )
    cols[1].metric(
        translate("metric_run_status"),
        status_label(state.get("run_status")) or "-",
    )
    cols[2].metric(translate("metric_audit_events"), len(state.get("audit_events", [])))
    cols[3].metric(translate("metric_run_id"), thread_id[:8])


def inject_auto_grow_textareas() -> None:
    """Inject JS so every textarea grows to fit its content automatically.

    Streamlit ``text_area`` widgets use a fixed pixel height by default, which
    clips long text. This observes the DOM and resizes each ``<textarea>`` to
    its ``scrollHeight`` on render and on every keystroke.
    """

    st.iframe(
        """
<script>
(function() {
  var doc = window.parent.document;
  function autoGrow(el) {
    el.style.height = 'auto';
    var sh = el.scrollHeight;
    if (sh < 20) sh = 44; /* fallback when scrollHeight is 0 */
    el.style.height = sh + 'px';
  }
  function setup() {
    doc.querySelectorAll('textarea').forEach(function(ta) {
      if (ta.getAttribute('data-autogrow')) return;
      ta.setAttribute('data-autogrow', '1');
      ta.style.overflowY = 'hidden';
      ta.style.resize = 'none';
      autoGrow(ta);
      ta.addEventListener('input', function() { autoGrow(ta); });
    });
    /* Re-measure after the browser finishes layout */
    requestAnimationFrame(function() {
      doc.querySelectorAll('textarea[data-autogrow]').forEach(function(ta) {
        autoGrow(ta);
      });
    });
  }
  setup();
  if (!window._stAutoGrowObs) {
    window._stAutoGrowObs = new MutationObserver(function() { setup(); });
    window._stAutoGrowObs.observe(doc.body, {childList: true, subtree: true});
  }
})();
</script>
""",
        height=1,
    )
