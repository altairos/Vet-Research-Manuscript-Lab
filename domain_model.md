# Domain Model

## 1. Scope and conventions

This model supports the MVP workflow for canine/feline retrospective
observational clinical studies. The canonical representation is structured and
JSON-compatible. Markdown, CSV, and DOCX are projections or export formats.

Identifiers are stable UUIDs/ULIDs. Timestamps are UTC ISO 8601 values. Every
versioned payload has a SHA-256 content hash. “Formal” means eligible for use by
a downstream scientific step; formal artifacts must be approved where required.

## 2. Aggregate boundaries

### Project aggregate

`Project` is the ownership and authorization boundary.

| Entity | Purpose | Key fields |
|---|---|---|
| `Project` | Research workspace | id, title, study_type, species, status, owner_id |
| `ProjectMember` | Role assignment | project_id, user_id, role |
| `WorkflowRun` | One execution lineage | id, project_id, thread_id, status, current_stage |
| `Approval` | Human decision | subject_type/id/version, decision, reviewer_id, comment, decided_at |
| `AmendmentRequest` | Controlled change to locked scope | target_id/version, rationale, impact, status |

An approval applies to an exact subject version and becomes stale when a new
version is created. Rejection never deletes the reviewed version.

### Artifact and provenance aggregate

| Entity | Purpose | Key fields |
|---|---|---|
| `Artifact` | Stable logical identity | id, project_id, artifact_type |
| `ArtifactVersion` | Immutable content version | artifact_id, version, uri, media_type, hash, status |
| `ProvenanceLink` | Directed derivation edge | source_version_id, target_version_id, relation |
| `AgentRun` | One node attempt | agent_type, prompt_version_id, input/output IDs, status |
| `ModelInvocation` | LLM audit record | provider, model, parameters, usage, request/response hashes |
| `ToolInvocation` | External action record | tool, arguments_hash, result_hash, status, timing |
| `AuditEvent` | Append-only security/scientific event | actor, action, target, outcome, metadata |
| `ExportPackage` | Final immutable bundle | manifest, component versions, package hash, sign-off ID |

Allowed artifact states are `draft`, `in_review`, `approved`, `rejected`,
`locked`, `superseded`, and `failed`. Approved or locked versions are immutable.

### Protocol aggregate

| Entity | Purpose | Key fields |
|---|---|---|
| `ResearchQuestion` | PECO/PICO and objectives | population, exposure/intervention, comparator, outcomes |
| `ProtocolVersion` | Study scope | design, endpoints, eligibility, variables, limitations |
| `GuidelineMapping` | Reporting requirements | guideline/version, checklist items, applicability |
| `ProtocolLock` | Scope freeze | protocol_version_id, approval_id, locked_at |

Once locked, endpoints, eligibility criteria, research question, and study type
can change only through an approved amendment that creates a new protocol
version and explicitly invalidates affected downstream artifacts.

### Literature and evidence aggregate

| Entity | Purpose | Key fields |
|---|---|---|
| `SearchStrategyVersion` | Reproducible search | databases, query strings, dates, filters, eligibility version |
| `LiteratureRecord` | Local bibliographic identity | DOI/PMID/title, Zotero identifiers, metadata |
| `AttachmentVersion` | Immutable source file | literature_record_id, attachment_key, hash, local/object URI |
| `ScreeningDecision` | Inclusion decision | record_id, stage, decision, reason, reviewer |
| `SourceSpan` | Exact source location | record_id, attachment version, page/section/chunk/offsets, quote hash |
| `EvidenceItem` | Validatable extracted evidence | concept, value, units, population, certainty, source_span_ids |
| `RetrievalRun` | Candidate-generation record | query, index version, parameters, candidate scores |

Retrieval results are not evidence. An `EvidenceItem` requires at least one
`SourceSpan`, validation status, and extraction provenance. Complex table
extractions default to `needs_human_review` in the MVP.

Zotero fields retained locally include library ID/type/version, item key/version,
DOI, PMID, title, creators, year, journal, attachment key/hash, local path,
BibTeX key, and sync status. Zotero is not the evidence source of truth.

