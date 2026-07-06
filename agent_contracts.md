# Agent Contracts

## 1. Common contract

Every node receives `WorkflowState` plus explicit artifact references and returns
a partial state update. Nodes do not pass large payloads through graph state.

Common preconditions:

- project and workflow run are active;
- referenced content hashes validate;
- required inputs have the exact approval/lock status specified below;
- actor/tool permissions pass the policy layer.

Common output requirements:

- schema-valid JSON-compatible payload;
- immutable artifact version with provenance;
- agent run, prompt/model/tool invocation, and audit records;
- explicit warnings, uncertainties, and human-review flags.

Common failure classes:

- `VALIDATION_ERROR`: structured output or domain rule failure; repair/retry.
- `TRANSIENT_SERVICE_ERROR`: timeout/rate limit; bounded retry with backoff.
- `POLICY_VIOLATION`: prohibited input/action; no retry, escalate.
- `MISSING_APPROVAL`: pause or route to the required approval gate.
- `SOURCE_INSUFFICIENT`: persist a gap; do not invent content.
- `HUMAN_REVIEW_REQUIRED`: interrupt with a serializable review payload.

No agent may approve its own output, alter a locked object, overwrite a formal
artifact, fabricate a reference/result, or suppress a material warning.

## 2. Workflow node contracts

### Project Init

- **Input:** title, owners, species scope, candidate study type, data sensitivity.
- **Output:** `Project`, `WorkflowRun`, storage namespace, initial audit event.
- **Tools:** persistence and artifact-store initialization only.
- **Gate:** user confirms project scope and responsibility statement.
- **Escalate:** unsupported study type or unresolved sensitive-data handling.

### Research Question Agent

- **Input:** project brief and optional investigator notes.
- **Output:** versioned `ResearchQuestion` with PECO/PICO, primary/secondary
  objectives, target population, outcomes, assumptions, unresolved questions.
- **Tools:** terminology lookup only when configured; no external publication.
- **Gate:** human approval of question and study type.
- **Forbidden:** inferring endpoints from observed results.

### Guideline Mapping Agent

- **Input:** approved question, study type, intended report type.
- **Output:** `ProtocolVersion` draft and `GuidelineMapping` for STROBE-Vet,
  including applicability, required evidence, owner, and status per item.
- **Gate:** human approval, followed by `ProtocolLock` creation.
- **Forbidden:** marking compliance complete; silently changing the question.

### Literature Search Agent

- **Input:** locked protocol, eligibility criteria, approved information sources.
- **Output:** versioned search strategy, database-specific queries, dates,
  filters, deduplication policy, and search log.
- **Tools:** configured bibliographic APIs and Zotero API; read operations by
  default. API credentials never enter artifacts or graph state.
- **Gate:** human approval before formal retrieval/screening.
- **Escalate:** inaccessible database, ambiguous eligibility, material query gap.

### Screening Agent

- **Input:** approved search strategy and retrieved literature records.
- **Output:** title/abstract and full-text screening decisions with reason codes.
- **Tools:** metadata/full-text access within project scope.
- **Gate:** conflicts and low-confidence exclusions require human disposition.
- **Forbidden:** excluding a record without a recorded reason.

### Evidence Extraction Agent

- **Input:** included records, immutable attachments, extraction schema.
- **Output:** draft `EvidenceItem` objects linked to exact `SourceSpan` objects;
  extraction gaps and table-review flags.
- **Tools:** PDF parser, LlamaIndex hybrid retrieval, reranker.
- **Gate:** human/audit validation for complex tables, ambiguous units, numeric
  endpoints, and unsupported source locations.
- **Forbidden:** treating top-k chunks as verified evidence.

### Citation / Evidence Audit Agent

- **Input:** evidence items, source spans, attachments, citations or manuscript
  claims depending on workflow stage.
- **Output:** audit findings for existence, locator integrity, entailment,
  overreach, contradictory support, and quote-hash mismatch.
- **Tools:** retrieval and deterministic reference/hash checks.
- **Gate:** unresolved high-severity findings block downstream formal writing or
  final export.
