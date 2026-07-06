# ADR-0009: Compliance, Sign-Off, and Export Architecture

Status: accepted

## Context

Phase 5 of the MVP requires a final compliance audit against the STROBE-Vet
checklist, human sign-off binding exact artifact versions, and an immutable
hash-addressed export package. The exit criteria mandate:

- high-severity unresolved findings block sign-off and export;
- sign-off binds exact artifact versions; any post-sign-off hash change
  causes export to fail-closed;
- the export package contains a manifest, AI usage log, and all artifact hashes;
- the export package is an immutable hash-addressed bundle.

This follows Phase 4 (Writing, Review, and Revision) so the compliance
pipeline must consume the reviewed manuscript, audited claims, and all
upstream artifacts.

## Decision

1. **Two new tables** (`compliance_findings`, `export_packages`) form the
   persistence layer. Migration `0005_compliance_export`.

2. **Compliance policies** are pure functions in
   `domain/policies/compliance.py`. Five invariants: no blocking findings,
   checklist complete, sign-off preconditions, export version integrity
   (fail-closed), and export package completeness. Each raises
   `PolicyViolation` on breach.

3. **Protocol injection** (`ComplianceAuditor`, `ExportGenerator`) with
   deterministic mock implementations (`MockComplianceAuditor`,
   `MockExportGenerator`) enables offline development and testing without
   external services.

4. **STROBE-Vet checklist** is hardcoded as 22 `STROBEItem` dataclasses in
   `services/compliance/strobe_checklist.py`, covering Title/Abstract,
   Introduction, Methods, Results, Discussion, and Other categories.

5. **Graph nodes** in `compliance_graph.py`:
   - `final_compliance_audit_node`: runs auditor, stores findings + readiness.
   - `route_compliance_audit_decision`: ready → sign-off; blocked → blocked
     termination; not_ready → rewrite.
   - `final_sign_off_node`: interrupt for authorised human sign-off; records
     artifact hash binding.
   - `route_sign_off_decision`: approved → export; rejected → rewrite.
   - `export_node`: generates package, verifies hash integrity (fail-closed),
     validates completeness, sets run_status to complete.

6. **Sign-off binding** captures all artifact content hashes at approval
   time. The export node re-reads current hashes and rejects any mismatch.

7. **Export package** is assembled by `MockExportGenerator` into four
   components: `manuscript.qmd` (Quarto markdown), `references.bib`
   (BibTeX), `manifest.json` (artifact versions + hashes), and
   `ai_usage.json`. Package hash is SHA-256 of all component hashes.

## Consequences

- The compliance pipeline extends the writing pipeline graph via
  `_make_writing_builder()`, allowing the compliance graph to override
  routing edges without duplicating node definitions.
- Blocking compliance findings immediately terminate the pipeline in a
  "blocked" state, requiring human escalation.
- Sign-off rejection or non-blocking compliance issues route back to
  section writing for rewriting and re-audit.
- The `_enrich_for_audit` helper bridges the gap between the mock writer
  (which links citations to sections) and the auditor (which checks
  per-claim citation coverage) by synthesizing claim-level citation
  references.
