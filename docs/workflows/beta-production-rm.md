# Beta Production RM Workflow

Purpose: make `Beta-1 Fresh Analytics Loop` repeatable from capture smoke through
fresh analytics and report/payload verification.

This is an operator workflow, not a runtime module. It must not modify observed
episode JSON or private source artifacts except through the explicit capture
flows being smoked.

## Preconditions

- Working tree is clean or all unrelated changes are understood.
- Docker daemon is available to the operator.
- `TELEGRAM_BOT_TOKEN`, `M3_TELEGRAM_ADMIN_CHAT_IDS`, and
  `M3_TELEGRAM_OWNER_CHAT_ID` are configured.
- `OPENAI_API_KEY` and explicit `M3_CAPTURE_EXTRACTION_MODEL` are configured for
  non-10Q capture extraction.
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
- `/cancel`, `/status`, `/help`, and `/profile` during active work.

Record count-only before/after checks for:

- episodes;
- runtime sessions;
- runtime flows;
- intake transcripts;
- capture artifacts;
- capture extractions;
- retained raw audio files.

Failure rule: do not mark beta ready if live capture smoke fails.

## 3. Fresh Analytics

Use `roles/fresh-analytics.md`.

Run a dry-run first:

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --dry-run
```

If missing rows are reported and a valid base run exists:

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --only-missing \
  --annotation-run-dir data/annotation-runs/<base-run> \
  --write
```

If no valid base run exists, create a full run only after recording that choice:

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --write
```

Then audit:

```bash
python -m app.annotation_audit --episode-dir data/episodes
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
make export-graph-report
make export-insight-payload ANNOTATION_RUN_DIR=<selected-run>
make export-map-payload ANNOTATION_RUN_DIR=<selected-run>
make export-map-html
python -m app.ux_analytics
```

Verify:

- graph report reads hydrated annotation-run data;
- `InsightPayload` is the shared analytics source for report/map consumers;
- map payload does not reselect conflicting motifs, forks, domains, outcomes, or
  gaps;
- `/profile` wording remains cautious and sample-bound;
- UX analytics can show funnel-level and user-level dropoff without raw content.

Failure rule: report/payload contradiction is a beta blocker unless explicitly
documented as a known limitation.

## 5. Release Decision

Use `roles/release-steward.md`.

Ready only when:

- static gates pass;
- Docker/live bot smoke passes;
- extraction model/API are configured and verified;
- fresh annotation-run is produced or no-op full coverage is recorded;
- report and payload checks pass;
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
