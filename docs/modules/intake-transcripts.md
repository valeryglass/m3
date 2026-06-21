# Intake Transcripts

## Purpose

Store the first durable source artifact for explicit `one_take_audio` intake
after temporary media has been transcribed.

```text
one_take_audio
  -> audio_intake_started
  -> raw audio as temporary runtime material
  -> IntakeTranscript source artifact
  -> full transcript confirmation
  -> optional situation-only EpisodeDraft
  -> confirmed Episode backlink
```

## Guarantees

- Raw audio is not persisted by this module.
- Telegram `file_id` is not persisted by default.
- Transcript text is persisted as private source material for future reannotation or extraction.
- Transcript artifacts are not canonical episodes and do not enter graph/report analytics directly.
- Telegram Capture may read a confirmed transcript to seed an EpisodeDraft.
- Rejecting transcript use retains this artifact and creates no draft.
- A saved episode may populate the existing optional `episode_id` backlink.

## Storage

Default storage path:

```text
data/intake-transcripts/telegram-chat-<chat_id>/message-<message_id>.json
```

The path is deterministic for a Telegram source message so retrying the same message does not create duplicate transcript artifacts.
