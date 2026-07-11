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
     -> Report Entities -> Report Cards -> Report ViewModel
        -> deterministic report rendering
        -> Structured Evidence Interpretation
           -> brief provider call on /profile
           -> expanded provider call on Подробнее
     -> Pattern Payloads
```

LLM profile interpretation and map projection are currently separate. Profile
interpretation consumes the safe report artifact registry; deterministic map
payloads continue to consume `InsightPayload` without LLM map-focus hints.

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

Runtime Storage sits below active JSON owners. It provides atomic replacement,
serialized JSONL append, one bot-writer lease, per-chat Telegram ordering, and
bounded worker execution without changing artifact schemas.

Provider Operations sits before paid capture/profile calls. It provides
per-user/global admission, count-only usage state, bounded retry, and circuit
behavior without receiving ownership of capture or report contracts.

Telegram Capture emits UX/access events and chooses one explicit flow before
input handlers mutate runtime state. The four visible methods use typed
pre-draft state where needed. Classic 10Q uses `LoopSession`; completed
extractions use `DraftReviewSession`. They require `/cancel` before switching.

After Save, Analytics Refresh compares durable Episodes with the latest valid
annotation snapshot and coalesces deterministic missing-only production. On
startup the same comparison recovers pending work; no separate queue is stored.

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
  logic, complete annotation-run writing, and automatic refresh orchestration.
- Annotation Runs owns versioned selected derived annotations and readiness
  gates.
- Graph Reporting owns computed graph views, deterministic pattern metrics,
  and user-facing report rendering.
- Insight Payloads owns the shared deterministic analytics projection consumed
  by report and map surfaces.
- Pattern Payloads owns renderer-neutral map and spatial projections built from
  the shared insight payload plus report-ready graph entities.
- UX Analytics owns append-only loop event logs and aggregate UX views.
- Userlist / Access owns approved-user, waitlist, versioned consent, and
  identity-scoped export/deletion operation.
- Runtime Storage owns crash-safe local write and concurrency primitives; data
  contracts remain owned by their domain modules.
- Provider Operations owns paid-call admission, count-only token/call state,
  retry bounds, and circuit behavior across capture and profile surfaces.

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

Approval is not consent. Telegram Capture requires a private chat and a current
versioned adult consent record before accepting episode input. User Data Rights
can export one identity's artifacts or remove them; deletion also invalidates
shared derived snapshots that cannot be safely separated by user.

Provider usage state is private operational metadata, not analytics evidence. It
contains user IDs, calls, token totals, and circuit counters only and participates
in identity-scoped export/deletion.

## CBT Domain Boundary

Accepted CBT model knowledge lives in `model/`, especially:

- `model/cbt.md`
- `model/graph.md`
- `model/episode.schema.json`

Draft domain ideas can live locally under `docs/methodology/`, but they are not
part of the accepted model until promoted into `model/` through an explicit
change.
