# 0001: Architecture Operating System

## Decision

Use `project.manifest.yaml` as the structured source of truth for project
structure. Use Markdown docs under `docs/` as human views over that structure.

## Why

The project has grown beyond a single bot and schema. It now has capture,
storage, annotation, readiness, graph reports, psy payloads, UX analytics, and
access control. A manifest-first structure keeps ownership and interfaces
visible without turning runtime code into architecture documentation.

## Consequences

Positive:

- clearer module boundaries
- explicit interface inventory
- easier onboarding for future agent work
- one place to check lifecycle stage and ownership

Negative:

- docs can drift until a checker exists
- v1 requires manual updates after structural changes

## Policy

ADRs are required for schema, boundary, interface, data-flow, lifecycle, or
major module ownership changes.

ADRs are not required for small copy edits, local bug fixes inside an existing
module, or test-only changes that do not alter behavior.
