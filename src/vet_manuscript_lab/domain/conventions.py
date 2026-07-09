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
    SCREENING_RESULT = "screening_result"
    EVIDENCE_LEDGER = "evidence_ledger"
    LITERATURE_BATCH = "literature_batch"
    ANALYSIS_PLAN = "analysis_plan"
    DATASET = "dataset"
    DATASET_DICTIONARY = "dataset_dictionary"
    ANALYSIS_RESULT = "analysis_result"
    MANUSCRIPT_SECTION = "manuscript_section"
    MANUSCRIPT = "manuscript"
    REVIEWER_CRITIQUE = "reviewer_critique"
    GUIDELINE_CHECKLIST = "guideline_checklist"
    CITATION_AUDIT = "citation_audit"
    AI_USAGE_LOG = "ai_usage_log"
    AUDIT_REPORT = "audit_report"
    EXPORT_PACKAGE = "export_package"
    ARGUMENT_SPINE = "argument_spine"


class RunMode(StrEnum):
    """Determines whether mock fallbacks are permitted.

    - ``DEMO`` (default): mock fallbacks allowed — for local development
      and the golden-project demo.
    - ``TEST``: fixture/mock fallbacks allowed but must be explicitly
      tagged; used by automated test suites.
    - ``PRODUCTION``: mock fallbacks forbidden.  Any node that would
      fall back to a mock raises a fail-closed error instead.
    """

    DEMO = "demo"
    TEST = "test"
    PRODUCTION = "production"


RUN_MODE_ENV = "VET_LAB_RUN_MODE"


class EvidenceType(StrEnum):
    """Structured classification for evidence items.

    Each type corresponds to a different kind of scientific claim and
    has its own required-field validation rules (see
    ``domain/policies/evidence.py``).
    """

    SAMPLE_CHARACTERISTIC = "sample_characteristic"
    DIAGNOSTIC_CRITERION = "diagnostic_criterion"
    EXPOSURE_OR_INTERVENTION = "exposure_or_intervention"
    OUTCOME_DEFINITION = "outcome_definition"
    STATISTICAL_RESULT = "statistical_result"
    ADVERSE_EVENT = "adverse_event"
    LIMITATION = "limitation"
    MECHANISTIC_HYPOTHESIS = "mechanistic_hypothesis"
    GUIDELINE_REQUIREMENT = "guideline_requirement"
    BACKGROUND_CLAIM = "background_claim"


def run_mode_allows_mock(mode: RunMode) -> bool:
    """Return ``True`` when *mode* permits mock fallbacks."""

    return mode != RunMode.PRODUCTION


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
