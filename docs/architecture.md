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
  -> Annotation Producer
  -> Annotation Runs
  -> Graph Reporting
  -> Pattern Payloads
```

Supporting flows:

```text
Telegram Capture -> UX Analytics
Telegram Capture -> Userlist / Access Gate
Telegram Capture -> explicit userflow router
  -> classic 10Q -> Episode Model + Storage
  -> audio_one_take -> Input Funnels -> Intake Transcripts
  -> hidden draft tools -> Episode Drafts -> Gap Hydration
```

Telegram Capture emits UX/access events and chooses one explicit flow before
input handlers mutate runtime state. `/start` is the normal `classic_10q`
entrypoint; hidden `/voice` arms `audio_one_take`. The flows use separate
runtime state and require `/cancel` before switching.

```text
audio_one_take
  -> audio_intake_started
  -> temporary media
  -> transcription
  -> IntakeTranscript source artifact
  -> transcript preview
  -> audio_intake_completed
  -> idle
```

Audio intake never enters Episode Drafts. An `IntakeTranscript` is not an
episode and does not enter episode storage or graph/report analytics.

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

- Telegram Capture receives Telegram input, access checks, callbacks, and UX
  event emission, and owns explicit userflow routing for the current runtime.
- Input Funnels normalize Telegram text, voice, audio, and future capture
  surfaces into input artifacts. Consumers are selected by the explicit flow:
  hidden text tools may use Episode Drafts, while `audio_one_take` uses Intake
  Transcripts.
- Telegram Media is the temporary download/cleanup boundary for
  Telegram voice, audio, and audio-like documents before transcription.
- Intake Transcripts owns durable transcript source artifacts created by the
  explicitly armed audio one-take flow.
- Episode Drafts stage partial observed fields before confirmation and
  persistence.
- Gap Hydration selects the smallest useful next question for incomplete or
  weak episode drafts.
- Episode Model + Storage owns the JSON contract, Pydantic mirror, persistence,
  and legacy normalization.
- Annotation Producer owns deterministic `Episode.observed -> Derived` business
  logic and explicit annotation-run writing.
- Annotation Runs owns versioned selected derived annotations and readiness
  gates.
- Graph Reporting owns computed graph views, deterministic pattern metrics,
  and user-facing report composition.
- Pattern Payloads owns renderer-neutral map payloads built from report-ready
  graph signatures.
- UX Analytics owns append-only loop event logs and aggregate UX views.
- Userlist / Access owns approved-user and waitlist metadata.

## Data Boundaries

Observed data is user-stated or minimally normalized episode evidence.

Derived data is interpretation over observed evidence. Every derived object must
include provenance through `source_field`, `source_quote`, and `confidence`.

The project keeps these boundaries explicit:

```text
input != episode
transcript != episode
transcript != draft
draft != episode
episode != annotation
annotation != graph
graph != report
report != source of truth
```

Episodes are observed source artifacts. Annotation runs are versioned selected
interpretations of episodes. `GraphReport` is the current computed graph view
built from episodes plus selected annotations. Reports and payloads are
downstream exports. They must describe evidence and gaps without making
diagnostic claims.

Runtime profile and admin report paths compute projections on demand. Persistent
report files under `data/reports/` are optional debug/export snapshots, not an
active storage layer.

## CBT Domain Boundary

Accepted CBT model knowledge lives in `model/`, especially:

- `model/cbt.md`
- `model/graph.md`
- `model/episode.schema.json`

Draft domain ideas can live locally under `docs/methodology/`, but they are not
part of the accepted model until promoted into `model/` through an explicit
change.
