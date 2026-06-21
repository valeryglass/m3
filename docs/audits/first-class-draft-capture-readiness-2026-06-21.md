# Capture Schema Extraction Readiness Audit — 2026-06-21

## Decision

`blocked`

The schema-extraction refactor and automated gates pass. Live release
verification is blocked because this host has no configured capture extraction
credentials/model and Docker daemon access was not approved.

## Audited Revision

- branch: `mvp2/userflow-containment`
- pre-refactor rollback ref: `cffdcc3`
- implementation range: `cffdcc3..HEAD`
- commits:
  - `eb2af0a docs(architecture): accept capture schema extraction`
  - `8abacd4 feat(capture): add grounded extraction contracts`
  - `ad33fd1 refactor(capture): separate draft review state`
  - `92736d2 feat(telegram): extract captures directly to review`
  - `docs(release): document capture extraction readiness` (this audit/docs
    boundary)

## Automated Evidence

Passed:

- `git diff --check`
- `make check`
  - full suite: `497 passed`
- `make test-docs`
  - documentation checks: `10 passed`
- `make release-audio-check`
  - full suite: `497 passed`
  - documentation checks: `10 passed`
  - ffmpeg available
  - `.venv/bin/whisper` available
- `docker compose config --quiet`

Automated coverage includes:

- exact capture-piece retention and SHA-256 hashing;
- mode role/cardinality validation and prohibited media references;
- deterministic 10Q projection;
- strict OpenAI Responses request shape with explicit model selection;
- refusal, incomplete, content-filtered, missing, malformed, timeout, API, and
  unavailable-provider failures;
- exact source-quote grounding and 3B evidence-group enforcement;
- persisted successful and failed extraction sidecars;
- separate `DraftReviewSession` storage and legacy completed `LoopSession`
  migration;
- direct review for 3B, 1T, and confirmed audio transcript evidence;
- no `gap_question_asked` event for non-10Q extraction;
- no review or episode after extraction failure;
- classic 10Q direct projection into the shared review boundary;
- shared Save/Cancel behavior, transcript backlink, extraction backlink, and
  explicit observed-field persistence;
- `/status` review precedence and active-work containment;
- no capture text in UX events or lifecycle logs.

Tests use mocked providers and never call the live OpenAI API.

## Runtime Baseline

Only artifact counts and configuration presence were inspected. No episode,
transcript, capture, extraction, or payload text was printed.

| Runtime surface | Baseline |
|---|---:|
| episodes | 113 files |
| runtime sessions | 1 file |
| runtime flows | 0 files |
| intake transcripts | 6 files |
| capture artifacts | 0 files |
| capture extractions | 0 files |
| retained runtime audio | 0 files |

Configuration presence:

- Telegram token: configured
- `OPENAI_API_KEY`: not configured
- `M3_CAPTURE_EXTRACTION_MODEL`: not configured

## Required Live Smoke

Not completed:

- container build and bot startup;
- `/start` and `/10q` direct projection, review, Save, and Cancel;
- `/1t` and legacy `/capture` extraction success/failure;
- `/3b` and legacy `/capture3` restart-safe collection and extraction;
- `/1a`, hidden `/1v`, and legacy `/voice`;
- supported voice/audio/document transcription and unsupported media;
- transcript Continue extraction, Reject retention, and final backlinks;
- provider refusal/error behavior against the configured production model;
- active-flow/review conflicts, `/cancel`, `/status`, `/help`, and `/profile`;
- before/after private artifact count comparison and raw-audio absence.

## Blockers

1. Live non-10Q extraction cannot run without `OPENAI_API_KEY` and an explicit
   `M3_CAPTURE_EXTRACTION_MODEL`. The runtime intentionally has no model
   default or fallback provider.
2. `docker compose build bot` could not access `/var/run/docker.sock`.
   Escalated Docker access was requested and declined, so image build/start
   was not attempted outside the sandbox.

No automated code, schema, grounding, or documentation blocker was found.

## Compatibility And Rollback

- episode schema migration required: no
- existing active classic `LoopSession` files: compatible
- legacy completed `LoopSession` review files: migrated to
  `DraftReviewSession` on load
- existing capture/audio flow files: compatible
- existing `IntakeTranscript` files: compatible
- private data migration required: no
- raw-audio retention introduced: no
- rollback ref: `cffdcc3`

Operator rollback:

```bash
git switch --detach cffdcc3
docker compose build bot
docker compose up -d bot
```

Do not delete private episodes, transcripts, sessions, capture artifacts,
extractions, annotation runs, or exports during rollback.
