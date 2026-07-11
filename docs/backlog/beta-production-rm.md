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

Goal: keep fresh analytics available through direct CLIs while keeping Makefile
limited to local admin bot/test commands.

Acceptance:

- direct CLI tools cover annotation dry-run, missing-only refresh, full refresh,
  graph report, InsightPayload, map payload/HTML, and UX report;
- Makefile is limited to virtualenv setup, local bot lifecycle, and Docker bot
  lifecycle;
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

- `app.fresh_analytics_status` gives a read-only recommendation before writing;
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
- `app.report_payload_qa` verifies selected-run consistency, export agreement,
  payload readiness, and report wording guards.

## RM-06 Brand Text Rewrite

Goal: separate product language rewrite from pipeline stabilization.

Acceptance:

- inventory covers Telegram messages, `/help`, short/long report copy,
  admin/operator copy, operator release notes, and tutorial script;
- tone engine remains wording-only and does not alter CBT data;
- brand copy preserves observed-vs-derived boundaries, no-diagnosis language,
  sample-bound insight, and capture-to-report pipeline terms.

## RM-07 Tutorial Script

Goal: prepare beta onboarding after stable copy lands.

Acceptance:

- script covers `/10q`, `/3b`, `/1t`, `/1a`, Save/Cancel, short/long report,
  and report/map limits;
- tutorial remains release artifact, not runtime dependency.

## RM-08 Capture Extraction Debug Visibility

Status: implemented.

Goal: make failed `/1t`, `/3b`, and `/1a` extraction attempts diagnosable
without creating drafts or episodes from invalid output.

Acceptance:

- private debug sidecars under `data/capture-debug/` show provider response
  presence, response length, JSON parse state, top-level keys, validation error
  paths, parsed field names, missing required fields, and grounding failure
  codes;
- raw provider output is owner-toggle only and remains private ignored debug
  material;
- process journal events include only safe debug summaries;
- existing `CaptureExtraction` success/failure sidecars and no-episode failure
  behavior remain unchanged.

## RM-09 Partial Draft Fallback For Non-10Q Capture

Status: implemented.

Goal: remove the beta product mismatch where `/1t` and `/3b` save source
material but extraction failure blocks draft review before missing-field
questions.

Acceptance:

- grounded parseable fields from `/1t`, `/3b`, and `/1a` can start a partial
  draft/gap session;
- provider failure or partial output can continue into missing-field questions
  using the original capture artifact as safe fallback context;
- final Save remains blocked until the observed episode is schema-valid;
- failed extraction sidecars remain failed and preserve provider/model/prompt
  provenance for diagnosis;
- no raw provider output, raw transcript text, or unsupported inference enters
  episode JSON.

## RM-A5 Production LLM Profile Interpreter

Status: implemented.

Goal: allow beta production `/profile` to use an LLM wording layer while keeping
`ml` mode deterministic.

Acceptance:

- `M3_PROFILE_REPORT_MODE=auto` resolves to deterministic profile rendering in
  `ml` mode and LLM profile rendering in `production`;
- `M3_PROFILE_LLM_PROVIDER=deepseek` and explicit `M3_PROFILE_LLM_MODEL` select
  the production profile provider;
- LLM input uses safe analytics facts only: `InsightPayload`, Report Entities,
  report cards, coverage, support counts, gaps, and provenance identifiers;
- raw episode text, transcripts, source quotes, prompts, API keys, and raw LLM
  output are not journaled or sent through report QA output;
- missing provider config, provider failure, invalid JSON, or unsafe wording
  falls back to deterministic profile text and writes a process-journal event.

Known gap:

- the first LLM interpreter can still produce schema-like summaries. It proves
  the provider path, not final report UX quality.

## RM-A6 Report ViewModel Contract

Status: implemented.

Goal: create a render-ready report object between ReportCards and text output.

Acceptance:

- `ReportViewModel` exposes `summary_sections` and `details_sections`;
- each section carries title, plain claim, evidence lines, support/coverage
  facts, limits, and next observation question when present;
