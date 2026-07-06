# ADR-0006: Methodology and Statistics Architecture

Status: accepted

## Context

Phase 3 of the MVP requires locking the analysis plan and dataset version,
generating structured methodology findings, and producing reproducible
statistical results. The exit criteria mandate:

- runner only accepts approved/locked plan and locked dataset;
- same input + script + environment reproduces core results;
- unplanned analyses must be flagged `exploratory`;
- statistics Agent cannot modify models, variables, or exclusion rules
  during execution;
- failed runs retain logs but cannot produce approved results.

This follows Phase 2.5 (Model Gateway) so the Methodology Critic must
route through the gateway rather than calling a provider directly.

## Decision

1. **Eight new tables** (`datasets`, `dataset_versions`, `dataset_variables`,
   `analysis_plan_versions`, `analysis_plan_locks`, `methodology_findings`,
   `analysis_runs`, `statistical_results`) form the persistence layer.
   Migration `0003_methodology_statistics`.

2. **Analysis policies** are pure functions in `domain/policies/analysis.py`.
   Six invariants: locked dataset, locked plan, variable existence,
   exploratory marking, execution immutability, and failure safety.

3. **StatisticsRunner Protocol + MockStatisticsRunner** follow the Backend
   Protocol + lazy-loading pattern established by Zotero, PDF, and
   retrieval services. The mock is deterministic (same plan + same
   dataset + same seed = same results).

4. **Analysis graph extends the evidence pipeline** with five nodes:
   `methodology_critic -> analysis_plan -> analysis_plan_approval ->
   analysis_plan_lock -> statistics_execution`, plus `results_approval`.

5. **Plan and dataset locking** uses `LockRef` entries (lock_type
   `"analysis_plan"` and `"dataset"`) so the immutability invariant
   is enforced by the same lock mechanism as protocol locking.

6. **Methodology Critic** routes through `ModelGateway.invoke()` with
   `TaskKind.METHODOLOGY_CRITIC` (high_reasoning tier). When no gateway
   is supplied, deterministic mock findings are generated.

## Consequences

- The analysis pipeline is runnable offline with deterministic mock data.
- All Phase 3 exit criteria are covered by policy checks and tests.
- Real Python/R runner can be substituted via the `StatisticsRunner`
  Protocol without changing graph nodes.
- Adding a real Model Gateway provider requires no changes to the
  methodology critic node contract.
