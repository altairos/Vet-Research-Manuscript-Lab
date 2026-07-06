# ADR-0002: Structured immutable artifacts

- Status: accepted
- Date: 2026-07-06

## Context

Scientific outputs must be auditable and reproducible across agents, approvals,
and revisions.

## Decision

JSON-compatible domain objects are canonical. Formal payloads are immutable,
versioned, SHA-256 hashed, and connected by provenance links. Markdown, CSV,
Quarto, and DOCX are projections or exports.

## Consequences

Approved content is never overwritten. Corrections create new versions and may
invalidate downstream approvals or locks.

