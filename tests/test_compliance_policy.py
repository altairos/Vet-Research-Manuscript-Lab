"""Unit tests for compliance domain policies (pure functions).

Covers normal path, invalid input, and policy-bypass attempts for each
of the 5 compliance policy functions.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.domain.policies import (
    ComplianceFindingSnapshot,
    PolicyViolation,
    SignOffContext,
    require_checklist_complete,
    require_export_package_complete,
    require_export_version_integrity,
    require_no_blocking_findings,
    require_signoff_preconditions,
)


def _finding(
    *,
    finding_id: str = "f1",
    rule_id: str = "rule-1",
    category: str = "checklist",
    severity: str = "info",
    status: str = "pass",
) -> ComplianceFindingSnapshot:
    return ComplianceFindingSnapshot(
        finding_id=finding_id,
        rule_id=rule_id,
        category=category,
        severity=severity,
        status=status,
    )


class RequireNoBlockingFindingsTests(unittest.TestCase):
    def test_all_pass_findings_allowed(self) -> None:
        findings = (
            _finding(severity="info", status="pass"),
            _finding(severity="warning", status="pass"),
        )
        require_no_blocking_findings(findings)

    def test_error_severity_fail_blocked(self) -> None:
        findings = (_finding(severity="error", status="fail"),)
        with self.assertRaises(PolicyViolation):
            require_no_blocking_findings(findings)

    def test_blocking_severity_fail_blocked(self) -> None:
        findings = (_finding(severity="blocking", status="fail"),)
        with self.assertRaises(PolicyViolation):
            require_no_blocking_findings(findings)

    def test_error_severity_pass_allowed(self) -> None:
        findings = (_finding(severity="error", status="pass"),)
        require_no_blocking_findings(findings)

    def test_warning_severity_fail_allowed(self) -> None:
        findings = (_finding(severity="warning", status="fail"),)
        require_no_blocking_findings(findings)

    def test_empty_findings_allowed(self) -> None:
        require_no_blocking_findings(())

    def test_mixed_findings_one_blocking(self) -> None:
        findings = (
            _finding(finding_id="ok1", severity="info", status="pass"),
            _finding(finding_id="bad1", severity="blocking", status="fail"),
        )
        with self.assertRaises(PolicyViolation):
            require_no_blocking_findings(findings)


class RequireChecklistCompleteTests(unittest.TestCase):
    def test_all_passed_allowed(self) -> None:
        findings = (
            _finding(finding_id="f1", status="pass"),
            _finding(finding_id="f2", status="not_applicable"),
        )
        require_checklist_complete(findings, total_items=2)

    def test_fail_status_blocked(self) -> None:
        findings = (_finding(status="fail"),)
        with self.assertRaises(PolicyViolation):
            require_checklist_complete(findings, total_items=1)

    def test_needs_review_blocked(self) -> None:
        findings = (_finding(status="needs_review"),)
        with self.assertRaises(PolicyViolation):
            require_checklist_complete(findings, total_items=1)

    def test_empty_findings_allowed(self) -> None:
        require_checklist_complete((), total_items=0)

    def test_mixed_fail_and_pass_blocked(self) -> None:
        findings = (
            _finding(finding_id="ok", status="pass"),
            _finding(finding_id="bad", status="fail"),
        )
        with self.assertRaises(PolicyViolation):
            require_checklist_complete(findings, total_items=2)


class RequireSignoffPreconditionsTests(unittest.TestCase):
    def _ctx(
        self,
        *,
        manuscript_version_id: str = "ms-1",
        manuscript_hash: str = "sha256:abc",
        all_required_gates_approved: bool = True,
        blocking_finding_count: int = 0,
    ) -> SignOffContext:
        return SignOffContext(
            manuscript_version_id=manuscript_version_id,
            manuscript_hash=manuscript_hash,
            all_required_gates_approved=all_required_gates_approved,
            blocking_finding_count=blocking_finding_count,
        )

    def test_valid_context_allowed(self) -> None:
        ctx = self._ctx()
        result = require_signoff_preconditions(ctx)
        self.assertEqual(result.manuscript_version_id, "ms-1")

    def test_missing_gates_blocked(self) -> None:
        ctx = self._ctx(all_required_gates_approved=False)
        with self.assertRaises(PolicyViolation):
            require_signoff_preconditions(ctx)

    def test_blocking_findings_blocked(self) -> None:
        ctx = self._ctx(blocking_finding_count=2)
        with self.assertRaises(PolicyViolation):
            require_signoff_preconditions(ctx)

    def test_empty_manuscript_version_blocked(self) -> None:
        ctx = self._ctx(manuscript_version_id="")
        with self.assertRaises(PolicyViolation):
            require_signoff_preconditions(ctx)

    def test_empty_manuscript_hash_blocked(self) -> None:
        ctx = self._ctx(manuscript_hash="")
        with self.assertRaises(PolicyViolation):
            require_signoff_preconditions(ctx)


class RequireExportVersionIntegrityTests(unittest.TestCase):
    def test_matching_hashes_allowed(self) -> None:
        signed = {"protocol": "sha256:a", "manuscript": "sha256:b"}
        current = {"protocol": "sha256:a", "manuscript": "sha256:b"}
        require_export_version_integrity(signed_hashes=signed, current_hashes=current)

    def test_hash_mismatch_blocked(self) -> None:
        signed = {"protocol": "sha256:a"}
        current = {"protocol": "sha256:changed"}
        with self.assertRaises(PolicyViolation):
            require_export_version_integrity(
                signed_hashes=signed, current_hashes=current
            )

    def test_missing_artifact_blocked(self) -> None:
        signed = {"protocol": "sha256:a", "manuscript": "sha256:b"}
        current = {"protocol": "sha256:a"}  # manuscript missing
        with self.assertRaises(PolicyViolation):
            require_export_version_integrity(
                signed_hashes=signed, current_hashes=current
            )

    def test_extra_current_artifacts_allowed(self) -> None:
        signed = {"protocol": "sha256:a"}
        current = {"protocol": "sha256:a", "extra": "sha256:x"}
        require_export_version_integrity(signed_hashes=signed, current_hashes=current)

    def test_empty_hashes_allowed(self) -> None:
        require_export_version_integrity(signed_hashes={}, current_hashes={})

    def test_signed_empty_current_nonempty_allowed(self) -> None:
        require_export_version_integrity(
            signed_hashes={}, current_hashes={"x": "sha256:y"}
        )


class RequireExportPackageCompleteTests(unittest.TestCase):
    def test_all_required_components_present(self) -> None:
        roles = ("manuscript", "references", "manifest", "ai_usage")
        require_export_package_complete(component_roles=roles)

    def test_missing_manifest_blocked(self) -> None:
        roles = ("manuscript", "references", "ai_usage")
        with self.assertRaises(PolicyViolation):
            require_export_package_complete(component_roles=roles)

    def test_missing_references_blocked(self) -> None:
        roles = ("manuscript", "manifest", "ai_usage")
        with self.assertRaises(PolicyViolation):
            require_export_package_complete(component_roles=roles)

    def test_missing_ai_usage_blocked(self) -> None:
        roles = ("manuscript", "references", "manifest")
        with self.assertRaises(PolicyViolation):
            require_export_package_complete(component_roles=roles)

    def test_missing_manuscript_blocked(self) -> None:
        roles = ("references", "manifest", "ai_usage")
        with self.assertRaises(PolicyViolation):
            require_export_package_complete(component_roles=roles)

    def test_extra_components_allowed(self) -> None:
        roles = (
            "manuscript",
            "references",
            "manifest",
            "ai_usage",
            "supplementary",
        )
        require_export_package_complete(component_roles=roles)

    def test_empty_components_blocked(self) -> None:
        roles: tuple[str, ...] = ()
        with self.assertRaises(PolicyViolation):
            require_export_package_complete(component_roles=roles)


if __name__ == "__main__":
    unittest.main()
