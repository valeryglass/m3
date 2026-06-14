# capture_to_episode

## Contract

Telegram Capture produces confirmed observed episode fields and hands them to
Episode Model + Storage for validation and persistence.

For new capture work, prefer the more explicit path:

```text
input_to_draft -> gap_hydration -> draft_to_episode
```

This interface remains the compatibility boundary for flows that already hand
complete observed fields directly to storage.

## Input

- one active loop session.
- observed CBT fields collected from text replies.
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
