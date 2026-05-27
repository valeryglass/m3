# capture_to_episode

## Contract

Telegram Capture produces observed episode fields and hands them to Episode
Model + Storage for validation and persistence.

## Input

- one active loop session.
- plain text replies for observed CBT frames.
- source metadata such as Telegram chat id.

## Output

- Episode JSON conforming to `model/episode.schema.json`.
- private saved file under `data/episodes/` when the episode is complete.

## Guarantees

- observed fields remain user-stated or minimally normalized.
- derived data remains empty at Telegram save time.
- saved episodes must validate against the schema.

## Ownership

- producer: `telegram_capture`
- consumer: `episode_model_storage`
