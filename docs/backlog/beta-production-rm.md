# Beta Production RM Backlog

Status: active release-milestone backlog.

Milestone: `Beta-1 Stable Micro Build`.

This backlog is a planning surface for beta production readiness. It does not
change runtime contracts, episode schema, annotation-run schema, or payload
contracts by itself.

## Target Loop

```text
/10q /3b /1t /1a
-> schema-valid episode
-> annotation-run refresh
-> hydrated graph
-> basic map export
-> short report
-> long report
-> UX/admin stats
```

Primary success signal: a beta user can submit episodes through existing input
tools, the operator can refresh graph analytics from those episodes, and report
or map payload consumers can produce cautious, provenance-backed insight without
manual archaeology.

## RM-00 Roadmap Source Of Truth Alignment

Goal: make the beta release-management surface name one target and one ordered
backlog without implying runtime behavior that has not landed.

Acceptance:

- active RM docs use `Beta-1 Stable Micro Build`;
- DeepSeek provider work is separated into RM-01;
- current runtime truth is updated by the RM item that implements it;
- no application code, schema, or Telegram behavior changes.

## RM-01 Runtime Mode And DeepSeek Provider

Status: implemented.

Goal: introduce owner-switchable beta runtime modes.

Modes:

- `ml`: free/non-LLM local mode; `/10q` remains deterministic and non-10Q
  provider absence fails safely;
- `production`: DeepSeek API LLM mode for non-10Q capture extraction.

Acceptance:

- config can switch mode/provider by owner-controlled environment values;
- DeepSeek sits behind the existing capture extraction provider protocol;
- OpenAI remains compatibility through explicit provider selection;
- missing provider credentials/model fail through the existing typed sidecar
  path instead of crashing Telegram capture;
- no silent fallback to 10Q or Gap Hydration.

## RM-02 Operator Analytics Commands

Status: implemented.

Goal: reduce beta operator command friction for fresh analytics.

Acceptance:

- Makefile/operator commands cover annotation dry-run, missing-only refresh,
  full refresh, graph report, InsightPayload, map payload/HTML, and UX report;
- commands require explicit selected annotation-run where exports need one.

## RM-03 Capture Smoke To Beta Standard

Status: implemented.

Goal: harden the existing `/10q`, `/1t`, `/3b`, and `/1a` flows for beta use.

Acceptance:

- `docs/workflows/audio-input-smoke.md` is updated from alpha/OpenAI framing to
  beta production mode and DeepSeek provider policy;
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

Implementation note: RM-03 defines the beta smoke contract and evidence record.
It does not itself certify that a live Docker bot smoke has passed for a
particular release candidate; that remains a Beta Gate action.

## RM-04 Fresh Annotation Run

Status: implemented.

Goal: produce or verify current annotation-run coverage without modifying
observed episodes.

Acceptance:

- `make fresh-analytics-status` gives a read-only recommendation before
  writing;
- dry-run, selected annotation-run, coverage, readiness, and blocker state are
  visible as JSON;
- missing-only snapshot is recommended when a valid base run exists;
- full snapshot is recommended only when no valid base run exists;
- selected annotation-run and readiness summary are recordable without raw
  episode content.

## RM-05 Payload / Map / Short+Long Report QA

Status: implemented.

Goal: make beta analytics useful without growing the Telegram command surface.

Acceptance:

- InsightPayload, graph report, map payload, and map HTML export from the same
  selected annotation-run;
- `/profile` short summary and inline details act as short and long report;
- reports interpret payload/card facts rather than reselecting conflicting
  analytics;
- map/report/profile wording remains cautious and sample-bound;
- `make beta-report-qa` verifies selected-run consistency, export agreement,
  payload readiness, and report wording guards.

## RM-06 Brand Text Rewrite

Goal: separate product language rewrite from pipeline stabilization.

Acceptance:

- inventory covers Telegram messages, `/help`, short/long report copy,
  admin/operator copy, user announcements, and tutorial script;
- tone engine remains wording-only and does not alter CBT data;
- brand copy preserves observed-vs-derived boundaries, no-diagnosis language,
  sample-bound insight, and capture-to-report pipeline terms.

## RM-07 Tutorial Script

Goal: prepare beta onboarding after stable copy lands.

Acceptance:

- script covers `/10q`, `/3b`, `/1t`, `/1a`, Save/Cancel, short/long report,
  and report/map limits;
- tutorial remains release artifact, not runtime dependency.

## Supporting Epic: Input-To-Schema Transport Tool

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

## Supporting Epic: Episode-To-Graph Refresh Role

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

## Supporting Epic: Payload Entity Brush

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

## Supporting Epic: Report Interpreter Role Or Tool

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

## Supporting Epic: Beta Release Management

Goal: make beta operation repeatable.

Acceptance:

- one beta smoke workflow covers input, extraction, annotation refresh, payload
  export, report render, UX analytics, and rollback;
- Release Steward has a checklist for beta readiness and blockers;
- operator notes explain what changed, what is supported, and what is not;
- beta is not marked ready until Docker/live bot smoke and configured
  production DeepSeek extraction model pass;
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
- production mode uses configured DeepSeek provider/model for non-10Q
  extraction;
- fresh annotation-run is produced or a no-op full-coverage refresh is recorded;
- graph report, InsightPayload, basic map export, short report, and long report
  outputs are verified;
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
- graph report, InsightPayload, map payload, map HTML, `/profile` summary and
  details, and UX analytics checks.

Verify:

- no raw audio retention;
- no unintended episode/schema mutation;
- no report or payload claims beyond observed evidence and derived provenance.
