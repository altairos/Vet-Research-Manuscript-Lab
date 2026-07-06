# ADR-0008: Writing, Review, and Revision Architecture

Status: accepted

## Context

Phase 4 of the MVP requires generating manuscript sections from approved
evidence and statistical results, auditing every claim for support and
consistency, reviewing the manuscript for quality issues, and applying
controlled revisions based on human-dispositioned findings. The exit
criteria mandate:

- every factual claim traces back to an EvidenceItem or StatisticalResult;
- numbers in the manuscript match the official statistical results;
- associative language is not rewritten as causal;
- every revision has a finding, a diff, and a human disposition;
- revision limits, finding conflicts, or protocol changes escalate to humans.

This follows Phase 3 (Methodology and Statistics) so the writing pipeline
must consume locked plans, approved results, and audited evidence.

## Decision

1. **Eight new tables** (`manuscripts`, `manuscript_versions`,
   `manuscript_sections`, `claims`, `claim_supports`, `citations`,
   `review_findings`, `revision_decisions`) form the persistence layer.
   Migration `0004_writing_review_revision`.

2. **Writing policies** are pure functions in `domain/policies/writing.py`.
   Seven invariants: writing inputs approved, factual claim has support,
   numeric consistency, no causal overreach, finding before revision,
   revision within limit, and reviewer read-only.

3. **Service layer** uses Protocol-based injection:
   - `SectionWriter` Protocol + `MockSectionWriter` for deterministic
     section generation from evidence and results.
   - `Reviewer` Protocol + `MockReviewer` for policy-based finding
     generation.
   - `Reviser` Protocol + `MockReviser` for text corrections based on
     accepted findings.

4. **Workflow graph** extends `build_analysis_pipeline_graph` with five
   new nodes: `section_writing`, `claim_audit`, `review`,
   `review_approval`, and `revision`. Routing functions control the
   claim-audit → review → revision loop.

5. **Claim audit** runs automated policy checks (support, numeric
   consistency, causal overreach) before the reviewer stage. Failures
   route back to section writing for regeneration.

6. **Review approval** uses LangGraph `interrupt()` for human disposition
   of each finding (accept/reject/defer). Accepted findings trigger a
   revision cycle that returns to claim audit for re-verification.

7. **Revision loop** is bounded by `max_revision_rounds` (default 3).
   When the limit is reached, the workflow terminates and requires
   human escalation.

## Consequences

- The manuscript aggregate is versioned by content hash; any change
  produces a new version with a diff record.
- Claim support links create an audit trail from manuscript text back
  to evidence items and statistical results.
- The reviewer is strictly read-only; manuscript hash invariance is
  enforced by policy.
- Revision decisions are permanently recorded with reviewer identity,
  enabling post-hoc audit of the review process.
