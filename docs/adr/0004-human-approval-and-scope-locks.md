# ADR-0004: Human approval and scope locks

- Status: accepted
- Date: 2026-07-06

## Context

Prompts and UI warnings cannot prevent scope drift, approval bypass, or HARKing.

## Decision

Approval and lock rules are enforced by deterministic policy code. Approvals bind
to exact subject versions and hashes. Protocols, analysis plans, and datasets are
immutable after locking; change requires an amendment and a new version.

## Consequences

Agents cannot approve their own output. Downstream stages fail closed when an
approval is missing, stale, rejected, or bound to different content.

