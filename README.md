# Vet Research Manuscript Lab

An auditable, human-in-the-loop workflow for developing veterinary medical
manuscripts with Python, LangGraph, Zotero, LlamaIndex, Streamlit, and
Quarto/Pandoc.

## Product scope

The first release targets **canine/feline retrospective observational clinical
studies** and **STROBE-Vet** reporting. Inputs are a CSV/Excel case table, a
Zotero library, and a limited set of PDFs. Planned outputs are:

- evidence ledger;
- approved statistical analysis plan;
- reviewer critique and revision record;
- claim/citation audit;
- manuscript draft;
- DOCX and provenance package.

The first vertical slice may use a simulated statistics runner. Real R/Python
execution is introduced only after approval, lock, and provenance controls work
end to end.

## Design goals

- Human approval at scientifically consequential decisions.
- Immutable, versioned, hash-addressed formal artifacts.
- Sentence-to-evidence and result-to-analysis provenance.
- Recoverable workflow execution through LangGraph checkpoints.
- Provider-neutral domain logic and structured agent output.
- Explicit uncertainty instead of plausible but unsupported prose.

## Architecture

```text
Streamlit UI
    |
Policy / Guardrails -------- Model Gateway
    |                              |
LangGraph Orchestration ---- Agent Nodes
    |
Domain Services
    |-- Zotero API
    |-- LlamaIndex retrieval
    |-- PDF/source-span extraction
    |-- R/Python analysis runner
    `-- Quarto/Pandoc exporter
    |
Storage
    |-- SQLite (MVP) / PostgreSQL
    |-- immutable artifact store
    `-- retrieval index
```

LangGraph state stores small JSON-compatible references and decisions. Large or
canonical content belongs in the artifact store and domain database.

## Workflow

The workflow locks the protocol and analysis plan after human approval. Later
agents can request an amendment but cannot silently modify locked scope.

```text
Question -> protocol approval -> protocol lock
         -> search approval -> screening/extraction -> evidence audit
         -> methods/SAP approval -> analysis-plan lock -> statistics
         -> interpretation approval -> writing -> claim audit
         -> review/revision (bounded) -> final audit -> human sign-off -> export
```

## Repository blueprint

The initial design documents are:

- `AGENT.md` — mandatory engineering and agent behavior rules.
- `DEVELOPMENT.md` — phased implementation process, quality gates, and MVP
  acceptance workflow.
- `domain_model.md` — entities, lifecycles, relations, and invariants.
- `agent_contracts.md` — inputs, outputs, tools, gates, and failures per node.
- `src/vet_manuscript_lab/workflow/state.py` — serializable LangGraph state and transition types.

The planned implementation structure is:

```text
src/vet_manuscript_lab/
  domain/          # entities, policies, validation
  workflow/        # LangGraph graph, nodes, routing
  services/        # Zotero, retrieval, PDF, analysis, export
  infrastructure/  # database, artifact store, model gateway
  ui/              # Streamlit pages and presenters
tests/
  unit/
  integration/
  adversarial/
artifacts/         # local development only; ignored by Git
```

## Delivery phases

1. **Foundation:** schemas, artifact/version model, policy checks, checkpointed
   mock graph, Streamlit approval screens.
2. **Evidence:** Zotero sync, PDF ingestion, hybrid retrieval, source spans,
   evidence ledger, citation audit.
3. **Methods and analysis:** analysis-plan versioning, dataset lock, simulated
   then isolated R/Python runner, reproducibility manifest.
4. **Writing and review:** section drafting, claim support, bounded revision,
   human disposition of findings.
5. **Compliance and export:** STROBE-Vet checklist, consistency checks, Quarto
   DOCX, references, figures/tables, AI log, provenance bundle.
6. **Production:** PostgreSQL, authentication/authorization, background jobs,
   object storage, observability, backup and deployment.


## Development setup

Python 3.12 or later is required. On Windows, bootstrap the local environment
and run all Phase 0 quality gates with:

```powershell
& .\tools\bootstrap.ps1
```

After setup, rerun lint, formatting, type checks, and tests with:

```powershell
& .\tools\check.ps1
```


## Foundation UI

Phase 1 provides a checkpointed mock workflow from project initialization through
research-question approval, protocol review, and protocol lock. Start it with:

```powershell
& .\tools\run-streamlit.ps1
```

The local UI persists project/governance records in SQLite, immutable payloads
under `artifacts/`, and LangGraph checkpoints in a separate SQLite file.

## Quality gates

The test suite will include schema and routing tests, checkpoint resume tests,
idempotency tests, approval-bypass attempts, immutable-version tests,
adversarial citation tests, claim-inflation tests, statistical reproducibility,
and Quarto export regression tests.

## Safety statement

This software is research-writing assistance. Human investigators retain
responsibility for study design, data quality, statistical interpretation,
ethics, authorship, reporting compliance, and submission decisions.