- deterministic `/profile` renders from `ReportViewModel`, not directly from
  raw cards;
- the ViewModel uses user-facing labels and avoids internal labels such as
  `approach`, `neutral_mixed`, `trigger`, `annotation`, and schema terms;
- existing deterministic profile facts remain sample-bound and provenance-backed.

## RM-A7 LLM As Copy Editor, Not Analyst

Status: implemented; production rendering superseded by RM-A9.

Goal: make production LLM profile rendering polish prepared report sections
instead of summarizing raw payload facts.

Acceptance:

- LLM input is `ReportViewModel` plus strict style rules, not a freeform
  `InsightPayload` dump;
- LLM output preserves section count, section order, support counts, evidence
  facts, limits, and questions;
- LLM output cannot add findings, remove coverage limits, or invent advice;
- any fact drift, missing section, missing support count, or missing question
  falls back to deterministic profile text;
- prompt/version names are bumped so old output can be distinguished in journal
  and tests.

## RM-A8 Report Quality Gate

Status: implemented.

Goal: block unsafe, ungrounded, or internally named LLM profile output before
it reaches Telegram without treating ordinary analytical vocabulary as a
runtime failure.

Acceptance:

- hard guard rejects explicit diagnostic, stable-trait, advisory, and internal
  wording such as `проаннотированы`;
- user-facing terms such as `триггер`, `подход`, `компенсация`, `исход`, and
  `в рамках сценария` are style preferences, not fallback conditions;
- causal connective phrases are not rejected by keyword alone; causal restraint
  remains in the provider prompt while artifact references, numeric facts, and
  composition are validated structurally;
- guard requires readable section structure, sample limitation, support facts,
  and next observation questions where the ViewModel has them;
- rejected LLM output falls back to deterministic profile text and journals a
  safe failure reason such as `unsafe_or_low_quality`;
- `app.report_payload_qa` covers deterministic report text and fake LLM outputs
  without printing raw private content.

## RM-A9 Structured Evidence Interpretation

Status: implemented; provider-call composition superseded by RM-A10.

Goal: let production LLM rendering select and combine prepared report artifacts
into one structured interpretation bundle without becoming a free essay.

Acceptance:

- production input is a deduplicated registry built from `InsightPayload`,
  Report Entities, and Report Cards without raw text, source quotes,
  transcripts, or episode IDs;
- one provider response contains a two-to-five-sentence brief, two to five
  structured expanded sections, one optional grounded question, limitations,
  and one to three basic map-focus hints;
- every generated block names valid supporting artifact IDs and numeric facts
  remain grounded in those specifically referenced artifacts;
- at least one section combines multiple analytical artifacts and later
  sections introduce new material instead of reproducing cards;
- map focus uses only compatible Region, Path, Boundary, Anchor, and Field roles
  and never changes MapPayload or layout;
- `/profile` caches expanded text and map focus in `context.chat_data`; the
  details callback performs no second provider call;
- `ml`, cache miss, insufficient material, provider failure, or unsafe output
  uses the complete deterministic fallback;
- journals retain only safe provider, status, and count metadata.

## RM-A10 Split Brief / Expanded Profile Interpretation

Status: implemented.

Goal: align provider calls with the two Telegram report actions and remove
all-or-nothing coupling between brief, expanded, and map presentation.

Acceptance:

- `/profile` makes one brief-only provider call;
- `profile:details` makes one expanded-only provider call when expanded text is
  not already cached;
- repeated details callbacks reuse cached expanded text;
- brief and expanded failures use independent deterministic fallbacks and
  surface-specific journal events;
- expanded may receive validated brief artifact IDs as priority hints, but not
  generated brief prose;
- both calls use the configured DeepSeek profile model with thinking disabled;
- LLM map-focus output is removed from report prompts, validation, and Telegram
  cache while deterministic map payload/export architecture remains available.

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
.venv/bin/python -m py_compile app/*.py app/schemas/*.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_project_inventory.py tests/test_roles.py -q
command -v ffmpeg
command -v "${M3_WHISPER_COMMAND:-.venv/bin/whisper}"
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
