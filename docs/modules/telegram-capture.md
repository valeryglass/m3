# Telegram Capture

## Purpose

Collect observed CBT episode frames through Telegram and save completed episodes
through the episode storage boundary.

## Inputs

- Telegram user messages.
- Telegram callback data where still used by bot control flow.
- private in-progress state under `data/state/`.
- tone configuration from `config/tone.yaml`.

## Outputs

- observed episode fields.
- completed private episode files under `data/episodes/`.
- private UX event records under `data/ux-events/`.

## Dependencies

- Episode Model + Storage for validation and persistence.
- Userlist / Access for approved-user checks.
- UX Analytics for loop event logging.

## Interfaces

- `capture_to_episode`

## Lifecycle

`experimental`

The flow is usable, but prompt copy and frame order can still evolve.
