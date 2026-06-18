# Intake Transcripts

## Purpose

Store the first durable source artifact for explicit `audio_one_take` intake
after temporary media has been transcribed.

```text
audio_one_take
  -> audio_intake_started
  -> raw audio as temporary runtime material
  -> IntakeTranscript source artifact
  -> transcript preview
  -> audio_intake_completed
  -> idle
```

## Guarantees

- Raw audio is not persisted by this module.
- Telegram `file_id` is not persisted by default.
- Transcript text is persisted as private source material for future reannotation or extraction.
- Transcript artifacts are not canonical episodes and do not enter graph/report analytics directly.
- This module does not create an `EpisodeDraft`, `LoopSession`, or episode.
- Future transcript extraction requires a separate validation flow and explicit
  architecture decision.

## Storage

Default storage path:

```text
data/intake-transcripts/telegram-chat-<chat_id>/message-<message_id>.json
```

The path is deterministic for a Telegram source message so retrying the same message does not create duplicate transcript artifacts.
