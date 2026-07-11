# Telegram Capture

## Purpose

Adapt Telegram messages and callbacks into the capture pipeline.

Telegram Capture owns Telegram-specific receiving, access checks, callbacks,
UX events, and explicit userflow routing. It should not own the full interview
architecture. `/start` and `/10q` enter `classic_10q`; `/3b`, `/1t`, and `/1a`
arm first-class pre-draft flows. Completed 3B, 1T, and accepted audio evidence
is persisted as a `CaptureArtifact`, extracted into a complete draft, and sent
directly to review. Audio requires an additional transcript-confirmation gate.

## Inputs

- Telegram user text messages.
- Telegram voice notes and audio uploads when enabled.
- Telegram callback data where still used by bot control flow.
- private in-progress session memory under `data/runtime-sessions/`.
- private explicit flow state under `data/runtime-flows/`.
- private review state under `data/runtime-sessions/review/`.
- tone configuration from `app/tone.yaml`.

## Outputs

- private `CaptureArtifact` and `CaptureExtraction` records.
- durable `IntakeTranscript` source artifacts when using `one_take_audio`.
- schema-complete provisional fields in `DraftReviewSession`.
- completed private observed source episode files under `data/episodes/`.
- private UX event records under `data/ux-events/`.

## Dependencies

- Episode Model + Storage for validation and persistence.
- Graph Reporting for user-facing `/profile` projections over processed
  episodes.
- Userlist / Access for approved-user checks.
- UX Analytics for loop event logging.
- Runtime Storage for atomic state writes, per-chat ordering, and bounded
  blocking provider work.

## Interfaces

- `capture_to_episode`
- `capture_to_draft`
- `draft_to_episode`

## Lifecycle

`experimental`

The four capture strategies are usable, but extraction prompts, provider
operations, and review copy can still evolve.

Classic 10Q presents one concise question at a time after the progress line.
Field-guide titles, examples, and tips remain internal reference material and
are not included in Telegram question messages.

The public Telegram command menu exposes `/start`, `/10q`, `/3b`, `/1t`,
`/1a`, `/status`, `/profile`, `/cancel`, and `/help`. Former compatibility
commands are retired; unknown commands return `/help` guidance without changing
flow state. Admin and operator commands remain hidden from regular users.

Episode files are observed source artifacts. Telegram capture does not persist
top-level `derived` or `current_derived`.

`/profile` requests a plain-language summary and details projection from Graph
Reporting for the current Telegram chat. Telegram Capture owns command
delivery, not report analytics or composition. Regular users should not
receive raw technical payload Markdown through this command.

In production mode, `/profile` requests the brief first. The explicit details
callback requests expanded interpretation only on cache miss and then reuses the
cached expanded text for repeated callbacks.

Different chats may be processed concurrently. Updates for the same chat remain
ordered, and one process lock prevents a second bot writer from using the same
runtime-flow root.
