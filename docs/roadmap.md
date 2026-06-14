# Roadmap

## Current Release Track

### Input Funnels And Episode Draft Hydration

Status: alpha foundation.

The epic has produced a shared runtime path for text, hidden command, hidden
three-block, voice, audio, and audio-document inputs:

```text
input surface -> InputArtifact -> EpisodeDraft -> Gap Hydration -> Draft Review -> confirmed episode
```

Accepted alpha result:

- one-take text can start draft capture.
- hidden `/capture <text>` can start draft capture explicitly.
- hidden `/capture3 a | b | c` can start a three-block draft.
- voice/audio/document inputs are recognized as input artifacts.
- untranscribed media stops before draft creation.
- draft review is explicit before persistence.
- funnel, gap-question, confirmation, save, discard, and rejection metrics are
  visible in UX analytics.

Not yet production feature status:

- audio/voice is not a production capture feature until transcription is wired.
- hidden command routes are alpha/test affordances, not polished user UX.
- one-take text is the only new user-visible capture behavior in this epic.
- episode schema, annotation runs, graph reports, and map payload behavior are
  intentionally unchanged.

## Production Readiness Track

### PR-00 Full-suite test hygiene

Goal: make the current patch train pass the full local focused test surface
without environment-dependent assertion failures.

Acceptance:

- full `tests/test_telegram_bot.py` passes in the local dev environment.
- fallback behavior without optional Telegram UI classes is explicit in tests.
- gap-question events are reflected in expected UX event sequences.

### PR-01 Release status and operator notes

Goal: document the actual shipped feature state so alpha operators do not market
placeholder audio as full audio capture.

Acceptance:

- README or operator docs distinguish `alpha foundation`, `active text capture`,
  and `media pending transcription`.
- `/capture` and `/capture3` are documented as hidden/manual alpha tools.
- audio/voice status says `received, not transcribed yet`.

### PR-02 Transcription provider boundary

Goal: choose and wire a real transcription provider behind the existing passive
`app.transcription` boundary.

Acceptance:

- voice/audio files can produce `TranscriptResult` or a clear failure.
- raw audio is not persisted by default.
- transcript text is treated as support evidence, not canonical episode data.
- provider errors emit UX events without creating drafts.

### PR-03 Voice/audio draft creation

Goal: allow transcribed media to enter the same draft/session path as text.

Acceptance:

- Telegram `voice` with transcript creates an episode draft.
- Telegram `audio` and audio-like `document` with transcript create drafts.
- missing transcript still blocks draft creation.
- confirmation remains required before persistence.

### PR-04 Production smoke checklist

Goal: define a small operator checklist for deploy readiness.

Acceptance:

- manual smoke covers `/start`, plain text, `/capture`, `/capture3`, voice,
  audio, unsupported document, save, cancel, `/profile`, and `/report_ux`.
- smoke test avoids private source data and generated export snapshots.
- expected UX events are listed for each flow.

### PR-05 Runtime compatibility and rollback

Goal: make the runtime-session changes safe to deploy and roll back.

Acceptance:

- legacy sessions without `capture_funnel` and `media_kind` keep working.
- rollback note explains that these session fields are optional metadata.
- no episode schema migration is required.

### PR-06 Production retention and privacy policy

Goal: define production behavior for audio/transcripts before real media capture
is enabled.

Acceptance:

- retention periods are defined for raw audio, transcripts, UX events, and
  runtime sessions.
- default is no raw audio persistence unless a later ADR changes it.
- user export/delete expectations are documented.
