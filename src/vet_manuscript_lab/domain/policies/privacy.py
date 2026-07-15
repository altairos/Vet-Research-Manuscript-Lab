"""Pure privacy/redaction policies for log scrubbing, PII detection, and secret
redaction.

These functions are used:

* Before logging workflow state, config values, or error messages.
* Before writing export package content to prevent PII leakage.
* In production mode to detect un-redacted secrets before they reach
  audit trails.

All functions are pure and side-effect free, making them unit-testable
without any I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation

# ---------------------------------------------------------------------------
# Regex patterns for common secret formats
# ---------------------------------------------------------------------------

# API keys: long alphanumeric strings (40+ chars) that look like tokens
_API_KEY_PATTERN = re.compile(
    r"\b(?:sk-|pk-|api[_-]?key[_-]?)?[a-zA-Z0-9]{40,}\b",
    re.IGNORECASE,
)

# AWS access keys (20 chars, starts with AKIA)
_AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

# AWS secret keys (40 chars base64-ish after "secret" label)
_AWS_SECRET_PATTERN = re.compile(
    r"(?:aws[_-]?secret[_-]?access[_-]?key|secret)"
    r"['\"]?\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9/+=]{40})",
    re.IGNORECASE,
)

# Generic password in URL: protocol://user:password@host
_URL_CRED_PATTERN = re.compile(
    r"(https?://[^:/\s]+:)([^@/\s]+)(@)",
)

# Generic key-value password: password=..., pwd=..., passwd=...
_KV_PASSWORD_PATTERN = re.compile(
    r"\b(?:password|passwd|pwd|secret|token|apikey|api_key)"
    r"(?:\s*[:=]\s*)(['\"]?)([^\s'\",;]+)",
    re.IGNORECASE,
)

# Bearer tokens in Authorization headers
_BEARER_PATTERN = re.compile(
    r"(?:bearer|authorization)\s*[:=]\s*([A-Za-z0-9\-_\.=]+)",
    re.IGNORECASE,
)

# Email addresses (common PII in veterinary data)
_EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",
)

# Phone numbers (basic international format)
_PHONE_PATTERN = re.compile(
    r"\b(?:\+\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}\b"
)

# Credit card numbers (basic 13-19 digit groups)
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """A single privacy issue detected in content."""

    finding_type: str  # "secret_api_key", "pii_email", etc.
    match_text: str  # the matched text (truncated)
    start: int
    end: int
    severity: str  # "critical" (secret) or "warning" (PII)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Result of a redaction operation."""

    redacted_text: str
    findings: tuple[PrivacyFinding, ...]
    redaction_count: int


# ---------------------------------------------------------------------------
# URL credential redaction
# ---------------------------------------------------------------------------


def redact_url(url: str) -> str:
    """Remove embedded credentials from a URL for safe logging.

    ``postgresql://user:secret@host:5432/db`` -> ``postgresql://user:***@host:5432/db``
    """

    if "@" not in url:
        return url
    parts = url.split("://", 1)
    if len(parts) != 2:
        return url
    scheme, rest = parts
    if "@" not in rest:
        return url
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{host}"


# ---------------------------------------------------------------------------
# Secret detection and redaction
# ---------------------------------------------------------------------------


def scan_for_secrets(text: str) -> list[PrivacyFinding]:
    """Detect potential secrets/API keys/passwords in *text*.

    Returns a list of findings sorted by position.
    """

    findings: list[PrivacyFinding] = []

    for m in _AWS_KEY_PATTERN.finditer(text):
        findings.append(
            PrivacyFinding(
                finding_type="secret_aws_key",
                match_text=m.group()[:20] + "...",
                start=m.start(),
                end=m.end(),
                severity="critical",
            )
        )

    for m in _AWS_SECRET_PATTERN.finditer(text):
        findings.append(
            PrivacyFinding(
                finding_type="secret_aws_secret",
                match_text=m.group()[:20] + "...",
                start=m.start(),
                end=m.end(),
                severity="critical",
            )
        )

    for m in _KV_PASSWORD_PATTERN.finditer(text):
        findings.append(
            PrivacyFinding(
                finding_type="secret_password",
                match_text=m.group(2)[:20] + "...",
                start=m.start(2),
                end=m.end(2),
                severity="critical",
            )
        )

    for m in _BEARER_PATTERN.finditer(text):
        findings.append(
            PrivacyFinding(
                finding_type="secret_bearer_token",
                match_text=m.group(1)[:20] + "...",
                start=m.start(1),
                end=m.end(1),
                severity="critical",
            )
        )

    findings.sort(key=lambda f: f.start)
    return findings


def redact_secrets(text: str) -> RedactionResult:
    """Replace all detected secrets in *text* with ``[REDACTED]``.

    Returns a :class:`RedactionResult` with the scrubbed text and the
    original findings for audit purposes.
    """

    findings = scan_for_secrets(text)
    if not findings:
        return RedactionResult(redacted_text=text, findings=(), redaction_count=0)

    # Redact from end to start so offsets stay valid
    result = text
    for f in reversed(findings):
        result = result[: f.start] + _REDACTED + result[f.end :]

    return RedactionResult(
        redacted_text=result,
        findings=tuple(findings),
        redaction_count=len(findings),
    )


