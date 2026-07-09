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
    "bg": "#F7F8F5",
    "surface": "#FFFFFF",
    "surface_alt": "#F1F4F0",
    "text": "#1F2933",
    "muted": "#6B7280",
    "border": "#D8DED6",
    "primary": "#355E4B",
    "primary_soft": "#E3EEE8",
    "accent": "#3B6F9E",
    "warning": "#B7791F",
    "warning_soft": "#FFF4D6",
    "danger": "#B42318",
    "danger_soft": "#FEE4E2",
    "success": "#2F855A",
    "success_soft": "#DFF3E8",
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
        }}

        /* ---- Typography ---- */
        * {{
          font-family: 'Inter','Source Sans 3','IBM Plex Sans',
          'Noto Sans SC','Source Han Sans','Microsoft YaHei',
          system-ui, sans-serif !important;
        }}
        /* Material Icons: let Streamlit handle natively, don't override font */
        .stApp {{
          background:var(--vrl-bg); color:var(--vrl-text);
        }}

        /* ---- Layout container ---- */
        .block-container {{
          max-width:1440px; padding-top:1.25rem; padding-bottom:3rem;
        }}
        [data-testid="stMainBlockContainer"] {{
          font-size:15px; line-height:1.55;
        }}
        [data-testid="stMainBlockContainer"] p {{
          font-size:.94rem; line-height:1.58;
        }}

        /* ---- Headings ---- */
        h1,h2,h3,h4,h5 {{
          letter-spacing:-.018em; color:var(--vrl-text); line-height:1.3;
        }}
        h1 {{ font-size:2rem !important; }}
        h2 {{
          font-size:1.4rem !important; margin-top:.5rem !important;
          margin-bottom:.3rem !important;
        }}
        h3 {{
          font-size:1.1rem !important; margin-top:.4rem !important;
          margin-bottom:.25rem !important;
        }}
        h4 {{ font-size:1rem !important; margin:.7rem 0 .4rem !important; }}
        h5 {{ font-size:.9rem !important; margin:.6rem 0 .35rem !important; }}

        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {{
          background:var(--vrl-surface-alt); border-right:1px solid var(--vrl-border);
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
          padding:.3rem 0 .9rem; margin-bottom:.4rem;
        }}
        .sidebar-brand strong {{
          display:block; color:var(--vrl-primary); font-size:1rem; line-height:1.35;
        }}
        .sidebar-brand span {{
          color:var(--vrl-muted); font-size:.82rem; line-height:1.5;
        }}
        .sidebar-card {{
          background:rgba(255,255,255,.72); border:1px solid var(--vrl-border);
          border-radius:12px; padding:.8rem .9rem; margin:.35rem 0 .8rem;
        }}
        .sidebar-card strong {{ display:block; margin-bottom:.25rem; }}
        .side-step {{
          font-size:.86rem; line-height:1.45; margin:.36rem 0;
          color:var(--vrl-muted);
        }}

        /* ---- Project list items ---- */
        .project-list-item {{
          border:1px solid var(--vrl-border); border-radius:10px;
          padding:.55rem .7rem; margin-bottom:.4rem; background:var(--vrl-surface);
        }}
        .project-list-item.active {{
          border-color:var(--vrl-primary); background:var(--vrl-primary-soft);
        }}
        .project-list-item strong {{ display:block; font-size:.88rem; }}
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
          margin-bottom:.5rem; padding-bottom:.35rem;
          border-bottom:1px solid var(--vrl-border);
          font-size:.95rem; color:var(--vrl-primary);
          white-space: normal; word-break: break-word;
          line-height:1.4;
        }}
        .pipeline-bar-header strong {{ font-size:1rem; }}
        [data-testid="stVerticalBlockBorderContainer"]
          [data-testid="stVerticalBlock"] {{
          gap:1.1rem;
        }}
        [data-testid="stVerticalBlockBorderContainer"] p {{
          line-height:1.85 !important;
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
          padding:1.25rem 1.5rem; border:1px solid var(--vrl-border);
          border-radius:16px;
          background:linear-gradient(135deg,var(--vrl-surface),var(--vrl-primary-soft));
          box-shadow:0 1px 3px rgba(16,24,40,.06);
          margin-bottom:1rem;
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
          gap:.35rem; background:var(--vrl-surface-alt); padding:.28rem;
          border-radius:12px; margin:.55rem 0 .7rem;
        }}
        .stTabs [data-baseweb="tab"] {{
          min-height:2.25rem; padding:.42rem 1.2rem; border-radius:8px;
        }}
        .stTabs [data-baseweb="tab"] p {{
          margin:0 !important; font-size:.88rem !important;
          line-height:1.4 !important;
        }}
        .stTabs [aria-selected="true"] {{
          background:var(--vrl-surface); color:var(--vrl-primary);
          box-shadow:0 1px 5px rgba(16,24,40,.06);
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
          border-radius:12px; padding:.78rem .85rem .68rem;
        }}
        [data-testid="stForm"] [data-testid="stVerticalBlock"] {{ gap:.3rem; }}
        [data-testid="stForm"] label p,
        [data-testid="stWidgetLabel"] p {{
          font-size:.86rem; line-height:1.4; font-weight:650;
          color:#41514b; margin-bottom:.18rem;
        }}
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div {{ min-height:2.15rem; }}
        textarea {{ min-height:2.8rem !important; }}
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] [data-baseweb="select"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
          border:1px solid var(--vrl-border) !important;
          border-radius:8px !important; background:var(--vrl-surface) !important;
        }}
        [data-testid="stSidebar"] textarea {{
          border:1px solid var(--vrl-border) !important; border-radius:8px !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] > div {{
          min-height:1.95rem;
        }}

        /* ---- Buttons ---- */
        .stButton > button,.stFormSubmitButton > button {{
          border-radius:999px; font-weight:650; min-height:2.15rem;
        }}

        /* ---- Metric cards (upgraded) ---- */
        div[data-testid="stMetric"] {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          padding:1rem; border-radius:16px;
          box-shadow:0 1px 2px rgba(16,24,40,.04);
        }}

        /* ---- Expander ---- */
        [data-testid="stExpander"] {{
          background:var(--vrl-surface); border-color:var(--vrl-border);
          border-radius:12px;
        }}

        /* ---- Phase tracker ---- */
        .phase-row {{
          display:grid; grid-template-columns:repeat(5,1fr);
          gap:6px; margin:.4rem 0 .65rem;
        }}
        .phase {{
          border:1px solid var(--vrl-border); border-radius:10px;
          padding:.48rem .58rem; background:var(--vrl-surface);
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
          padding:.72rem .88rem; border-radius:10px; margin:.35rem 0 .75rem;
        }}

        /* ===== DESIGN-SYSTEM PRIMITIVES (.vrl-*) ===== */

        .vrl-card {{
          background:var(--vrl-surface); border:1px solid var(--vrl-border);
          border-radius:16px; padding:1rem 1.125rem;
          box-shadow:0 1px 3px rgba(16,24,40,.06); margin-bottom:.875rem;
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

        .vrl-badge {{
          display:inline-flex; align-items:center;
          border-radius:999px; padding:.18rem .55rem;
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
          background:#EEF2F6; color:#475467; border-color:#D0D5DD;
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
          border-radius:8px !important;
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
          word-break: break-word;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker)::-webkit-scrollbar {{
          width: 6px;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker
        )::-webkit-scrollbar-thumb {{
          background:#c2d1cc; border-radius:4px;
        }}
        [data-testid="stColumn"]:has(.pipeline-sidebar-marker) .phase-row {{
          grid-template-columns: repeat(2, 1fr);
        }}

        @media(max-width:800px) {{
          .phase-row {{ grid-template-columns:1fr 1fr; }}
          .block-container {{ padding:2.6rem .9rem .9rem; }}
          .hero h1 {{ font-size:1.55rem !important; }}
        }}
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
    el.style.height = el.scrollHeight + 'px';
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
