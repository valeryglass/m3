# Lifecycle

This document defines lifecycle words used by `project.manifest.yaml`.

## Stages

- `draft`: idea or local note; not an accepted project artifact.
- `prototype`: working shape exists, but boundaries or outputs may change.
- `experimental`: usable and tested enough for local operation, but still
  expected to evolve.
- `stable`: contract is expected to remain compatible unless an ADR changes it.
- `legacy`: still supported for compatibility, but no longer the preferred path.
- `archived`: retained only as historical reference.

## Transition Rules

- `draft -> prototype`: the purpose and owner are clear enough to create files.
- `prototype -> experimental`: there is a working path and focused tests or
  manual verification.
- `experimental -> stable`: interface, data shape, and failure modes are known.
- `stable -> legacy`: a replacement exists and compatibility behavior is clear.
- `legacy -> archived`: no runtime or compatibility path depends on it.

## ADR Rules

Create an ADR for changes that affect:

- JSON schemas or persisted data shape.
- module boundaries or ownership.
- interface contracts between bounded contexts.
- data flow from observed evidence to derived outputs.
- lifecycle policy or maturity gates.

An ADR is not required for small copy edits, local bug fixes inside an existing
module, or test-only changes that do not alter behavior.

## Release Flow

This is a personal project, so release flow is intentionally light:

```text
local change -> focused verification -> commit -> optional branch/PR workflow
```

Private runtime data under `data/` is not part of release scope.
