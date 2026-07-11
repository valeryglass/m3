# Beta Production RM Backlog

Status: active release-milestone backlog.

Milestone: `Beta-1 Stable Micro Build`.

Next milestone: `Beta-2 Public Readiness` (planned).

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

## RM-10 Canonical Telegram Command Surface

Status: implemented.

Goal: retire hidden compatibility commands and their command-specific code so
the Telegram runtime has one supported route for each beta capture strategy.

Canonical command surface:

```text
/start /10q /3b /1t /1a /status /profile /cancel /help
```

Implementation scope:

- accept ADR 0017 before removing compatibility behavior recorded by ADRs 0009
  and 0013;
- unregister `/1v`, `/voice`, `/capture`, and `/capture3`;
- remove the direct inline `/capture` and pipe-separated `/capture3` handlers,
  parsers, and route-specific tests;
- remove the runtime-unused `app/audio_flow_store.py` compatibility facade and
  migrate remaining tests to `CaptureFlowStore`;
- remove old `audio-one-take` state-format/path compatibility only after the
  operator confirms that no private runtime-flow files require migration;
- add one generic unknown-command response that directs users to `/help`;
- update active command, smoke, module, roadmap, manifest, and rollback docs
  while preserving historical audits as history.

Acceptance:

- only canonical user commands and explicit admin/operator commands are
  registered;
- `/1t`, `/3b`, and `/1a` retain the shared `CaptureFlowStore ->
  CaptureArtifact -> CaptureExtraction -> review/gap` pipeline;
- removing the `/voice` command does not remove Telegram voice-note, audio-file,
  document-media, transcription, or `one_take_audio` handling;
- unknown commands fail visibly without starting or replacing a flow;
- no episode, capture, transcript, annotation, report, or payload schema changes;
- private runtime artifacts are migrated or preserved before compatibility
  readers are removed.

Planning evidence:

- `/capture`, `/capture3`, and `/1v` have no recorded command invocations in the
  current private UX log;
- `/voice` has historical invocations but is fully superseded by `/1a`;
- the current checkout has no private files under the legacy
  `data/runtime-flows/audio-one-take/` path.

## RM-11 Command Usage UX Analytics

Status: implemented.

Goal: expose per-command usage from the safe command metadata already stored in
private UX events.

Current finding:

- `update_received` records the first command token in `command`;
- the current report aggregates only `updates_by_message_kind`, so command
  counts require manual inspection;
- Telegram does not distinguish selecting a command-menu item from typing the
  same command manually.

Implementation scope:

- normalize command names for aggregation without retaining arguments or
  message text;
- add `commands_received_by_name`, `authorized_commands_by_name`, and
  `unauthorized_commands_by_name` to JSON and Markdown UX reports;
- add private owner-facing `commands_by_user` using existing user labels;
- keep historical legacy-command names visible rather than rewriting old
  events;
- document that command invocation is measurable but menu-click attribution is
  not;
- leave inline callback analytics such as `profile:details` for a separate
  backlog item.

Acceptance:

- existing UX JSONL files can be aggregated without migration;
- command arguments, Telegram message text, episode content, transcripts, and
  report text never enter aggregates;
- totals reconcile with command-shaped `update_received` events and matching
  unauthorized attempts;
- `/report_ux` and `app.ux_analytics` expose the same command counts;
- tests cover normalization, authorized/unauthorized separation, historical
  unknown commands, and per-user counts.

Implemented result:

- JSON, Markdown, and hidden `/report_ux` use the same aggregation path;
- command tokens are lowercased and stripped of bot-name suffixes and
  arguments before counting;
- historical retired and unknown command names remain visible;
- `commands_by_user` contains authorized invocations only, while unauthorized
  attempts remain separately aggregated.

## Beta-2 Public Readiness Boundary

Status: planned after the Beta-1 gate.

Default access model: publicly discoverable, approval-gated beta for adults.
Anonymous open access is out of scope while M3 stores sensitive personal episode
material and depends on paid external providers.

Beta-2 does not change the CBT model, episode schema, annotation schema, or
InsightPayload contract. It hardens consent, storage, provider operations,
analytics freshness, and release operations around the existing product loop.

Prerequisites:

