"""Tests for privacy policies and export privacy scanning.

Covers:
- URL credential redaction
- Secret detection (AWS keys, passwords, bearer tokens)
- PII detection (emails, phone numbers, credit cards)
- Combined sanitisation
- Dict sanitisation
- Production mode enforcement
- Export component scanning
"""

from __future__ import annotations

import pytest

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.domain.policies.privacy import (
    redact_pii,
    redact_secrets,
    redact_url,
    require_no_secrets_in_export,
    sanitize_dict,
    sanitize_text,
    scan_for_pii,
    scan_for_secrets,
)
from vet_manuscript_lab.services.export.generator import (
    ExportInput,
    MockExportGenerator,
)
from vet_manuscript_lab.services.export.privacy_scan import (
    ComponentPrivacyReport,
    ExportPrivacyReport,
    scan_component,
    scan_export,
    scan_export_content,
    summarize_report,
)
from vet_manuscript_lab.services.export.types import ExportComponent

# ---------------------------------------------------------------------------
# URL redaction
# ---------------------------------------------------------------------------


class TestRedactUrl:
    def test_postgres_url_with_password(self) -> None:
        url = "postgresql://admin:secret123@db.host:5432/vet_lab"
        redacted = redact_url(url)
        assert "secret123" not in redacted
        assert "***" in redacted
        assert "admin" in redacted
        assert "db.host" in redacted

    def test_url_without_credentials(self) -> None:
        url = "sqlite:///./vet_lab.db"
        assert redact_url(url) == url

    def test_url_without_at_sign(self) -> None:
        url = "https://example.com/path"
        assert redact_url(url) == url

    def test_mysql_url_with_password(self) -> None:
        url = "mysql://root:pass@localhost:3306/db"
        redacted = redact_url(url)
        assert "pass" not in redacted.replace("password", "")
        assert "***" in redacted


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------


