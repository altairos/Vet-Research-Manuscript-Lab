"""Reusable HTML badge components for the design system."""

from __future__ import annotations

import html

# Map internal severity strings to badge tones.
_SEVERITY_TONE: dict[str, str] = {
    "critical": "danger",
    "error": "danger",
    "high": "danger",
    "warning": "warning",
    "medium": "warning",
    "info": "neutral",
    "low": "neutral",
}

_SEVERITY_LABEL_SUFFIX: dict[str, str] = {
    "critical": "CRITICAL",
    "error": "ERROR",
    "high": "HIGH",
    "warning": "WARNING",
    "medium": "MEDIUM",
    "info": "INFO",
    "low": "LOW",
}


def badge(label: str, tone: str = "neutral") -> str:
    """Return an inline HTML badge element.

    ``tone`` must be one of: ``success``, ``warning``, ``danger``,
    ``neutral``, ``primary``.
    """

    safe = html.escape(label)
    return f'<span class="vrl-badge vrl-badge-{tone}">{safe}</span>'


def status_badge(status: str, severity: str | None = None) -> str:
    """Return a badge that reflects both status and optional severity.

    If *severity* is provided the badge tone is derived from it; otherwise
    the status text itself is used as a neutral label.
    """

    tone = _SEVERITY_TONE.get(severity or "", "neutral") if severity else "neutral"
    return badge(status, tone=tone)


def severity_pill(severity: str) -> str:
    """Return a coloured pill for a severity level (replaces emoji badges)."""

    tone = _SEVERITY_TONE.get(severity, "neutral")
    label = _SEVERITY_LABEL_SUFFIX.get(severity, severity.upper())
    return badge(label, tone=tone)


def status_to_tone(status: str) -> str:
    """Map a workflow / artifact status string to a badge tone."""

    status_lower = status.lower()
    if status_lower in ("approved", "locked", "complete", "included", "passed"):
        return "success"
    if status_lower in ("in_review", "pending", "needs_review", "waiting"):
        return "warning"
    if status_lower in ("rejected", "failed", "blocked", "error"):
        return "danger"
    return "neutral"
