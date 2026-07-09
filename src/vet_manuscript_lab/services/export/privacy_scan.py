"""Export-time privacy scanner.

Scans each export component for:

1. **Secrets** — API keys, passwords, bearer tokens (critical severity).
2. **PII** — email addresses, phone numbers, credit card numbers (warning
   severity).

In ``RunMode.PRODUCTION``, any critical secret finding blocks the export.
The scanner is designed as a pure function that operates on
:class:`ExportResult` (or its components) without any I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.domain.policies.privacy import (
    PrivacyFinding,
    require_no_secrets_in_export,
    scan_for_pii,
    scan_for_secrets,
)
from vet_manuscript_lab.services.export.types import ExportComponent, ExportResult


@dataclass(frozen=True, slots=True)
class ComponentPrivacyReport:
    """Privacy scan report for a single export component."""

    component_role: str
    component_filename: str
    secret_findings: tuple[PrivacyFinding, ...]
    pii_findings: tuple[PrivacyFinding, ...]

    @property
    def has_critical(self) -> bool:
        """True when at least one critical-severity secret was found."""

        return any(f.severity == "critical" for f in self.secret_findings)

    @property
    def finding_count(self) -> int:
        return len(self.secret_findings) + len(self.pii_findings)


@dataclass(frozen=True, slots=True)
class ExportPrivacyReport:
    """Aggregated privacy scan report for an entire export package."""

    reports: tuple[ComponentPrivacyReport, ...] = field(default_factory=tuple)

    @property
    def total_secret_count(self) -> int:
        return sum(len(r.secret_findings) for r in self.reports)

    @property
    def total_pii_count(self) -> int:
        return sum(len(r.pii_findings) for r in self.reports)

    @property
    def total_count(self) -> int:
        return self.total_secret_count + self.total_pii_count

    @property
    def has_critical(self) -> bool:
        return any(r.has_critical for r in self.reports)

    def critical_components(self) -> list[str]:
        """Return filenames of components with critical secrets."""

        return [r.component_filename for r in self.reports if r.has_critical]


def scan_component(component: ExportComponent) -> ComponentPrivacyReport:
    """Scan a single export component for privacy issues."""

    content = component.content
    secrets = tuple(scan_for_secrets(content))
    pii = tuple(scan_for_pii(content))
    return ComponentPrivacyReport(
        component_role=component.role,
        component_filename=component.filename,
        secret_findings=secrets,
        pii_findings=pii,
    )


def scan_export(
    export_result: ExportResult,
    *,
    run_mode_is_production: bool = False,
) -> ExportPrivacyReport:
    """Scan all components in an export package for privacy issues.

    When *run_mode_is_production* is ``True``, any critical secret finding
    raises :class:`PolicyViolation` and blocks the export entirely.
    """

    reports: list[ComponentPrivacyReport] = []
    for component in export_result.components:
        report = scan_component(component)
        reports.append(report)

        # In production, block immediately on the first critical component
        if run_mode_is_production and report.has_critical:
            raise PolicyViolation(
                f"Export blocked: component '{component.filename}' "
                f"contains {len(report.secret_findings)} potential "
                f"secret(s); production mode requires redaction"
            )

    return ExportPrivacyReport(reports=tuple(reports))


def scan_export_content(
    content: str,
    *,
    run_mode_is_production: bool = False,
) -> tuple[list[PrivacyFinding], list[PrivacyFinding]]:
    """Scan arbitrary text content for secrets and PII.

    Convenience wrapper for pre-export validation. Returns
    ``(secret_findings, pii_findings)``.
    """

    secret_findings = require_no_secrets_in_export(
        content, run_mode_is_production=run_mode_is_production
    )
    pii_findings = scan_for_pii(content)
    return secret_findings, pii_findings


def summarize_report(report: ExportPrivacyReport) -> dict[str, Any]:
    """Return a plain-dict summary suitable for logging or UI display."""

    return {
        "total_components_scanned": len(report.reports),
        "total_findings": report.total_count,
        "total_secrets": report.total_secret_count,
        "total_pii": report.total_pii_count,
        "has_critical": report.has_critical,
        "critical_components": report.critical_components(),
        "component_summaries": [
            {
                "filename": r.component_filename,
                "role": r.component_role,
                "secret_count": len(r.secret_findings),
                "pii_count": len(r.pii_findings),
                "has_critical": r.has_critical,
            }
            for r in report.reports
        ],
    }


__all__ = [
    "ComponentPrivacyReport",
    "ExportPrivacyReport",
    "scan_component",
    "scan_export",
    "scan_export_content",
    "summarize_report",
]