class TestScanForSecrets:
    def test_aws_access_key_detected(self) -> None:
        text = "Using key AKIAIOSFODNN7EXAMPLE for AWS"
        findings = scan_for_secrets(text)
        assert len(findings) == 1
        assert findings[0].finding_type == "secret_aws_key"
        assert findings[0].severity == "critical"

    def test_password_kv_detected(self) -> None:
        text = "password=mySecretPass123"
        findings = scan_for_secrets(text)
        assert any(f.finding_type == "secret_password" for f in findings)

    def test_bearer_token_detected(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test"
        findings = scan_for_secrets(text)
        assert any(f.finding_type == "secret_bearer_token" for f in findings)

    def test_clean_text_no_findings(self) -> None:
        text = "The prevalence of disease was 15% in dogs."
        assert scan_for_secrets(text) == []

    def test_findings_sorted_by_position(self) -> None:
        text = "password=secret1 token=abc123def456"
        findings = scan_for_secrets(text)
        positions = [f.start for f in findings]
        assert positions == sorted(positions)


class TestRedactSecrets:
    def test_secret_replaced_with_redacted(self) -> None:
        text = "password=mySecretPass123"
        result = redact_secrets(text)
        assert result.redaction_count >= 1
        assert "mySecretPass123" not in result.redacted_text
        assert "[REDACTED]" in result.redacted_text

    def test_clean_text_unchanged(self) -> None:
        text = "Normal scientific text."
        result = redact_secrets(text)
        assert result.redaction_count == 0
        assert result.redacted_text == text

    def test_multiple_secrets_redacted(self) -> None:
        text = "password=pass1 token=tok123"
        result = redact_secrets(text)
        assert result.redaction_count >= 1


# ---------------------------------------------------------------------------
# PII detection
# ---------------------------------------------------------------------------


class TestScanForPii:
    def test_email_detected(self) -> None:
        text = "Contact: dr.smith@university.edu for details"
        findings = scan_for_pii(text)
        assert any(f.finding_type == "pii_email" for f in findings)
        assert findings[0].severity == "warning"

    def test_credit_card_detected(self) -> None:
        text = "Card: 4111 1111 1111 1111"
        findings = scan_for_pii(text)
        assert any(f.finding_type == "pii_credit_card" for f in findings)

    def test_phone_number_detected(self) -> None:
        text = "Call +1-555-123-4567"
        findings = scan_for_pii(text)
        phone_findings = [f for f in findings if f.finding_type == "pii_phone"]
        assert len(phone_findings) >= 1

    def test_short_number_not_phone(self) -> None:
        text = "Group A had 15 dogs."
        findings = scan_for_pii(text)
        phone_findings = [f for f in findings if f.finding_type == "pii_phone"]
        assert len(phone_findings) == 0

    def test_clean_text_no_pii(self) -> None:
        text = "Canine patients were included in the study."
        assert scan_for_pii(text) == []


class TestRedactPii:
    def test_email_redacted(self) -> None:
        text = "Email: test@example.com"
        result = redact_pii(text)
        assert result.redaction_count >= 1
        assert "test@example.com" not in result.redacted_text
        assert "[REDACTED]" in result.redacted_text

    def test_clean_text_unchanged(self) -> None:
        text = "Results were significant."
        result = redact_pii(text)
        assert result.redaction_count == 0
        assert result.redacted_text == text


# ---------------------------------------------------------------------------
# Combined sanitisation
# ---------------------------------------------------------------------------


class TestSanitizeText:
    def test_both_secret_and_pii_redacted(self) -> None:
        text = "password=secret email: user@test.com"
        result = sanitize_text(text)
        assert "secret" not in result.redacted_text
        assert "user@test.com" not in result.redacted_text
        assert result.redaction_count >= 2

    def test_clean_text_unchanged(self) -> None:
        text = "The results show p < 0.05."
        result = sanitize_text(text)
        assert result.redaction_count == 0
        assert result.redacted_text == text


# ---------------------------------------------------------------------------
# Dict sanitisation
# ---------------------------------------------------------------------------


class TestSanitizeDict:
    def test_sensitive_key_redacted(self) -> None:
        data = {"zotero_api_key": "abc123secret", "name": "Project A"}
        result = sanitize_dict(data)
        assert result["zotero_api_key"] == "[REDACTED]"
        assert result["name"] == "Project A"

    def test_nested_dict_sanitised(self) -> None:
        data = {
            "config": {"password": "pass123", "url": "http://test.com"},
        }
        result = sanitize_dict(data)
        nested = result["config"]
        assert isinstance(nested, dict)
        assert nested["password"] == "[REDACTED]"

    def test_string_value_sanitised(self) -> None:
        data = {"notes": "password=secret123 in the text"}
        result = sanitize_dict(data)
        assert "secret123" not in str(result["notes"])

    def test_list_values_sanitised(self) -> None:
        data = {"items": ["password=pass1", "normal text"]}
        result = sanitize_dict(data)
        items = result["items"]
        assert isinstance(items, list)
        assert "pass1" not in str(items[0])

    def test_non_string_values_preserved(self) -> None:
        data = {"count": 42, "rate": 0.15, "active": True}
        result = sanitize_dict(data)
        assert result["count"] == 42
        assert result["rate"] == 0.15
        assert result["active"] is True

    def test_custom_sensitive_keys(self) -> None:
        data = {"custom_secret": "value", "name": "test"}
        result = sanitize_dict(data, sensitive_keys=frozenset({"custom_secret"}))
        assert result["custom_secret"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# Production enforcement
# ---------------------------------------------------------------------------


class TestRequireNoSecretsInExport:
    def test_clean_text_no_issue(self) -> None:
        text = "Normal manuscript content."
        findings = require_no_secrets_in_export(text, run_mode_is_production=True)
        assert findings == []

    def test_secret_in_production_raises(self) -> None:
        text = "password=secret123"
        with pytest.raises(PolicyViolation, match="secret"):
            require_no_secrets_in_export(text, run_mode_is_production=True)

    def test_secret_in_demo_returns_findings(self) -> None:
        text = "password=secret123"
        findings = require_no_secrets_in_export(text, run_mode_is_production=False)
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Export component scanning
# ---------------------------------------------------------------------------


def _make_component(
    role: str = "manuscript",
    filename: str = "manuscript.qmd",
    content: str = "Normal content.",
) -> ExportComponent:
    return ExportComponent(
        role=role,
        filename=filename,
        content=content,
        content_hash="sha256:test",
        media_type="text/markdown",
    )


class TestScanComponent:
    def test_clean_component(self) -> None:
        comp = _make_component(content="Normal text")
        report = scan_component(comp)
        assert isinstance(report, ComponentPrivacyReport)
        assert report.finding_count == 0

    def test_component_with_secret(self) -> None:
        comp = _make_component(content="password=secret123")
        report = scan_component(comp)
        assert len(report.secret_findings) >= 1
        assert report.has_critical

    def test_component_with_pii(self) -> None:
        comp = _make_component(content="Email: test@test.com")
        report = scan_component(comp)
        assert len(report.pii_findings) >= 1


# ---------------------------------------------------------------------------
# Export-level scanning
# ---------------------------------------------------------------------------


class TestScanExport:
    def test_clean_export(self) -> None:
        components = (
            _make_component(role="manuscript", filename="m.qmd"),
            _make_component(role="references", filename="r.bib"),
        )
        from vet_manuscript_lab.services.export.types import (
            ExportManifest,
            ExportResult,
        )

        export = ExportResult(
            manifest=ExportManifest(
                project_id="test",
                sign_off_id="so-1",
                artifact_versions=(),
                ai_usage={},
            ),
            components=components,
            package_hash="sha256:test",
            package_uri="mock://test",
        )
        report = scan_export(export)
        assert isinstance(report, ExportPrivacyReport)
        assert report.total_count == 0

    def test_export_with_secret_in_production_raises(self) -> None:
        from vet_manuscript_lab.services.export.types import (
            ExportManifest,
            ExportResult,
        )

        components = (
            _make_component(content="password=secret123"),
            _make_component(content="Clean text"),
        )
        export = ExportResult(
            manifest=ExportManifest(
                project_id="test",
                sign_off_id="so-1",
                artifact_versions=(),
                ai_usage={},
            ),
            components=components,
            package_hash="sha256:test",
            package_uri="mock://test",
        )
        with pytest.raises(PolicyViolation, match="secret"):
            scan_export(export, run_mode_is_production=True)

    def test_export_with_secret_in_demo_returns_report(self) -> None:
        from vet_manuscript_lab.services.export.types import (
            ExportManifest,
            ExportResult,
        )

        components = (
            _make_component(content="password=secret123"),
            _make_component(content="Clean text"),
        )
        export = ExportResult(
            manifest=ExportManifest(
                project_id="test",
                sign_off_id="so-1",
                artifact_versions=(),
                ai_usage={},
            ),
            components=components,
            package_hash="sha256:test",
            package_uri="mock://test",
        )
        report = scan_export(export, run_mode_is_production=False)
        assert report.total_secret_count >= 1
        assert report.has_critical


class TestSummarizeReport:
    def test_summary_structure(self) -> None:
        from vet_manuscript_lab.services.export.types import (
            ExportManifest,
            ExportResult,
        )

        components = (
            _make_component(filename="m.qmd", content="password=secret123"),
            _make_component(role="references", filename="r.bib", content="Clean"),
        )
        export = ExportResult(
            manifest=ExportManifest(
                project_id="test",
                sign_off_id="so-1",
                artifact_versions=(),
                ai_usage={},
            ),
            components=components,
            package_hash="sha256:test",
            package_uri="mock://test",
        )
        report = scan_export(export)
        summary = summarize_report(report)
        assert summary["total_components_scanned"] == 2
        assert summary["total_secrets"] >= 1
        assert summary["has_critical"] is True
        assert len(summary["component_summaries"]) == 2
        assert summary["component_summaries"][0]["has_critical"] is True


class TestScanExportContent:
    def test_returns_secrets_and_pii(self) -> None:
        content = "password=secret test@test.com"
        secrets, pii = scan_export_content(content)
        assert len(secrets) >= 1
        assert len(pii) >= 1

    def test_production_blocks_on_secret(self) -> None:
        content = "password=secret"
        with pytest.raises(PolicyViolation):
            scan_export_content(content, run_mode_is_production=True)


# ---------------------------------------------------------------------------
# Integration: full export generation + privacy scan
# ---------------------------------------------------------------------------


class TestExportGenerationWithPrivacyScan:
    def test_mock_export_clean_content(self) -> None:
        gen = MockExportGenerator()
        inputs = ExportInput(
            sections=(
                {
                    "section_id": "s1",
                    "section_type": "abstract",
                    "content": "Clean abstract text.",
                    "order": 0,
                    "word_count": 3,
                },
            ),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "so-1"},
            manuscript_summary={
                "manuscript_id": "test",
                "content_hash": "hash",
                "title": "Test",
            },
        )
        result = gen.generate(inputs)
        report = scan_export(result)
        assert report.total_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
