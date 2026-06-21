# draft_to_episode

## Contract

Episode Drafts hand confirmed observed fields to Episode Model + Storage for
schema validation and persistence.

## Input

- a complete or sufficiently hydrated episode draft.
- explicit user confirmation.
- source metadata needed to construct the episode `source` field.

## Output

- Episode JSON conforming to the canonical episode schema.
- private saved file under the configured episode directory.

## Guarantees

- unconfirmed drafts are not persisted as episodes.
- saved episodes contain observed fields only.
- saved episodes do not persist top-level `derived` or `current_derived`.
- saved episodes validate against the schema.
- an audio-derived save may link its source `IntakeTranscript` to the new
  episode identifier without storing transcript metadata in the episode.

## Ownership

- producer: `episode_drafts`
- consumer: `episode_model_storage`

## Lifecycle

`draft`
