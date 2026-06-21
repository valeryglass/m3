# First-Class Draft Capture Readiness Audit — 2026-06-21

## Decision

`blocked`

The implementation and automated gates pass. Release readiness remains blocked
because this host cannot access the Docker daemon, so container startup and the
required live Telegram smoke matrix were not completed.

## Audited Revision

- branch: `mvp2/userflow-containment`
- pre-epic rollback ref: `a7dec33`
- implementation range: `c4b0dc1..11ac5fe`
- commits:
  - `c4b0dc1 feat(capture): add typed draft capture flows`
  - `ed4b38e feat(bot): promote draft capture commands`
  - `11ac5fe docs(architecture): accept draft capture modes`

## Automated Evidence

Passed:

- `git diff --check`
- `make release-audio-check`
  - full suite: `471 passed`
  - documentation checks: `10 passed`
  - ffmpeg available
  - `.venv/bin/whisper` available
- `docker compose config --quiet`
- focused capture/router/session/transcript/Telegram checks
- Python Telegram `CommandHandler` and `BotCommand` construction for `/10q`,
  `/3b`, `/1t`, `/1a`, and `/1v`

Automated coverage includes:

- typed pre-draft TTL state and legacy audio-flow loading;
- active-flow containment and `/cancel` requirements;
- classic, one-take text, and sequential three-block draft hydration;
- complete transcript chunking within Telegram limits;
- transcript Continue and Reject behavior;
- no episode before final Save;
- transcript-to-episode backlink after Save;
- legacy `LoopSession` loading and optional transcript-link persistence;
- unchanged `/profile` code path and report contracts.

## Runtime Baseline

Only artifact counts were inspected. No episode, transcript, annotation, or
payload text was printed.

| Runtime surface | Baseline |
|---|---:|
| episodes | 113 files |
| runtime sessions | 1 file |
| runtime flows | 0 files |
| intake transcripts | 6 files |
| retained runtime audio | 0 files |

The intentional local map export remains untracked and was not staged.

## Required Live Smoke

Not completed:

- `/start` and `/10q` equivalence;
- `/1t` arming, text intake, hydration, review, Save, and Cancel;
- `/3b` restart-safe three-answer intake and hydration;
- `/1a`, hidden `/1v`, and legacy `/voice` aliases;
- voice, audio, supported document, and unsupported media handling;
- full transcript rendering, Reject retention, Continue hydration, and final
  episode backlink;
- flow conflicts, TTL expiry, `/cancel`, `/help`, and `/profile`;
- before/after count comparison confirming expected session, flow, transcript,
  episode, UX-event, and raw-audio behavior.

## Blocker

Both normal and approved Docker build attempts failed before image construction:

```text
permission denied while trying to connect to the Docker daemon socket
```

No code or contract blocker was found by automated validation. Do not mark this
epic release-ready until the live matrix in
`docs/workflows/audio-input-smoke.md` passes on a Docker-capable host with an
approved Telegram test user and working transcription provider.

## Compatibility And Rollback

- episode schema migration required: no
- existing `LoopSession` files: compatible through optional defaults
- existing `audio-one-take` flow files: compatible through legacy loading
- private data migration required: no
- raw-audio retention introduced: no
- rollback ref: `a7dec33`

Operator rollback:

```bash
git switch --detach a7dec33
docker compose build bot
docker compose up -d bot
```

Do not delete private episodes, transcripts, sessions, flows, or exports during
rollback.
