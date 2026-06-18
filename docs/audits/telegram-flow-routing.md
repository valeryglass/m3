# Telegram Flow Routing Audit

## Current Entry Points

| Entry point | Classification | Current behavior | Containment target |
|---|---|---|---|
| `/start` -> `_handle_start_after_authorized` | explicit command | starts or restarts classic 10Q | keep as the normal classic 10Q entry |
| active text -> `_handle_message_after_authorized` | active continuation | answers the current 10Q step | keep |
| idle text -> `_handle_message_after_authorized` | idle fallback | starts one-take text capture | replace with `/start` guidance |
| idle media -> voice/audio/document handlers | idle fallback | downloads and transcribes immediately | require an armed `/voice` flow |
| active 10Q media -> media handlers | active-flow conflict | rejects media and asks for text | keep through router decision |
| `/capture` -> `_start_text_capture_session` | hidden developer route | explicitly creates a draft-backed session | keep hidden and explicit |
| `/capture3` -> `_start_episode_draft_capture_session` | hidden developer route | explicitly creates a three-block session | keep hidden and explicit |
| media -> `_transcribe_media_artifact_or_reply` | audio intake operation | stores `IntakeTranscript` and previews it | call only from armed audio flow |
| `/cancel` -> `_handle_cancel_after_authorized` | explicit command | deletes classic `LoopSession` only | clear whichever userflow is active |

## Coupling Found

- Idle text can create a `LoopSession` without an explicit flow command.
- Idle media can start transcription without an explicit flow command.
- Audio eligibility is inferred from `LoopSession` shape instead of separate
  audio-flow state.
- `/cancel` does not know about audio intake state.

## Accepted Containment

```text
idle + /start -> classic_10q
idle + /voice -> audio_one_take awaiting media
idle + arbitrary text/media -> /start guidance
classic_10q + text -> current step
classic_10q + media -> text-required guidance
audio_one_take + media -> transcript artifact, preview, close
audio_one_take + text -> media-or-cancel guidance
```

`IntakeTranscript` remains a source artifact. The router must not convert audio
intake into an `EpisodeDraft`, episode, annotation, graph, or report.
