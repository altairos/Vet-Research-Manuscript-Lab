# ADR-0003: LangGraph state boundary

- Status: accepted
- Date: 2026-07-06

## Context

Checkpoint state can become fragile and expensive if it contains full documents,
dataframes, PDFs, or binary exports.

## Decision

LangGraph state contains only identifiers, compact decisions, status, warnings,
and immutable artifact references. Large or canonical content lives in domain
storage. State must pass strict JSON serialization with non-finite numbers
rejected.

## Consequences

Nodes load payloads through services and return partial reference updates.
Checkpoint persistence is not a document or vector store.

