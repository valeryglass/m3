# Beta Production RM Backlog

Status: active release-milestone backlog.

Milestone: `Beta-1 Fresh Analytics Loop`.

This backlog is a planning surface for beta production readiness. It does not
change runtime contracts, episode schema, annotation-run schema, or payload
contracts by itself.

## Target Loop

```text
stable capture
-> schema transport
-> fresh annotation-run
-> payload
-> interpreted report
```

Primary success signal: a beta user can submit episodes through existing input
tools, the operator can refresh graph analytics from those episodes, and report
or map payload consumers can produce cautious, provenance-backed insight without
manual archaeology.

## EPIC-01 Sturdy Existing Input Flow

Goal: harden the existing `/10q`, `/1t`, `/3b`, and `/1a` flows for beta use.

Acceptance:

- live smoke passes for classic text, one-take text, three-block, and audio
  transcript confirmation;
- active-session conflicts, `/cancel`, `/status`, unsupported media, extraction
  failure, Save, and Cancel are predictable;
- UX analytics can show funnel-level and user-level dropoff without raw content;
- no new input mode is added.

Out of scope:

- automatic idle capture;
- long-form audio;
- field-editing review UI.

## EPIC-02 Input-To-Schema Transport Tool

Goal: make user input reliably become schema-valid episode drafts.

Acceptance:

- CaptureArtifact and CaptureExtraction sidecars are inspectable as private
  source/debug artifacts;
- non-10Q extraction has clear success and failure states;
- extraction failures never create episodes;
- successful output maps cleanly to `EpisodeDraft`;
- final Save persists only schema-valid observed episodes;
- `model/episode.schema.json` remains unchanged unless an explicit ADR promotes
  a schema change.

## EPIC-03 Episode-To-Graph Refresh Role

Goal: give Codex an operator role and workflow for fresh analytics.

Acceptance:

- role can run/check annotation production over current `data/episodes/`;
- role knows when to use `--only-missing`, when to produce a new annotation-run,
  and when to stop;
- workflow records selected annotation-run and coverage/readiness summary;
- analytics loaders, graph reports, payloads, and profile use the selected or
  latest valid run consistently;
- observed episode JSON is never modified by refresh work.

Primary artifacts:

- `roles/fresh-analytics.md`;
- `docs/workflows/beta-production-rm.md`.

## EPIC-04 Payload Entity Brush

Goal: clean the analytical entity ladder before report and map interpretation
grow.

Acceptance:

- registry distinguishes atom, pair, signature, set_signature, path_motif,
  set_motif, fork, contrast, counterexample, and attractor;
- payload wording does not imply causality from unordered co-presence;
- payloads keep provenance, support counts, coverage/gap state, and confidence
  visible;
- map/layout terms stay downstream and do not become domain truth;
- promotion path is explicit: report layer first, model/schema only through ADR.

Primary artifact:

- `docs/methodology/insight-entity-registry.md`.

## EPIC-05 Report Interpreter Role Or Tool

Goal: refactor report generation around interpreting payloads, not reselecting
analytics.

Acceptance:

- report interpreter consumes `InsightPayload` as its main input;
- report text is cautious, user-facing, and avoids diagnostic or stable-trait
  claims;
- report cards explain motifs, forks, contrasts, counterexamples, outcomes,
  coverage, and next observation questions;
- `/profile` and debug reports do not contradict map/payload analytics;
- interpreter role/workflow can be used by Codex for report QA.

Primary artifacts:

- `roles/report-interpreter.md`;
- `docs/modules/graph-reporting.md`;
- `docs/modules/insight-payloads.md`.

## EPIC-06 Beta Release Management

Goal: make beta operation repeatable.

Acceptance:

- one beta smoke workflow covers input, extraction, annotation refresh, payload
  export, report render, UX analytics, and rollback;
- Release Steward has a checklist for beta readiness and blockers;
- operator notes explain what changed, what is supported, and what is not;
- beta is not marked ready until Docker/live bot smoke and configured extraction
  model pass;
- rollback preserves private episodes, sessions, transcripts, annotation-runs,
  and exports.

Primary artifacts:

- `roles/release-steward.md`;
- `docs/workflows/beta-production-rm.md`;
- `docs/workflows/user-announcements.md`.

## Milestone Gates

### MVP Gate

- existing tests pass;
- local smoke passes;
- capture and extraction work with mocked providers.

### Beta Gate

- live Docker bot smoke passes;
- `OPENAI_API_KEY` and explicit `M3_CAPTURE_EXTRACTION_MODEL` are configured;
- fresh annotation-run is produced or a no-op full-coverage refresh is recorded;
- report and payload outputs are verified;
- user-level UX stats can be shown without raw content.

### Production-Ready Beta Gate

- repeatable operator workflow exists;
- rollout and rollback notes are written;
- no unresolved schema, interface, manifest, or role/workflow drift remains;
- beta blockers are recorded instead of hidden.

## Verification Checklist

```bash
make check
make test-docs
make release-audio-check
```

Then run:

- `docs/workflows/audio-input-smoke.md`;
- `docs/workflows/beta-production-rm.md`;
- annotation producer dry-run and missing-only workflow;
- graph report, insight payload, map payload, `/profile`, and UX analytics
  checks.

Verify:

- no raw audio retention;
- no unintended episode/schema mutation;
- no report or payload claims beyond observed evidence and derived provenance.
