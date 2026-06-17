# Intake Transcripts

## Purpose

Store the first durable truth artifact for audio intake after temporary media has been transcribed.

```text
raw audio -> temporary runtime material
transcript -> durable intake source artifact
episode -> future validated structured artifact
```

## Guarantees

- Raw audio is not persisted by this module.
- Telegram `file_id` is not persisted by default.
- Transcript text is persisted as private source material for future reannotation or extraction.
- Transcript artifacts are not canonical episodes and do not enter graph/report analytics directly.

## Storage

Default storage path:

```text
data/intake-transcripts/telegram-chat-<chat_id>/message-<message_id>.json
```

The path is deterministic for a Telegram source message so retrying the same message does not create duplicate transcript artifacts.
