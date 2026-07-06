# ADR-0005: Relational literature and evidence tables

- Status: accepted
- Date: 2026-07-06

## Context

The Foundation layer (ADR-0002) stores all scientific outputs as generic,
content-addressed `Artifact` / `ArtifactVersion` rows whose payloads live in
the artifact store. This works well for documents (research questions,
protocols, analysis plans) that are written once, hashed, and referenced by ID.

Phase 2 introduces a different access pattern. Literature references must be
deduplicated by DOI/PMID, screened individually, linked to exact source
locations, and queried by concept, species, or certainty. Evidence items must
join back to their source spans and literature records. Treating these as JSON
blobs inside opaque artifact versions would make every deduplication check,
screening query, and provenance trace a full-payload scan.

domain_model.md §2 already defines a "Literature and evidence aggregate" with
`LiteratureRecord`, `AttachmentVersion`, `SourceSpan`, `EvidenceItem`, and
`ScreeningDecision` as first-class entities.

## Decision

Create dedicated relational tables (migration `0002_literature_evidence`) for
the literature and evidence aggregate:

| Table | Purpose |
|---|---|
| `literature_records` | Local bibliographic identity; DOI/PMID unique per project |
| `attachment_versions` | Immutable source-file versions keyed to a literature record |
| `source_spans` | Exact source location (page, section, offsets, quote hash) |
| `evidence_items` | Extracted evidence with concept, value, units, certainty, span links |
| `screening_decisions` | Inclusion/exclusion per record per stage |
| `provenance_links` | Typed directed derivation edges between versioned objects |

Large binary payloads (PDF bytes, full extracted text) remains in the
content-addressed artifact store; the relational tables store only identity,
metadata, and relationships.

Policy invariants are enforced by `domain/policies/evidence.py`:

- Every `EvidenceItem` requires at least one `SourceSpan`.
- Screening may proceed only after the search strategy is approved.
- Evidence extraction requires that every literature record has been screened.
- DOI and PMID are unique within a project.

## Consequences

Literature and evidence entities are queryable, indexable, and joinable without
deserialising artifact payloads. Deduplication is enforced at the database level
via unique constraints. Provenance chains from search strategy → literature
record → attachment → source span → evidence item are traversable through typed
edges rather than flat ID arrays.

The trade-off is schema rigidity: adding a new evidence field requires a
migration rather than a JSON key change. This is acceptable because the
literature/evidence domain is stable and well-specified, and queryability
outweighs schema flexibility for this aggregate.
