"""Repository-wide identifiers, timestamps, hashes, and stable codes."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum

SCHEMA_VERSION = "1.0.0"
HASH_ALGORITHM = "sha256"


class ArtifactType(StrEnum):
    RESEARCH_QUESTION = "research_question"
    PROTOCOL = "protocol"
    GUIDELINE_MAPPING = "guideline_mapping"
    SEARCH_STRATEGY = "search_strategy"
    EVIDENCE_LEDGER = "evidence_ledger"
    ANALYSIS_PLAN = "analysis_plan"
    DATASET = "dataset"
    ANALYSIS_RESULT = "analysis_result"
    MANUSCRIPT_SECTION = "manuscript_section"
    MANUSCRIPT = "manuscript"
    AUDIT_REPORT = "audit_report"
    EXPORT_PACKAGE = "export_package"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    TRANSIENT_SERVICE_ERROR = "transient_service_error"
    POLICY_VIOLATION = "policy_violation"
    MISSING_APPROVAL = "missing_approval"
    SOURCE_INSUFFICIENT = "source_insufficient"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    HASH_MISMATCH = "hash_mismatch"
    EXECUTION_ERROR = "execution_error"


def new_id() -> str:
    """Return a globally unique, opaque identifier."""

    return str(uuid.uuid4())


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp in canonical ISO 8601 form."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    """Return an algorithm-qualified content digest."""

    return f"{HASH_ALGORITHM}:{hashlib.sha256(payload).hexdigest()}"
