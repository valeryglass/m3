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
- Beta production `/profile` uses `M3_PROFILE_REPORT_MODE=auto`,
  `M3_PROFILE_LLM_PROVIDER=deepseek`, and explicit `M3_PROFILE_LLM_MODEL` for
  separate structured brief and expanded interpretation calls. Missing,
  insufficient, or failed interpretation must fall back independently for that
  report surface and write a process-journal event. LLM map focus is paused.
- `M3_CAPTURE_EXTRACTION_PROVIDER=openai` remains an explicit compatibility
  option, not the beta production default.
- Whisper/ffmpeg prerequisites are available for audio smoke.
- Test user is approved in `data/userlist/users.json`.
- Existing private runtime data is backed up or intentionally preserved in place.

## 1. Static Gates

```bash
git status --short --branch
git diff --check
.venv/bin/python -m py_compile app/*.py app/schemas/*.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_project_inventory.py tests/test_roles.py -q
command -v ffmpeg
command -v "${M3_WHISPER_COMMAND:-.venv/bin/whisper}"
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
python -m app.fresh_analytics_status --episode-dir data/episodes --annotation-run-root data/annotation-runs
```

The live bot should already have refreshed coverage after Save or startup. Use
this command to verify automatic behavior. Run the recommended producer command
only to repair a recorded blocker or to prepare explicit offline release
evidence.

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
python -m app.annotation_audit --episode-dir data/episodes --annotation-run-root data/annotation-runs --annotation-run-dir <selected-run>
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
python -m app.graph_report --episode-dir data/episodes --output-dir data/reports/graph --by-source --min-count 2 --annotation-run-dir <selected-run>
python -m app.insight_payload --episode-dir data/episodes --annotation-run-dir <selected-run> --source <source> --output data/exports/insight-payload/<source-safe>.json
python -m app.map_payload --episode-dir data/episodes --annotation-run-dir <selected-run> --source <source> --output data/exports/map-payload/<source-safe>.json
python -m app.map_payload_html --input data/exports/map-payload/<source-safe>.json --output data/exports/map-payload/<source-safe>.html
python -m app.ux_analytics --output-dir data/reports/ux
python -m app.report_payload_qa --episode-dir data/episodes --annotation-run-dir <selected-run> --source <source> --insight-payload-path data/exports/insight-payload/<source-safe>.json --map-payload-path data/exports/map-payload/<source-safe>.json
```

Verify:

- graph report reads hydrated annotation-run data;
- `InsightPayload` is the shared analytics source for report/map consumers;
- map payload JSON and HTML preview are operator exports, not Telegram user
  features;
- map payload does not reselect conflicting motifs, forks, domains, outcomes, or
  gaps;
- production `/profile` brief and expanded sections are independent cautious,
  artifact-backed interpretations over the same registry;
- inline details make a separate provider call on cache miss and reuse cached
  expanded text on repeated callbacks;
- a brief failure does not prevent expanded interpretation, and an expanded
  failure does not replace an already displayed brief;
- profile interpretation emits no map-focus hints and does not alter the
  deterministic map payload;
- UX analytics can show funnel-level and user-level dropoff without raw content.

`app.report_payload_qa` is the acceptance check for report/payload consistency.
It must pass with `status=passed` before beta can be marked ready.

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