- Beta-1 release evidence is complete;
- RM-06, RM-07, RM-10, and RM-11 are implemented;
- the operator has selected a retention policy and public-beta support contact;
- unresolved private-data or provider-cost blockers stop the milestone.

## RM-12 Public Consent And Data Rights

Status: implemented technically; public-beta gate remains blocked on reviewed
legal copy and owner-selected retention policy.

Goal: make sensitive-data collection explicit and give the operator a complete,
verifiable per-user data lifecycle.

Implementation direction:

- accept a data-lifecycle ADR before adding persisted consent or deletion
  contracts;
- replace alpha-only terms with reviewed public-beta terms and privacy notice;
- require private Telegram chats, adult confirmation, and explicit acceptance
  of a versioned notice before capture starts;
- add owner tools for private per-user inventory, export, deletion preview,
  confirmed deletion, and post-delete verification;
- cover episodes, sessions, flows, reviews, transcripts, capture artifacts,
  extraction/debug sidecars, UX events, userlist records, annotation-derived
  references, reports, and exports;
- define retention and backup-deletion behavior without promising deletion the
  runtime cannot prove.

Acceptance:

- consent state is versioned, inspectable, and contains no submitted content;
- users cannot capture data before consent and private-chat checks pass;
- export and deletion operate by Telegram identity without cross-user leakage;
- deletion dry-run and verification report safe counts and paths only;
- legal copy is reviewed separately from implementation correctness.

Implemented result:

- approved users must accept the current versioned adult notice in a private
  chat before capture/profile access;
- consent stores version/status/timestamp only and resets when the configured
  version changes;
- owner CLI supports safe inventory, identity-scoped ZIP export, deletion
  preview, exact-confirmation deletion, and post-delete verification;
- deletion preserves other users' source files while clearing affected
  annotation runs and unattributable shared reports/exports/local backups;
- export and deletion refuse to race an active bot writer.

Remaining PO gate:

- review final public-beta legal wording and support contact;
- set `M3_DATA_RETENTION_DAYS` or explicitly approve no automatic expiry;
- inventory and clear any external copies outside configured runtime paths.

## RM-13 Atomic Storage And Runtime Concurrency

Status: implemented; live Docker-volume verification remains in RM-16.

Goal: keep the JSON runtime small while making the single-instance beta
crash-safe and responsive under concurrent user activity.

Implementation direction:

- retain the JSON artifact architecture for Beta-2 rather than introducing a
  database migration;
- add a shared atomic JSON writer using temporary files plus `os.replace`;
- serialize episode ID allocation/write and mutable per-chat/user state with
  bounded file or process locks;
- serialize append-only UX/journal writes so concurrent workers cannot
  interleave or lose events;
- enforce one active bot writer for the data root and fail startup clearly on a
  second instance;
- move synchronous profile provider calls off the Telegram event loop through a
  bounded worker boundary;
- add a global Telegram error handler with safe journal metadata;
- add crash, collision, concurrent-chat, and interrupted-write tests.

Acceptance:

- interrupted writes do not leave partial JSON as active state;
- concurrent saves cannot select the same episode ID;
- one slow profile or extraction call does not block unrelated Telegram updates;
- multi-instance writes are rejected rather than silently racing;
- existing private artifacts remain readable without schema migration.

Implemented result:

- active runtime JSON stores use atomic same-directory replacement;
- episode allocation and persistence share a cross-process lock;
- UX and process journal JSONL writes are serialized;
- one process lock rejects a second bot writer for the runtime root;
- Telegram runs different chats concurrently while preserving per-chat order;
- extraction, transcription, and profile calls use a bounded worker pool;
- unhandled update errors journal IDs and exception type without error text.

## RM-14 Provider Quotas And Cost Guardrails

Status: implemented; live limit tuning and provider-health evidence remain in
RM-16.

Goal: prevent public-beta misuse or provider failure from creating unbounded
cost, latency, or queue pressure.

Implementation direction:

- add owner-configured per-user capture/profile daily limits;
- add a global in-flight provider-call semaphore and queue timeout;
- record safe provider usage counts and token usage when returned by the API;
- add a daily global budget stop, temporary circuit breaker, and bounded
  retry/backoff policy for retryable failures;