### Dataset and statistics aggregate

| Entity | Purpose | Key fields |
|---|---|---|
| `Dataset` | Stable dataset identity | id, project_id, name |
| `DatasetVersion` | Immutable analysis input | schema, row count, uri, hash, status |
| `DatasetVariable` | Variable dictionary | name, type, unit, missing code, role |
| `AnalysisPlanVersion` | Prespecified analysis | endpoints, populations, models, exclusions, missingness |
| `AnalysisPlanLock` | Approved plan freeze | plan_version_id, approval_id, locked_at |
| `AnalysisRun` | Reproducible execution | plan/dataset/script versions, environment, seed, status |
| `StatisticalResult` | Typed result | estimand, estimate, uncertainty, p value, units, run ID |
| `TableFigure` | Generated display artifact | type, caption, source result IDs, artifact version |

An `AnalysisRun` may start only when its analysis plan is approved/locked and
its dataset version is locked. It records dataset hash, script hash, package
versions, seed, environment, stdout/stderr, exit status, and output IDs.
Exploratory results carry `analysis_class=exploratory` through writing and audit.

### Manuscript aggregate

| Entity | Purpose | Key fields |
|---|---|---|
| `Manuscript` | Stable manuscript identity | id, project_id, target_journal |
| `ManuscriptVersion` | Immutable assembled draft | section versions, citation set, hash, status |
| `ManuscriptSection` | Versioned section | section_type, content URI, order, hash |
| `Claim` | Manuscript assertion | section/version, sentence/span, type, certainty, status |
| `ClaimSupport` | Claim-to-source relation | claim_id, support_type/id, relation, audit status |
| `Citation` | Citation occurrence | claim/section, literature record, locator, citation key |
| `ReviewFinding` | Actionable critique | category, severity, location, rationale, status |
| `RevisionDecision` | Human disposition | finding_id, accept/reject/defer, reason, reviewer |
| `ComplianceFinding` | Checklist/audit outcome | rule, status, evidence, human review requirement |

`EvidenceItem` represents what a source reports; `Claim` represents what the
manuscript asserts. They must remain separate. A factual claim requires support
from an evidence item or statistical result. An interpretation may link both but
must retain calibrated certainty. A citation alone does not prove support.

## 3. Critical relationships

```text
ProtocolVersion --approved/locked--> ProtocolLock
SearchStrategyVersion -----------> ProtocolVersion
LiteratureRecord -----------------> Zotero item
EvidenceItem ---------------------> SourceSpan -> AttachmentVersion
AnalysisRun -> AnalysisPlanVersion + DatasetVersion + ScriptVersion
StatisticalResult ----------------> AnalysisRun
Claim -> ClaimSupport -> EvidenceItem | StatisticalResult
Citation -> LiteratureRecord -> SourceSpan (when full text exists)
ManuscriptVersion ----------------> ManuscriptSection versions
ExportPackage --------------------> exact approved artifact versions
```

## 4. Policy invariants

1. Downstream formal nodes read only approved inputs required by their contract.
2. Locked entities are never updated in place.
3. Every mutation attempt and approval decision emits an `AuditEvent`.
4. A content hash mismatch invalidates the version and blocks downstream use.
5. Agent/model output cannot create an `Approval` or human sign-off.
6. Final audit reports findings; only an authorized human can sign off.
7. Revision is bounded and each material change links to a review finding or an
   approved amendment request.
8. Deleting metadata never deletes referenced immutable payloads; retention and
   privacy policies govern physical deletion separately.

## 5. MVP storage mapping

- SQLite/PostgreSQL: identities, versions, relations, approvals, locks, audit.
- Artifact store: Markdown, JSON, CSV, PDFs, scripts, logs, tables, figures,
  Quarto sources, DOCX, and export bundles.
- Retrieval index: disposable derived index keyed by attachment and chunk hashes.
- LangGraph checkpointer: thread/run state and resumable execution cursor only.

