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

The first vertical slice uses a deterministic mock statistics runner. Real
R/Python execution is introduced only after approval, lock, and provenance
controls work end to end.

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
Policy / Guardrails -------- Model Gateway (Router Agent)
    |                              |
LangGraph Orchestration ---- Agent Nodes
    |
Domain Services
    |-- Zotero API
    |-- LlamaIndex retrieval
    |-- PDF/source-span extraction
    |-- R/Python analysis runner (mock-first)
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
         -> methodology critic -> analysis-plan approval -> analysis-plan lock
         -> statistics execution -> results approval
         -> writing -> claim audit
         -> review/revision (bounded) -> final audit -> human sign-off -> export
```

Every interrupt checkpoint is serializable, so the workflow can resume from any
approval gate after a process restart.

## Repository blueprint

```text
src/vet_manuscript_lab/
  domain/
    conventions.py    # IDs, timestamps, hashes, ArtifactType enum
    policies/         # pure policy functions (foundation, evidence, analysis)
  workflow/
    state.py          # WorkflowState TypedDict + stage transitions
    foundation_graph.py    # PROJECT_INIT → PROTOCOL_LOCK
    literature_graph.py    # LITERATURE_SEARCH → EVIDENCE_AUDIT
    analysis_graph.py      # METHODOLOGY_CRITIC → RESULTS_APPROVAL
  services/
    zotero/           # Zotero API client + mapper + synchroniser
    retrieval/        # chunker + hybrid retriever (BM25 / LlamaIndex)
    documents/        # PDF parser + importer
    analysis/         # dictionary + importer + statistics runner
    export/           # (Phase 5)
  infrastructure/
    database/         # SQLAlchemy ORM + Alembic migrations
    artifacts/        # content-addressed artifact store
    checkpoints/      # LangGraph SQLite checkpointer
    model_gateway/    # Router Agent + providers + pricing + usage
  ui/
    app.py            # Streamlit entry point
    i18n.py           # bilingual labels
tests/
  test_*.py           # unit, integration, and adversarial tests
fixtures/
  golden_project/     # synthetic dataset + analysis plan + literature
artifacts/            # local development only; ignored by Git
migrations/
  versions/           # Alembic migrations (0001–0002)
docs/
  adr/                # Architecture Decision Records (0001–0007)
```

## Delivery phases

### Completed

1. **Phase 0 — Engineering baseline** ✅
   Python 3.12 + src layout, pyproject.toml, Alembic, Ruff, mypy, pytest,
   ADR-0001–0005, golden project fixture skeleton.

2. **Phase 1 — Foundation vertical slice** ✅
   Project init → research-question approval → guideline mapping →
   protocol approval → protocol lock. Checkpointed mock LangGraph,
   Streamlit approval screens, policy checks, artifact versioning.

3. **Phase 2 — Literature & evidence vertical slice** ✅
   Zotero API v3 sync, PDF import and parsing, text chunker, LlamaIndex
   hybrid retrieval, source spans, evidence ledger, citation audit.
   Full graph from protocol lock through evidence audit.

4. **Phase 2.5 — Model Gateway / Router Agent** ✅
   Deterministic router policy, pricing catalog, mock provider,
   fallback chains, budget hard-stop, AI usage log artifact.
   36 tests covering routing, gateway, pricing, and adversarial cases.

5. **Phase 3 — Methodology & statistics vertical slice** ✅
   Dataset dictionary validation, CSV importer, content-hash versioning,
   analysis-plan approval and dual lock (plan + dataset),
   deterministic mock statistics runner with full provenance,
   methodology critic via Model Gateway.
   32 new tests covering all 5 exit-gate invariants.

### Planned

6. **Phase 4 — Writing, review & revision** — Section drafting through the
   Model Gateway, claim/citation audit, bounded revision loop.

7. **Phase 5 — Compliance & export** — STROBE-Vet checklist, Quarto/Pandoc
   DOCX export, provenance bundle, AI usage log.

8. **Phase 6 — Production** — PostgreSQL, authentication, background jobs,
   object storage, observability, backup and deployment.

## Current quality gate status

| Gate | Status |
|---|---|
| ruff check | All checks passed |
| ruff format | 80+ files formatted |
| pytest | 242 tests passed |
| mypy | No issues in 57 source files |

## Architecture Decision Records

| ADR | Topic |
|---|---|
| [0001](docs/adr/0001-python-312-and-src-layout.md) | Python 3.12 and src layout |
| [0002](docs/adr/0002-structured-immutable-artifacts.md) | Structured immutable artifacts |
| [0003](docs/adr/0003-langgraph-state-boundary.md) | LangGraph state boundary |
| [0004](docs/adr/0004-human-approval-and-scope-locks.md) | Human approval and scope locks |
| [0005](docs/adr/0005-relational-literature-evidence-tables.md) | Relational literature/evidence tables |
| [0006](docs/adr/0006-methodology-and-statistics-architecture.md) | Methodology and statistics architecture 
| [0007](docs/adr/0007-model-gateway-and-router-agent.md) | Model Gateway and Router Agent |

## Golden project fixture

`fixtures/golden_project/` contains fully synthetic, redistributable test
data for end-to-end regression testing:

- `project.json` — project metadata and research question
- `data/cases_synthetic.csv` — 30-row synthetic canine/feline clinical dataset
- `dictionary/variables.json` — validated data dictionary (5 variables)
- `analysis_plan/analyses.json` — prespecified primary and secondary analyses
- `literature/records.json` — mock Zotero literature records
- `methodology/findings.json` — mock methodology critic findings

No real clinical data, credentials, or proprietary content is included.

## Development setup

Python 3.12 or later is required. On Windows, bootstrap the local environment
and run all quality gates with:

```powershell
& .\tools\bootstrap.ps1
```

After setup, rerun lint, formatting, type checks, and tests with:

```powershell
& .\tools\check.ps1
```

## Streamlit UI

The Streamlit UI runs the full pipeline from project initialization through
results approval. Start it with:

```powershell
& .\tools\run-streamlit.ps1
```

The startup script automatically clears `__pycache__` directories and kills any
stale Python processes before launching Streamlit. This avoids `sys.modules`
cache issues after editing `__init__.py` exports. Do **not** use `streamlit run`
directly — always launch through the script.

The local UI persists project/governance records in SQLite, immutable payloads
under `artifacts/`, and LangGraph checkpoints in a separate SQLite file.

## Quality gates

The test suite (242 tests across 21 files) includes schema and routing tests,
checkpoint resume tests, idempotency tests, approval-bypass attempts,
immutable-version tests, adversarial citation tests, claim-inflation tests,
statistical reproducibility, model-routing bypass tests, budget-downgrade
adversarial tests, evidence-pipeline integration tests, and golden-project
end-to-end regression tests.

## Safety statement

This software is research-writing assistance. Human investigators retain
responsibility for study design, data quality, statistical interpretation,
ethics, authorship, reporting compliance, and submission decisions.