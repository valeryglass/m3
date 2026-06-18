# Telegram Capture

## Purpose

Adapt Telegram messages and callbacks into the capture pipeline.

Telegram Capture owns Telegram-specific receiving, access checks, callbacks,
UX events, and explicit userflow routing. It should not own the full interview
architecture. `/start` enters `classic_10q`; hidden `/voice` arms
`audio_one_take`. Hidden text developer routes may use Episode Drafts and Gap
Hydration, but audio intake ends at an `IntakeTranscript` source artifact.

## Inputs

- Telegram user text messages.
- Telegram voice notes and audio uploads when enabled.
- Telegram callback data where still used by bot control flow.
- private in-progress session memory under `data/runtime-sessions/`.
- private explicit flow state under `data/runtime-flows/`.
- tone configuration from `config/tone.yaml`.

## Outputs

- normalized input artifacts when using the draft pipeline.
- durable `IntakeTranscript` source artifacts when using `audio_one_take`.
- confirmed observed episode fields when using the legacy direct path.
- completed private observed source episode files under `data/episodes/`.
- private UX event records under `data/ux-events/`.

## Dependencies

- Episode Model + Storage for validation and persistence.
- Graph Reporting for user-facing `/profile` summaries over processed episodes.
- Userlist / Access for approved-user checks.
- UX Analytics for loop event logging.

## Interfaces

- `capture_to_episode`

Planned downstream capture work may use `input_to_draft` and `draft_to_episode`
after Telegram-specific receiving and access checks. `audio_one_take` does not
use either interface.

## Lifecycle

`experimental`

The classic text flow and explicit transcript intake are usable, but prompt copy,
frame order, and draft hydration can still evolve.

Episode files are observed source artifacts. Telegram capture does not persist
top-level `derived` or `current_derived`.

`/profile` renders a plain-language summary and details view from graph report
data for the current Telegram chat. Regular users should not receive raw
technical payload Markdown through this command.
