"""Card-style layout components for the design system."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.components.badges import badge, severity_pill, status_to_tone


@dataclass(frozen=True, slots=True)
class Metric:
    """A single metric for ``metric_strip``."""

    label: str
    value: Any
    tone: str = "neutral"


def _esc(text: Any) -> str:
    return html.escape(str(text))


def card(
    title: str,
    body: str = "",
    eyebrow: str | None = None,
    *,
    tone: str = "",
) -> None:
    """Render a generic design-system card.

    Parameters
    ----------
    title
        Bold card heading.
    body
        Muted descriptive text below the title.
    eyebrow
        Small uppercase label above the title.
    tone
        Optional left-border accent: ``success``, ``warning``, ``danger``,
        ``primary``, ``accent``.
    """

    eyebrow_html = (
        f'<div class="vrl-eyebrow">{_esc(eyebrow)}</div>' if eyebrow else ""
    )
    body_html = (
        f'<div class="vrl-muted">{_esc(body)}</div>' if body else ""
    )
    tone_class = f" {tone}" if tone else ""
    st.markdown(
        f"""<div class="vrl-card{tone_class}">
        {eyebrow_html}
        <div class="vrl-title">{_esc(title)}</div>
        {body_html}
        </div>""",
        unsafe_allow_html=True,
    )


def metric_strip(metrics: list[Metric]) -> None:
    """Render a horizontal strip of metric cards."""

    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics, strict=True):
        with col:
            tone_class = f" {m.tone}" if m.tone and m.tone != "neutral" else ""
            st.markdown(
                f"""<div class="vrl-card{tone_class}" style="margin-bottom:0;">
                <div class="vrl-eyebrow">{_esc(m.label)}</div>
                <div class="vrl-title" style="margin-bottom:0;">{_esc(m.value)}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def artifact_card(
    title: str,
    version: str = "",
    status: str = "",
    hash_short: str = "",
    updated_at: str = "",
    artifact_type: str = "",
) -> None:
    """Render an artifact summary card with hash hidden by default.

    The raw hash is truncated and only displayed if *hash_short* is provided.
    """

    parts: list[str] = []
    if artifact_type:
        parts.append(badge(artifact_type, tone="neutral"))
    status_tone = status_to_tone(status) if status else "neutral"
    if status:
        parts.append(badge(status, tone=status_tone))
    if version:
        parts.append(f'<span class="vrl-muted">v{_esc(version)}</span>')
    badges_html = " ".join(parts)

    meta_parts: list[str] = []
    if updated_at:
        meta_parts.append(f'<span class="vrl-muted">{_esc(updated_at)}</span>')
    if hash_short:
        meta_parts.append(
            f'<span class="vrl-muted" style="font-family:monospace;font-size:.75rem;">'
            f"{_esc(hash_short)}</span>"
        )
    meta_html = " · ".join(meta_parts)

    st.markdown(
        f"""<div class="vrl-card">
        <div class="vrl-eyebrow">{_esc(translate_safe("dash_artifact"))}</div>
        <div class="vrl-title">{_esc(title)}</div>
        <div style="margin-bottom:.35rem;">{badges_html}</div>
        <div>{meta_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def finding_card(
    severity: str,
    title: str,
    location: str = "",
    recommendation: str = "",
    detail: str = "",
) -> None:
    """Render a risk-finding card with severity pill and accent border."""

    tone_map = {
        "critical": "danger",
        "error": "danger",
        "high": "danger",
        "warning": "warning",
        "medium": "warning",
        "info": "",
        "low": "",
    }
    tone = tone_map.get(severity, "")

    loc_html = (
        f'<div class="vrl-muted" style="margin-bottom:.2rem;">'
        f"{_esc(location)}</div>"
        if location
        else ""
    )
    detail_html = f'<div class="vrl-body">{_esc(detail)}</div>' if detail else ""
    rec_html = (
        f'<div class="vrl-muted" style="margin-top:.3rem;">'
        f"{_esc(recommendation)}</div>"
        if recommendation
        else ""
    )

    title_span = (
        f'<span class="vrl-title" '
        f'style="margin-bottom:0;font-size:1rem;">{_esc(title)}</span>'
    )

    st.markdown(
        f"""<div class="vrl-card {tone}">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;">
          {severity_pill(severity)}
          {title_span}
        </div>
        {loc_html}
        {detail_html}
        {rec_html}
        </div>""",
        unsafe_allow_html=True,
    )


def approval_gate_card(
    title: str,
    summary: str = "",
    next_stage: str = "",
) -> None:
    """Render an approval-gate prompt card (amber accent)."""

    next_html = ""
    if next_stage:
        next_html = (
            f'<div class="vrl-muted" style="margin-top:.2rem;">'
            f'{translate_safe("dash_next_stage")}: {_esc(next_stage)}</div>'
        )

    st.markdown(
        f"""<div class="vrl-card warning">
        <div class="vrl-eyebrow">{translate_safe("dash_approval_needed")}</div>
        <div class="vrl-title">{_esc(title)}</div>
        <div class="vrl-body">{_esc(summary)}</div>
        {next_html}
        </div>""",
        unsafe_allow_html=True,
    )


def empty_state_card(
    icon: str,
    title: str,
    body: str = "",
) -> None:
    """Render a friendly empty-state placeholder card."""

    st.markdown(
        f"""<div class="vrl-card" style="text-align:center;padding:2.5rem 1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:.5rem;">{_esc(icon)}</div>
        <div class="vrl-title">{_esc(title)}</div>
        <div class="vrl-muted">{_esc(body)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def translate_safe(key: str) -> str:
    """Translate with graceful fallback (avoids circular import at module level)."""

    from vet_manuscript_lab.ui.i18n import translate

    return translate(key)


__all__ = [
    "Metric",
    "approval_gate_card",
    "artifact_card",
    "card",
    "empty_state_card",
    "finding_card",
    "metric_strip",
]