- **Forbidden:** repairing evidence by inventing text or changing source data.

### Methodology Critic Agent

- **Input:** locked protocol, dataset dictionary/summary, evidence ledger,
  guideline mapping.
- **Output:** methodological findings and `AnalysisPlanVersion` draft covering
  populations, endpoints, confounding, missingness, exclusions, models,
  sensitivity analyses, and limitations.
- **Tools:** read-only domain references; no statistics execution.
- **Gate:** statistician/investigator approval, then `AnalysisPlanLock`.
- **Forbidden:** inspecting outcome results to optimize the primary plan.

### Statistics Agent

- **Input:** locked dataset version, locked approved analysis plan, fixed script
  version, runner configuration.
- **Output:** `AnalysisRun`, typed statistical results, tables/figures, logs, and
  reproducibility manifest.
- **Tools:** isolated R/Python runner only; MVP may use a declared mock runner.
- **Gate:** human approval of interpretation, not merely successful execution.
- **Forbidden:** changing variables/models/exclusions; promoting exploratory
  output to confirmatory; executing arbitrary model-generated code unsandboxed.

### Writing Agent

- **Input:** approved protocol, validated evidence, approved statistical results,
  reporting checklist, manuscript section request.
- **Output:** versioned section plus extracted `Claim`, `ClaimSupport`, and
  `Citation` records; explicit evidence gaps.
- **Tools:** evidence/result lookup and citation formatter only.
- **Gate:** claim/citation audit before a section becomes formal.
- **Forbidden:** unsupported facts, fabricated locators/DOIs, causal language for
  associations, or changing reported statistics.

### Reviewer Agent

- **Input:** assembled manuscript version, provenance graph, checklist, audits.
- **Output:** deduplicated `ReviewFinding` objects with severity, location,
  rationale, evidence, and proposed resolution—not direct manuscript edits.
- **Tools:** read-only manuscript/evidence/statistics access.
- **Gate:** user selects findings for revision or disposition.
- **Forbidden:** approving final compliance or expanding scope silently.

### Revision Agent

- **Input:** manuscript version and accepted review findings.
- **Output:** new manuscript/section versions, structured diff, claim/support
  changes, and finding-resolution links.
- **Tools:** same constrained evidence/result lookup as Writing Agent.
- **Gate:** material changes return to claim audit; protocol/analysis changes
  require amendment workflow. Revision loops are bounded.
- **Forbidden:** addressing rejected findings or modifying locked scientific
  inputs without an approved amendment.

### Final Compliance Audit

- **Input:** candidate final manuscript, all required audits, guideline mapping,
  approvals, figures/tables, references, AI usage and provenance records.
- **Output:** deterministic and model-assisted `ComplianceFinding` list,
  completeness report, export readiness status, unresolved-risk summary.
- **Tools:** validators, reference checker, Quarto preflight; no sign-off tool.
- **Gate:** authorized human sign-off. High-severity findings block export.
- **Forbidden:** declaring compliance or scientific validity autonomously.

### Export Service (non-agent)

- **Input:** signed-off exact artifact versions and journal template/config.
- **Output:** `manuscript.qmd`, `references.bib`, figures, tables, audit files,
  DOCX, manifest, AI usage log, and hash-addressed `ExportPackage`.
- **Tools:** Quarto/Pandoc and filesystem/object store.
- **Rule:** export must fail closed if a referenced version changed after sign-off.

## 3. Approval payload

Interrupt payloads are small and serializable and contain: gate type, subject
ID/version/hash, summary, warnings, proposed next stage, allowed decisions, and
required reviewer role. Resume input contains decision, reviewer identity,
comment, requested changes, and timestamp. The server verifies authorization;
the model never supplies reviewer identity or decision.

## 4. Revision stopping rules

The default maximum is three automated revision rounds. Stop earlier when no
accepted actionable findings remain. Escalate when findings conflict, require a
protocol/analysis amendment, remain high severity after two attempts, or require
scientific judgment unavailable to the system.

