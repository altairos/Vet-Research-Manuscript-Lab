# Vet Research Manuscript Lab — Agent Development Guide

## 1. Purpose

This repository implements an auditable, human-governed workflow for veterinary
medical manuscript development. The initial product scope is **canine/feline
retrospective observational clinical research**, aligned with **STROBE-Vet**.

The system assists researchers; it does not replace scientific, statistical,
ethical, or authorship judgment. No agent may claim that a manuscript is valid,
publishable, or compliant without explicit human sign-off.

## 2. Architectural invariants

These rules are mandatory:

1. **LangGraph owns workflow state, not document storage.** Graph state contains
   identifiers, status, decisions, and artifact references—not PDFs, full text,
   DataFrames, or binary exports.
2. **LlamaIndex returns candidate evidence, not facts.** Retrieved chunks must be
   converted to source spans and validated before becoming evidence items.
3. **Structured output is canonical.** JSON-compatible domain objects are the
   source of truth; Markdown, CSV, and DOCX are human-facing projections.
4. **Formal artifacts are immutable.** Changes create new versions with hashes
   and provenance links. Never overwrite an approved or locked version.
5. **Approval is enforced in code.** Prompts and UI warnings are not security or
   workflow controls. Downstream nodes must reject unapproved inputs.
6. **Claims require support.** Every factual manuscript claim must map to an
   evidence item or statistical result; citations must map to a Zotero item and,
   when full text is available, a source span.
7. **Locked scope cannot drift silently.** Agents may create amendment requests,
   but cannot modify a locked protocol, analysis plan, or dataset.
8. **Uncertainty must remain visible.** Missing evidence, extraction ambiguity,
   exploratory analysis, and unsupported interpretation must be labeled.

## 3. System boundaries

- **Streamlit UI:** project setup, artifact review, approvals, diffs, run status.
- **LangGraph:** node routing, interrupts, checkpoints, retries, resume behavior.
- **Domain services:** Zotero sync, search, PDF parsing, evidence processing,
  statistics runners, Quarto/Pandoc export.
- **Storage:** SQLite for local MVP; PostgreSQL for multi-user deployment;
  filesystem/object storage for immutable artifacts and exports.
- **Model gateway:** model calls, structured validation, model/prompt versions,
  usage, cost, timeout, and retry policy.
- **Policy/guardrail layer:** approval gates, lock rules, evidence requirements,
  prohibited actions, and escalation conditions.

## 4. Canonical workflow

```text
Project Init
  -> Research Question
  -> Human approval: question and study type
  -> Protocol / Guideline Mapping
  -> Human approval: protocol, endpoints, eligibility, guideline
  -> Protocol Lock
  -> Literature Search
  -> Human approval: search strategy and eligibility criteria
  -> Screening & Evidence Extraction
  -> Citation / Evidence Audit
  -> Methodology Critic
  -> Human approval: methodology and statistical analysis plan
  -> Analysis Plan Lock
  -> Statistics Execution
  -> Human approval: results interpretation
  -> Writing
  -> Citation / Claim Audit
  -> Reviewer
  -> Revision Loop (bounded)
  -> Citation / Claim Audit
  -> Final Compliance Audit
  -> Human sign-off and export
```

## 5. Agent implementation contract

Every agent/node must declare:

- typed input and output schemas;
- artifact types it may read and create;
- tools it may invoke;
- required approval and lock preconditions;
- deterministic validation performed after model output;
- retryable and non-retryable failures;
- escalation conditions;
- idempotency behavior.

Model output must be validated before persistence. A failed validation must not
be converted into a formal artifact. Side effects before a LangGraph interrupt
must be idempotent.

## 6. Data and provenance rules

- Use stable UUID/ULID identifiers; never use filenames as identity.
- Store UTC timestamps in ISO 8601 format.
- Hash artifact payloads, datasets, scripts, attachments, and quoted source text.
- Record prompt version, model identifier, model parameters, tool invocations,
  source artifact IDs, and agent run ID for every generated artifact.
- Store secrets only in environment/configuration secret stores; never in graph
  state, artifacts, logs, fixtures, or committed files.
- Zotero is a reference manager, not the evidence ledger. Do not access or mutate
  Zotero's SQLite database directly; use its supported API.

## 7. Statistics rules

- An `AnalysisRun` requires an approved `AnalysisPlanVersion` and a locked
  `DatasetVersion`.
- The runner cannot modify models, variables, exclusion criteria, or endpoints.
- Record dataset hash, script hash, plan version, package versions, random seed,
  environment, stdout/stderr, exit status, and generated artifacts.
- Exploratory analyses are allowed only when labeled `exploratory`; they cannot
  be silently promoted to primary results.

## 8. Development practices

- Keep domain logic independent of Streamlit and model providers.
- Prefer pure functions for routing, policy checks, and schema validation.
- Keep graph nodes small; orchestration and domain operations are separate.
- Use database transactions for artifact metadata plus provenance relationships.
- Do not catch broad exceptions without preserving the original error context.
- Tests must cover interrupt/resume, idempotency, approval bypass, immutable
  versions, misleading citations, claim inflation, and reproducible analysis.

## 9. MVP completion criteria

1. A run can pause and resume at every approval gate.
2. Every formal artifact has an immutable version, hash, and provenance.
3. Unapproved artifacts cannot enter downstream formal writing.
4. Every factual claim resolves to evidence or a statistical result.
5. Every citation resolves to a Zotero item and available PDF source span.
6. Every result resolves to dataset, script, environment, and analysis plan.
7. Every revision has a finding, diff, and recorded human disposition.
8. Export includes manuscript, references, figures/tables, checklist, AI usage
   log, and provenance package.

