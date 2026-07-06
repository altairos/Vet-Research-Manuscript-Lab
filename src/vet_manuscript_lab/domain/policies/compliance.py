"""Pure policy checks for the compliance, sign-off, and export aggregate.

These functions enforce the invariants described in domain_model.md
("ComplianceFinding" and "ExportPackage") and the Phase 5 exit criteria
in DEVELOPMENT.md.

Core invariants:

1. High-severity unresolved findings block sign-off and export.
2. Required checklist items must pass before export.
3. Sign-off binds exact artifact versions; any post-sign-off hash change
   invalidates the export (fail-closed).
4. The export package must contain all required components.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation


@dataclass(frozen=True, slots=True)
class ComplianceFindingSnapshot:
    """Compact representation of a compliance finding."""

    finding_id: str
    rule_id: str
    category: str
    severity: str  # "info", "warning", "error", "blocking"
    status: str  # "pass", "fail", "not_applicable", "needs_review"


@dataclass(frozen=True, slots=True)
class SignOffContext:
    """Inputs checked before sign-off may proceed."""

    manuscript_version_id: str
    manuscript_hash: str
    all_required_gates_approved: bool
    blocking_finding_count: int


@dataclass(frozen=True, slots=True)
class ExportVersionBinding:
    """Hash binding recorded at sign-off time."""

    sign_off_id: str
    artifact_hashes: dict[str, str] = field(default_factory=dict)


def require_no_blocking_findings(
    findings: tuple[ComplianceFindingSnapshot, ...],
) -> None:
    """No blocking or error-level unresolved finding may remain.

    A finding with status 'fail' and severity 'error' or 'blocking'
    must be resolved before sign-off can proceed.
    """

    for f in findings:
        if f.status == "fail" and f.severity in ("error", "blocking"):
            raise PolicyViolation(
                f"Compliance finding '{f.finding_id}' (rule '{f.rule_id}') "
                f"has unresolved {f.severity} severity; "
                f"blocks sign-off and export"
            )


def require_checklist_complete(
    findings: tuple[ComplianceFindingSnapshot, ...],
    *,
    total_items: int,
) -> None:
    """All required checklist items must have a pass or not_applicable finding.

    The number of passed items must equal the total required items.
    Any 'fail' or 'needs_review' status means the checklist is incomplete.
    """

    unresolved = [
        f
        for f in findings
        if f.status in ("fail", "needs_review")
    ]
    if unresolved:
        raise PolicyViolation(
            f"Checklist incomplete: {len(unresolved)} item(s) "
            f"are unresolved (fail or needs_review)"
        )


def require_signoff_preconditions(ctx: SignOffContext) -> SignOffContext:
    """Sign-off requires all gates approved and no blocking findings.

    Only an authorised human can sign off; the system cannot self-approve.
    """

    if not ctx.all_required_gates_approved:
        raise PolicyViolation(
            "Sign-off requires all required gates to be approved"
        )
    if ctx.blocking_finding_count > 0:
        raise PolicyViolation(
            f"Sign-off blocked by {ctx.blocking_finding_count} "
            f"blocking compliance finding(s)"
        )
    if not ctx.manuscript_version_id:
        raise PolicyViolation("Sign-off requires a manuscript version")
    if not ctx.manuscript_hash:
        raise PolicyViolation("Sign-off requires a manuscript hash")
    return ctx


def require_export_version_integrity(
    *,
    signed_hashes: dict[str, str],
    current_hashes: dict[str, str],
) -> None:
    """Export must fail-closed if any artifact version changed post-sign-off.

    The hashes recorded at sign-off time must exactly match the current
    hashes.  Any mismatch indicates a post-sign-off mutation and must
    block the export.
    """

    for key, signed_hash in signed_hashes.items():
        current_hash = current_hashes.get(key)
        if current_hash is None:
            raise PolicyViolation(
                f"Artifact '{key}' was present at sign-off but is "
                f"now missing; export blocked (fail-closed)"
            )
        if signed_hash != current_hash:
            raise PolicyViolation(
                f"Artifact '{key}' hash changed after sign-off: "
                f"signed={signed_hash}, current={current_hash}; "
                f"export blocked (fail-closed)"
            )


def require_export_package_complete(
    *,
    component_roles: tuple[str, ...],
) -> None:
    """The export package must contain all required components.

    Required roles: manuscript, references, manifest, ai_usage.
    """

    required = {"manuscript", "references", "manifest", "ai_usage"}
    actual = set(component_roles)
    missing = required - actual
    if missing:
        raise PolicyViolation(
            f"Export package is missing required components: "
            f"{sorted(missing)}"
        )


__all__ = [
    "ComplianceFindingSnapshot",
    "ExportVersionBinding",
    "SignOffContext",
    "require_checklist_complete",
    "require_export_package_complete",
    "require_export_version_integrity",
    "require_no_blocking_findings",
    "require_signoff_preconditions",
]
