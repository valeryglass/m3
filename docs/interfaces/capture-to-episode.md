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
- saved episode files are observed source artifacts.
- Telegram save does not persist top-level `derived` or `current_derived`.
- saved episodes must validate against the schema.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.

## Ownership

- producer: `telegram_capture`
- consumer: `episode_model_storage`
