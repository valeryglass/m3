# Telegram Capture

## Purpose

Adapt Telegram messages and callbacks into the capture pipeline.

Telegram Capture owns Telegram-specific receiving, access checks, callbacks,
UX events, and explicit userflow routing. It should not own the full interview
architecture. `/start` and `/10q` enter `classic_10q`; `/3b`, `/1t`, and `/1a`
arm first-class pre-draft flows. All accepted inputs enter Episode Drafts and
Gap Hydration. Audio requires an additional transcript-confirmation gate.

## Inputs

- Telegram user text messages.
- Telegram voice notes and audio uploads when enabled.
- Telegram callback data where still used by bot control flow.
- private in-progress session memory under `data/runtime-sessions/`.
- private explicit flow state under `data/runtime-flows/`.
- tone configuration from `config/tone.yaml`.

## Outputs

- normalized input artifacts when using the draft pipeline.
- durable `IntakeTranscript` source artifacts when using `one_take_audio`.
- confirmed observed episode fields when using the legacy direct path.
- completed private observed source episode files under `data/episodes/`.
- private UX event records under `data/ux-events/`.

## Dependencies

- Episode Model + Storage for validation and persistence.
- Graph Reporting for user-facing `/profile` projections over processed
  episodes.
- Userlist / Access for approved-user checks.
- UX Analytics for loop event logging.

## Interfaces

- `capture_to_episode`
- `input_to_draft`
- `draft_to_episode`

## Lifecycle

`experimental`

The four capture strategies are usable, but prompt copy, frame order, and draft
hydration can still evolve.

Classic 10Q presents one concise question at a time after the progress line.
Field-guide titles, examples, and tips remain internal reference material and
are not included in Telegram question messages.

Episode files are observed source artifacts. Telegram capture does not persist
top-level `derived` or `current_derived`.

`/profile` requests a plain-language summary and details projection from Graph
Reporting for the current Telegram chat. Telegram Capture owns command
delivery, not report analytics or composition. Regular users should not
receive raw technical payload Markdown through this command.