# ---------------------------------------------------------------------------
# PII detection and redact
# ---------------------------------------------------------------------------


def scan_for_pii(text: str) -> list[PrivacyFinding]:
    """Detect email addresses, phone numbers, and credit card numbers.

    Returns a list of findings sorted by position.
    """

    findings: list[PrivacyFinding] = []

    for m in _EMAIL_PATTERN.finditer(text):
        findings.append(
            PrivacyFinding(
                finding_type="pii_email",
                match_text=m.group()[:30],
                start=m.start(),
                end=m.end(),
                severity="warning",
            )
        )

    for m in _CREDIT_CARD_PATTERN.finditer(text):
        digits = re.sub(r"[^\d]", "", m.group())
        if len(digits) >= 13:
            findings.append(
                PrivacyFinding(
                    finding_type="pii_credit_card",
                    match_text=m.group()[:20] + "...",
                    start=m.start(),
                    end=m.end(),
                    severity="warning",
                )
            )

    # Phone numbers: only flag if they look like real numbers (10+ digits)
    for m in _PHONE_PATTERN.finditer(text):
        digits = re.sub(r"[^\d]", "", m.group())
        if len(digits) >= 10:
            findings.append(
                PrivacyFinding(
                    finding_type="pii_phone",
                    match_text=m.group()[:20],
                    start=m.start(),
                    end=m.end(),
                    severity="warning",
                )
            )

    findings.sort(key=lambda f: f.start)
    return findings


def redact_pii(text: str) -> RedactionResult:
    """Replace email addresses and phone numbers with ``[REDACTED]``."""

    findings = scan_for_pii(text)
    if not findings:
        return RedactionResult(redacted_text=text, findings=(), redaction_count=0)

    result = text
    for f in reversed(findings):
        result = result[: f.start] + _REDACTED + result[f.end :]

    return RedactionResult(
        redacted_text=result,
        findings=tuple(findings),
        redaction_count=len(findings),
    )


# ---------------------------------------------------------------------------
# Combined sanitisation
# ---------------------------------------------------------------------------


def sanitize_text(text: str) -> RedactionResult:
    """Apply both secret and PII redaction in a single pass.

    This is the main entry point for scrubbing text before logging or
    writing to export artifacts.
    """

    secret_result = redact_secrets(text)
    pii_result = redact_pii(secret_result.redacted_text)

    all_findings = secret_result.findings + pii_result.findings
    total = secret_result.redaction_count + pii_result.redaction_count

    return RedactionResult(
        redacted_text=pii_result.redacted_text,
        findings=all_findings,
        redaction_count=total,
    )


# ---------------------------------------------------------------------------
# Structured dict sanitisation
# ---------------------------------------------------------------------------


def sanitize_dict(
    data: dict[str, object],
    *,
    sensitive_keys: frozenset[str] | None = None,
) -> dict[str, object]:
    """Recursively sanitise a dictionary for safe logging.

    Values associated with *sensitive_keys* (default: password, token,
    api_key, secret, zotero_api_key) are replaced with ``[REDACTED]``.
    All other string values are passed through :func:`sanitize_text`.
    """

    if sensitive_keys is None:
        sensitive_keys = _DEFAULT_SENSITIVE_KEYS

    result: dict[str, object] = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if key_lower in sensitive_keys:
            result[key] = _REDACTED
        elif isinstance(value, str):
            result[key] = sanitize_text(value).redacted_text
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, sensitive_keys=sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, sensitive_keys=sensitive_keys)
                if isinstance(item, dict)
                else sanitize_text(str(item)).redacted_text
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value

    return result


_DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "zotero_api_key",
        "authorization",
        "bearer",
    }
)


# ---------------------------------------------------------------------------
# Production enforcement
# ---------------------------------------------------------------------------


def require_no_secrets_in_export(
    text: str,
    *,
    run_mode_is_production: bool,
) -> list[PrivacyFinding]:
    """In production mode, block export if secrets are detected.

    Returns the list of secret findings (empty if none found).
    Raises :class:`PolicyViolation` in production mode if any
    critical-severity secret is present.
    """

    findings = scan_for_secrets(text)
    if run_mode_is_production and findings:
        critical = [f for f in findings if f.severity == "critical"]
        if critical:
            raise PolicyViolation(
                f"Export blocked: {len(critical)} potential secret(s) "
                f"detected in manuscript content; production mode "
                f"requires manual review and redaction"
            )
    return findings


__all__ = [
    "PrivacyFinding",
    "RedactionResult",
    "redact_pii",
    "redact_secrets",
    "redact_url",
    "require_no_secrets_in_export",
    "sanitize_dict",
    "sanitize_text",
    "scan_for_pii",
    "scan_for_secrets",
]