- return a user-facing unavailable/limit message without exposing provider
  internals;
- keep deterministic `/10q` and deterministic report fallback available where
  their existing contracts permit it.

Acceptance:

- limits apply before provider calls and survive normal process restart;
- one user cannot consume the global provider capacity;
- provider timeout, rate limit, circuit-open, and budget-exhausted states are
  distinguishable in safe journal/UX metadata;
- API keys, prompts, provider output, and episode text never enter usage logs.

Implemented result:

- capture and profile share persistent UTC-day call/token accounting, a global
  in-flight bound, and one active provider slot per user;
- owner-configured per-surface quotas, global token budget, queue timeout,
  bounded retry/backoff, and circuit cooldown apply before paid work;
- provider-returned token counts are recorded without prompts or content;
- corrupt/unavailable usage state fails closed before a paid call, while a
  telemetry write failure after a response cannot trigger duplicate spend;
- blocked profile calls use deterministic reporting and blocked non-10Q capture
  keeps the existing private sidecar and schema-safe partial-gap behavior;
- identity-scoped usage records participate in export and deletion.

## RM-15 Automatic Analytics Freshness

Status: implemented; live restart/container-volume evidence remains in RM-16.

Goal: ensure `/profile` has an explicit, repeatable relationship to episodes
saved after the currently selected annotation-run.

Implementation direction:

- enqueue deterministic missing-only annotation refresh after successful Save;
- recover pending refresh work by comparing episodes with the latest valid run
  on startup;
- publish a new complete annotation snapshot atomically and never mutate
  observed episodes;
- expose selected run, pending count, and freshness state to profile/admin
  checks without backend jargon in user copy;
- while stale, either block `/profile` with an updating state or show the last
  valid report with an explicit coverage limit; never imply fresh coverage;
- journal queue, refresh, publish, and blocker states using IDs and counts only.

Acceptance:

- every saved episode becomes represented in a complete selected run without a
  manual CLI archaeology step;
- restart cannot lose discoverable pending work;
- simultaneous saves coalesce safely into complete snapshots;
- `/profile`, payload, map, and debug reports select the same valid run;
- refresh failure preserves the last valid run and exposes a clear blocker.

Implemented result:

- durable Episodes act as the recovery queue, so startup discovers any coverage
  gap without a second persisted queue;
- successful Save enqueues one coalescing background worker and does not wait for
  deterministic annotation production;
- the worker writes a full first snapshot or a complete missing-only replacement
  and loops when another Save arrives during production;
- latest valid selection uses manifest creation time, while an explicit stale
  `M3_ANNOTATION_RUN_DIR` blocks automatic movement instead of being ignored;
- `/profile` fixes one selected run per render, preserves the partial-coverage
  note, and uses neutral processing copy before a first report is ready;
- admin graph output names selected run, freshness, and pending count;
- failed refresh preserves the prior valid run and journals safe blocker metadata.

## RM-16 Public Beta Operations Gate

Status: planned.

Goal: turn the hardened runtime into an operable public-beta release candidate.

Implementation direction:

- run the container as non-root with restart policy, health/readiness signal,
  bounded resources, and bounded Docker logs;
- enforce private data-volume permissions and document encryption-at-rest
  requirements for the runtime host;
- pin and inventory the release image and external runtime prerequisites;
- document and test encrypted backup, restore, rollback, and deletion handling;
- add one-instance startup checks, disk-space checks, provider health evidence,
  and operator alerts for critical journal events;
- run live Telegram, DeepSeek capture/profile, audio, consent, quota, freshness,
  export, deletion, backup, restore, and rollback smoke;
- run a curated brief/expanded report regression set plus manual safety sampling
  before approving the release candidate;
- publish support boundaries, known limitations, and incident ownership.

Public Beta Gate:

- RM-12 through RM-16 are implemented and verified;
- brand copy, tutorial, canonical command surface, and command UX stats are
  complete;
- no unhandled private-chat, consent, deletion, concurrent-write, provider-cost,
  stale-analytics, report-safety, data-volume, or restore blocker remains;
- the release candidate has count-only evidence for live smoke and rollback;
- public beta remains approval-gated until a later ADR explicitly accepts open
  access.

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
