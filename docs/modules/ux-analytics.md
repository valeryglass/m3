# UX Analytics

## Purpose

Record and aggregate step-level Telegram loop UX events.

## Inputs

- capture flow event records.
- private JSONL logs under `data/ux-events/`.

## Outputs

- append-only private event logs.
- aggregate UX summaries from the CLI or admin command.
- optional Markdown and JSON debug exports.

## Dependencies

- Telegram Capture for event emission.

## Interfaces

- `capture_to_episode`

## Lifecycle

`prototype`

The event log exists and is useful, but analytics outputs are still lightweight.

`app.ux_analytics` writes files only when `--output-dir` is explicitly passed.
