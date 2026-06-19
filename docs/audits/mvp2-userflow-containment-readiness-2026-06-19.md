# MVP2 Userflow Containment Readiness Audit — 2026-06-19

## Decision

`blocked`

The post-patch branch passes all automated release gates. Release readiness is
blocked because the required Docker startup and live Telegram operator smoke
could not be completed on this host.

## Audited Revision

- branch: `mvp2/userflow-containment`
- pre-patch rollback ref: `a22d242`
- audited head: `112ef22`
- applied patch commits:
  - `7972c11 feat(report): add profile report cards`
  - `c0c545d refactor(report): render profile from report cards`
  - `112ef22 docs(report): document card-composed profile reports`

The disposable patch files were removed after conversion into commits.

## Automated Evidence

Passed:

- `git diff --check`
- `make release-audio-check`
  - Python compilation passed.
  - full suite: `425 passed`
  - documentation checks: `10 passed`
  - `ffmpeg` available
  - `.venv/bin/whisper` available
- focused report-card, user-report, and Telegram profile checks:
  `8 passed`
- `docker compose config --quiet`
- branch ancestry check: `origin/epic/input-funnel-alpha` is an ancestor

Profile projection checks covered empty, single-episode, and richer samples:

| Sample | Summary characters | Details characters | Internal terms |
|---|---:|---:|---|
| empty | 103 | 80 | none |
| single | 561 | 597 | none |
| rich | 552 | 1071 | none |

All measured outputs remain below Telegram's 4096-character message limit.
Tests also confirm deterministic card ordering, cautious sample-bound wording,
partial and insufficient-data states, and no profile mutation of classic or
audio flow state.

## Runtime Baseline

Only artifact counts were inspected; no private artifact contents were read.

| Runtime surface | Baseline |
|---|---:|
| episodes | 112 files |
| runtime sessions | 1 file |
| runtime flows | 0 files |
| intake transcripts | 6 files |
| episode drafts | directory absent |
| UX events | 2 files / 6090 lines |

## Required Operator Smoke

Not completed.

The required matrix remains:

- idle text and media containment
- classic 10Q start, text continuation, media rejection, and cancellation
- `/voice` arming, armed text rejection, supported and unsupported media
- successful transcript creation with return to idle
- post-audio idle containment
- `/help` and `/profile` without flow mutation
- artifact-count comparison confirming no episode, draft, or raw-audio
  retention from audio intake

## Blocker

Docker startup could not reach the host daemon:

```text
permission denied while trying to connect to the Docker daemon socket
```

The privileged fallback also could not run because this environment cannot
supply the required sudo password. Therefore container startup health, Telegram
connectivity, the live containment matrix, and post-smoke artifact deltas remain
unverified.

No code or contract blocker was found by the automated audit. Do not mark the
MVP ready or tag a release until the documented live smoke passes on a host with
Docker access and an approved Telegram test user.

## Known Risks

- Automated Telegram handler tests cannot prove host Docker permissions,
  Telegram network connectivity, or real media-provider behavior.
- Existing private runtime artifacts were intentionally left untouched.

## Rollback

- episode schema migration required: no
- runtime session compatibility: expected yes; compatibility tests pass
- private data touched by this audit: no
- report-card changes affect computed `/profile` projections only
- rollback ref: `a22d242`

Operator rollback:

```bash
git switch --detach a22d242
docker compose build bot
docker compose up -d bot
```

Do not delete private runtime data as part of rollback.

## Unblock Criteria

On a Docker-capable host:

1. Build and start the bot container from the audited branch.
2. Complete every scenario in `docs/workflows/audio-input-smoke.md`.
3. Compare count-only runtime baselines before and after the smoke.
4. Confirm no prohibited episode, draft, or raw-audio artifact was created.
5. Update this audit with the smoke evidence and change the decision to
   `ready` only if every required scenario passes.
