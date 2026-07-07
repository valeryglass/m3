# Beta Production RM Workflow

Purpose: make `Beta-1 Stable Micro Build` repeatable from capture smoke through
fresh analytics and report/payload verification.

This is an operator workflow, not a runtime module. It must not modify observed
episode JSON or private source artifacts except through the explicit capture
flows being smoked.

## Preconditions

- Working tree is clean or all unrelated changes are understood.
- Docker daemon is available to the operator.
- `TELEGRAM_BOT_TOKEN`, `M3_TELEGRAM_ADMIN_CHAT_IDS`, and
  `M3_TELEGRAM_OWNER_CHAT_ID` are configured.
- Beta production smoke uses `M3_APP_MODE=production`,
  `M3_CAPTURE_EXTRACTION_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, and explicit
  `M3_CAPTURE_EXTRACTION_MODEL` for non-10Q capture extraction.
- `M3_CAPTURE_EXTRACTION_PROVIDER=openai` remains an explicit compatibility
  option, not the beta production default.
- Whisper/ffmpeg prerequisites are available for audio smoke.
- Test user is approved in `data/userlist/users.json`.
- Existing private runtime data is backed up or intentionally preserved in place.

## 1. Static Gates

```bash
git status --short --branch
git diff --check
make check
make test-docs
make release-audio-check
docker compose config --quiet
```

Failure rule: do not continue to beta smoke until these pass or the failure is
recorded as a beta blocker.

## 2. Live Capture Smoke

Start the runtime with Docker:

```bash
docker compose build bot
docker compose up -d bot
docker compose logs -f bot
```

Run `docs/workflows/audio-input-smoke.md` completely:

- idle containment;
- `/10q` classic capture through review Save/Cancel;
- `/1t` extraction success and extraction failure behavior;
- `/3b` restart-safe collection and extraction;
- `/1a` audio transcript Continue/Reject;
- unsupported media rejection;
- `/cancel`, `/status`, `/help`, and `/profile` during active work;
- `/profile` summary and inline details after analytics are ready.

Current RM-08/RM-09 note: capture artifacts are expected to exist even when
non-10Q extraction fails. Failed extraction should keep its failed
`CaptureExtraction` sidecar, write private `data/capture-debug/` evidence when
available, and continue into a missing-field gap session when safe partial
context exists. Record a blocker only when the bot dead-ends without review,
gap session, or explicit failure evidence.

Complete the smoke evidence record with count-only before/after checks for:

- episodes;
- runtime sessions;
- runtime flows;
- intake transcripts;
- capture artifacts;
- capture extractions;
- capture debug sidecars;
- retained raw audio files;
- UX events.

Record provider and model names, but never record API keys, raw user text,
transcripts, or episode content in the release evidence.

Failure rule: do not mark beta ready if live capture smoke fails.

## 3. Fresh Analytics

Use `roles/fresh-analytics.md`.

Start with the read-only status command:

```bash
make fresh-analytics-status
```

Follow the JSON recommendation:

- `no_op_empty`: record that there are no observed episodes and stop analytics
  refresh.
- `no_op_full_coverage`: record the selected annotation-run and continue.
- `missing_only`: run the `recommended_command`, then rerun status with the new
  run as `ANNOTATION_RUN_DIR`.
- `full_snapshot`: run the `recommended_command`, then rerun status with the new
  run as `ANNOTATION_RUN_DIR`.
- `blocked`: stop and record the blocker as beta evidence.

Then audit:

```bash
make audit ANNOTATION_RUN_DIR=<selected-run>
```

Record:

- selected annotation-run directory;
- observed episode count;
- annotation row count;
- readiness gap counts;
- whether any selected-source episode is not payload eligible.

## 4. Payload And Report Verification

Use `roles/report-interpreter.md` for report interpretation and QA.

For explicit exports, set `ANNOTATION_RUN_DIR` to the selected run.

```bash
make export-graph-report ANNOTATION_RUN_DIR=<selected-run>
make export-insight-payload ANNOTATION_RUN_DIR=<selected-run>
make export-map-payload ANNOTATION_RUN_DIR=<selected-run>
make export-map-html
make export-ux-report
make beta-report-qa ANNOTATION_RUN_DIR=<selected-run>
```

Verify:

- graph report reads hydrated annotation-run data;
- `InsightPayload` is the shared analytics source for report/map consumers;
- map payload JSON and HTML preview are operator exports, not Telegram user
  features;
- map payload does not reselect conflicting motifs, forks, domains, outcomes, or
  gaps;
- `/profile` short summary and inline long details remain cautious and
  sample-bound;
- UX analytics can show funnel-level and user-level dropoff without raw content.

`make beta-report-qa` is the acceptance check for report/payload consistency. It
must pass with `status=passed` before beta can be marked ready.

Failure rule: report/payload contradiction is a beta blocker unless explicitly
documented as a known limitation.

## 5. Release Decision

Use `roles/release-steward.md`.

Ready only when:

- static gates pass;
- Docker/live bot smoke passes;
- production DeepSeek model/API are configured and verified;
- fresh annotation-run is produced or no-op full coverage is recorded;
- map, report, payload, and UX checks pass;
- rollback path is recorded.

If blocked, write:

- blocker summary;
- failed command or smoke step;
- private-data-safe evidence;
- next unblock action.

## Rollback

Rollback is branch/image based:

```bash
git switch <previous-known-good-branch-or-tag>
docker compose build bot
docker compose up -d bot
```

Do not delete private episodes, runtime sessions, runtime flows, transcripts,
capture artifacts, capture extractions, annotation-runs, UX logs, reports, or
exports as a rollback shortcut.
