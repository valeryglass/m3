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
  -> Insight Payloads
     -> User Report Rendering
     -> Pattern Payloads
```

Supporting flows:

```text
Telegram Capture -> UX Analytics
Telegram Capture -> Userlist / Access Gate
Telegram Capture -> explicit userflow router
  -> /start or /10q -> classic_10q
  -> /3b -> three_block
  -> /1t -> one_take_text
  -> /1a -> one_take_audio
  -> Capture Artifacts -> Capture Extraction -> Episode Drafts
  -> Draft Review -> Episode Model + Storage
```

Telegram Capture emits UX/access events and chooses one explicit flow before
input handlers mutate runtime state. The four visible methods use typed
pre-draft state where needed. Classic 10Q uses `LoopSession`; completed
extractions use `DraftReviewSession`. They require `/cancel` before switching.

```text
one_take_audio
  -> audio_intake_started
  -> temporary media
  -> transcription
  -> IntakeTranscript source artifact
  -> explicit transcript confirmation
  -> Capture Extraction
  -> schema-complete EpisodeDraft
  -> Save/Cancel review
  -> observed Episode
```

An `IntakeTranscript` remains source evidence, not an episode. It enters the
draft path only after explicit transcript confirmation and never enters
graph/report analytics directly.

## Layers

- `raw/`: immutable user materials and private inputs.
- `sources/`: immutable reference/source seeds.
- `model/`: accepted CBT domain model and JSON contracts.
- `app/`: runtime code and local CLIs.
- `data/`: private runtime artifacts, ignored by Git.
- `docs/`: architecture operating system and methodology drafts for humans.
- `roles/`: role prompts and task behavior specs.

## Bounded Contexts

- Telegram Capture receives Telegram input, access checks, callbacks, and UX
  event emission, and owns explicit userflow routing for the current runtime.
- Input Funnels normalize Telegram text, voice, audio, and future capture
  surfaces into input artifacts. Accepted text or transcript evidence may seed
  Episode Drafts through the explicit flow.
- Telegram Media is the temporary download/cleanup boundary for
  Telegram voice, audio, and audio-like documents before transcription.
- Intake Transcripts owns durable transcript source artifacts created by the
  explicitly armed audio one-take flow and their optional confirmed-episode
  backlink.
- Capture Artifacts own completed mode-specific evidence before extraction.
- Capture Extraction owns source-grounded projection into schema-complete
  Episode Drafts.
- Episode Drafts stage provisional observed fields before confirmation and
  persistence.
- Draft Review Sessions own complete provisional observed fields while the user
  chooses Save or Cancel.
- Gap Hydration is an experimental next-question module. Production non-10Q
  capture does not use it.
- Episode Model + Storage owns the JSON contract, Pydantic mirror, persistence,
  and legacy normalization.
- Annotation Producer owns deterministic `Episode.observed -> Derived` business
  logic and explicit annotation-run writing.
- Annotation Runs owns versioned selected derived annotations and readiness
  gates.
- Graph Reporting owns computed graph views, deterministic pattern metrics,
  and user-facing report rendering.
- Insight Payloads owns the shared deterministic analytics projection consumed
  by report and map surfaces.
- Pattern Payloads owns renderer-neutral map and spatial projections built from
  the shared insight payload plus report-ready graph entities.
- UX Analytics owns append-only loop event logs and aggregate UX views.
- Userlist / Access owns approved-user and waitlist metadata.

## Data Boundaries

Observed data is user-stated or minimally normalized episode evidence.

Derived data is interpretation over observed evidence. Every derived object must
include provenance through `source_field`, `source_quote`, and `confidence`.
Life-domain annotations are derived classifications over situation evidence;
they are produced in annotation snapshots before report or payload analytics.

The project keeps these boundaries explicit:

```text
input != episode
transcript != episode
transcript != draft until explicit user acceptance
capture artifact != draft
capture extraction != episode
draft != episode
episode != annotation
annotation != graph
graph != insight payload
insight payload != report
insight payload != spatial layout
report != source of truth
```

Episodes are observed source artifacts. Annotation runs are versioned selected
interpretations of episodes. `GraphReport` is the current computed graph view
built from episodes plus selected annotations. `InsightPayload` is the shared
deterministic analytics projection used by report rendering and Pattern
Payloads. Reports, map payloads, and spatial payloads are downstream projections
or exports. They must describe evidence and gaps without making diagnostic
claims.

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
