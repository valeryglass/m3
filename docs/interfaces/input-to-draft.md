# input_to_draft

## Contract

Input Funnels hand normalized input artifacts to Episode Drafts. Episode Drafts
return a provisional draft, not a saved episode.

## Input

- normalized input artifact.
- optional active runtime session.
- optional current capture mode such as one-take, classic question flow, or
  three-block narrative.

## Output

- episode draft with partial observed fields.
- missing-field and weak-field notes.
- source quote references where available.

## Guarantees

- no canonical episode is persisted by this interface.
- audio and transcripts remain pre-episode evidence.
- transcript text may seed only `observed.situation` after explicit transcript
  confirmation.
- all downstream persistence still goes through `draft_to_episode` and Episode
  Model + Storage.

## Ownership

- producer: `input_funnels`
- consumer: `episode_drafts`

## Lifecycle

`draft`
