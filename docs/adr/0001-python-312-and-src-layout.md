# ADR-0001: Python 3.12 and src layout

- Status: accepted
- Date: 2026-07-06

## Context

The project needs modern typing support and a package structure that prevents
accidental imports from the repository root.

## Decision

Use Python 3.12 or later and package code under `src/vet_manuscript_lab`.
Use setuptools initially because it is available in the target environment and
does not impose a separate package-manager prerequisite.

## Consequences

Local commands set `PYTHONPATH=src` or install the package. Supporting Python
3.11 and earlier is outside the MVP scope.

