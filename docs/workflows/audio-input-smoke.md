# Audio Input Smoke Checklist

Use this checklist on `mvp2/audio-input` before marking audio capture deployable.

## Preconditions

- Branch is based on `epic/input-funnel-alpha`.
- Default transcription provider is `whisper`.
- Whisper command, model, and language values are known to the operator.
- Raw audio retention remains disabled; media is temporary-only.
- Test user is approved in the userlist.

## Commands

Run local checks first:

```bash
make release-audio-check
```

If `make check-whisper` fails, install Whisper on the runtime host or set
`M3_WHISPER_COMMAND` to a valid command before inviting alpha users.

## Manual Telegram Smoke

| Flow | Expected result |
|---|---|
| `/start` | starts guided capture |
| plain text without session | starts one-take draft capture |
| `/capture text` | starts hidden one-take draft capture |
| `/capture3 a \| b \| c` | starts hidden three-block draft capture |
| voice note under limit | transcribes, creates draft, asks next gap question |
| audio upload under limit | transcribes, creates draft, asks next gap question |
| audio-like document under limit | transcribes, creates draft, asks next gap question |
| non-audio document | rejected politely before provider call |
| audio over duration cap | rejected politely before provider call |
| failed transcription | no draft, asks for text |
| save | persists confirmed observed episode |
| cancel | discards runtime draft/session |
| `/profile` | still computes report on demand |
| `/report_ux` | includes funnel/media/transcription metrics |

## UX Event Expectations

Successful media capture should include:

```text
input_received
transcript_created
input_received
draft_created
session_started
step_answered
step_prompted
gap_question_asked
```

Failed media capture should include one of:

```text
input_rejected
media_download_failed
transcription_failed
transcription_pending
```

## Release Notes

Use honest wording:

```text
Audio input is enabled for short voice/audio notes. Audio is transcribed first,
then turned into a draft. Nothing is saved as an episode until the user confirms.
Raw audio is temporary-only by default.
```

Do not claim:

```text
long-form transcription
voice emotion detection
raw audio archive
clinical interpretation
```

## Readiness Note

Audio alpha is releasable only after this manual smoke passes. Rollback does not
require an episode schema migration, raw audio deletion, or private data
deletion because raw audio is temporary-only by default.
