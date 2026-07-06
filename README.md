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
    `-- Quarto/Pandoc DOCX exporter
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
         -> review/revision (bounded) -> final compliance audit
         -> human sign-off -> export -> complete
```

Every interrupt checkpoint is serializable, so the workflow can resume from any
approval gate after a process restart.

## Repository blueprint

```text
src/vet_manuscript_lab/
  domain/
    conventions.py    # IDs, timestamps, hashes, ArtifactType enum
    policies/         # pure policy functions (foundation, evidence, analysis,
                      #   writing, compliance)
  workflow/
    state.py               # WorkflowState TypedDict + stage transitions
    foundation_graph.py    # PROJECT_INIT → PROTOCOL_LOCK
    literature_graph.py    # LITERATURE_SEARCH → EVIDENCE_AUDIT
    analysis_graph.py      # METHODOLOGY_CRITIC → RESULTS_APPROVAL
    writing_graph.py       # WRITING → REVIEW → REVISION
    compliance_graph.py    # FINAL_COMPLIANCE_AUDIT → EXPORT → COMPLETE
  services/
    zotero/           # Zotero API client + mapper + synchroniser
    retrieval/        # chunker + hybrid retriever (BM25 / LlamaIndex)
    documents/        # PDF parser + importer
    analysis/         # dictionary + importer + statistics runner
    writing/          # section writer + reviewer + reviser (Protocol + Mock)
    compliance/       # STROBE-Vet checklist + auditor (Protocol + Mock)
    export/           # export generator + DOCX renderer (Protocol + Mock)
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
  versions/           # Alembic migrations (0001–0005)
docs/
  adr/                # Architecture Decision Records (0001–0009)
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

5. **Phase 3 — Methodology & statistics vertical slice** ✅
   Dataset dictionary validation, CSV importer, content-hash versioning,
   analysis-plan approval and dual lock (plan + dataset),
   deterministic mock statistics runner with full provenance,
   methodology critic via Model Gateway.

6. **Phase 4 — Writing, review & revision** ✅
   Section drafting through the Model Gateway, claim/citation audit,
   bounded revision loop with human-dispositioned findings.
   7 policy functions, 5 graph nodes, Mock writer/reviewer/reviser.
   38 new tests covering all 5 exit-gate invariants.

7. **Phase 5 — Compliance & export** ✅
   STROBE-Vet 22-item checklist, final compliance audit, human sign-off
   with artifact hash binding, Quarto/Pandoc DOCX export, provenance
   bundle with manifest + AI usage log, hash-addressed export package.
   5 policy functions, 5 graph nodes, auto-detect DOCX renderer
   (Quarto → Pandoc → Mock fallback chain).
   55 new tests across policy, graph, and renderer.

### Planned

8. **Phase 6 — Production** — PostgreSQL, authentication, background jobs,
   object storage, observability, backup and deployment.

## DOCX export

The export pipeline assembles a Quarto markdown (`.qmd`) source from approved
manuscript sections and renders it to Word DOCX via the best available tool:

1. **Quarto CLI** (preferred) — `quarto render --to docx`
2. **pandoc** (fallback) — `pandoc --to docx`
3. **MockDocxRenderer** (offline) — deterministic placeholder

Auto-detection is handled by `create_docx_renderer()`, which probes for the
tools at runtime. When neither Quarto nor pandoc is installed, the pipeline
falls back to a mock renderer so tests and local development work without
external dependencies.

To install Quarto: see <https://quarto.org/>.
To install pandoc: see <https://pandoc.org/installing.html>.

A `reference-doc.docx` style template can be passed via `DocxRenderInput` for
consistent journal formatting.

## Current quality gate status

| Gate | Status |
|---|---|
| ruff check | All checks passed |
| ruff format | 105+ files formatted |
| pytest | 335 tests passed |
| mypy | No issues in source files |

## Architecture Decision Records

| ADR | Topic |
|---|---|
| [0001](docs/adr/0001-python-312-and-src-layout.md) | Python 3.12 and src layout |
| [0002](docs/adr/0002-structured-immutable-artifacts.md) | Structured immutable artifacts |
| [0003](docs/adr/0003-langgraph-state-boundary.md) | LangGraph state boundary |
| [0004](docs/adr/0004-human-approval-and-scope-locks.md) | Human approval and scope locks |
| [0005](docs/adr/0005-relational-literature-evidence-tables.md) | Relational literature/evidence tables |
| [0006](docs/adr/0006-methodology-and-statistics-architecture.md) | Methodology and statistics architecture |
| [0007](docs/adr/0007-model-gateway-and-router-agent.md) | Model Gateway and Router Agent |
| [0008](docs/adr/0008-writing-review-and-revision-architecture.md) | Writing, review, and revision architecture |
| [0009](docs/adr/0009-compliance-and-export-architecture.md) | Compliance, sign-off, and export architecture |

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

The test suite (335 tests across 24 files) includes schema and routing tests,
checkpoint resume tests, idempotency tests, approval-bypass attempts,
immutable-version tests, adversarial citation tests, claim-inflation tests,
statistical reproducibility, model-routing bypass tests, budget-downgrade
adversarial tests, evidence-pipeline integration tests, golden-project
end-to-end regression tests, writing/revision cycle tests, compliance audit
tests, sign-off fail-closed tests, DOCX renderer tests, and export package
integrity tests.

## Safety statement

This software is research-writing assistance. Human investigators retain
responsibility for study design, data quality, statistical interpretation,
ethics, authorship, reporting compliance, and submission decisions.
