# Architecture

This project is a personal CBT-oriented model workspace. The architecture is
organized around one rule:

```text
immutable inputs -> accepted contracts -> structured artifacts
```

`project.manifest.yaml` is the structural source of truth. This document is the
human map of how the pieces fit together.

## System Flow

```text
Telegram user
  -> Episode Capture
  -> Episode Model + Storage
  -> Annotation Workflow
  -> Graph Reporting
  -> Pattern Payloads
```

Supporting flows:

```text
Episode Capture -> UX Analytics
Episode Capture -> Userlist / Access Gate
```

## Layers

- `raw/`: immutable user materials and private inputs.
- `sources/`: immutable reference/source seeds.
- `model/`: accepted CBT domain model and JSON contracts.
- `app/`: runtime code and local CLIs.
- `config/`: runtime configuration.
- `data/`: private runtime artifacts, ignored by Git.
- `docs/`: architecture operating system and methodology drafts for humans.
- `roles/`: role prompts and task behavior specs.

## Bounded Contexts

- Episode Capture collects observed episode frames and writes validated episode
  drafts.
- Episode Model + Storage owns the JSON contract, Pydantic mirror, persistence,
  and legacy normalization.
- Annotation Workflow owns derived nodes, annotations, relations, and readiness
  gates.
- Graph Reporting owns graph readiness and core graph quality reports.
- Pattern Payloads owns renderer-neutral map payloads built from report-ready
  graph signatures.
- UX Analytics owns append-only loop event logs and aggregate UX views.
- Userlist / Access owns approved-user and waitlist metadata.

## Data Boundaries

Observed data is user-stated or minimally normalized episode evidence.

Derived data is interpretation over observed evidence. Every derived object must
include provenance through `source_field`, `source_quote`, and `confidence`.

Reports and payloads are downstream summaries. They must describe evidence and
gaps without making diagnostic claims.

## CBT Domain Boundary

Accepted CBT model knowledge lives in `model/`, especially:

- `model/cbt.md`
- `model/graph.md`
- `model/episode.schema.json`

Draft domain ideas can live locally under `docs/methodology/`, but they are not
part of the accepted model until promoted into `model/` through an explicit
change.
