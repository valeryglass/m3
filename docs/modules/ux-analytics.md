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

No formal storage interface. Telegram Capture emits the current runtime events.

## Funnel Success Metrics

Input funnel metrics are product-facing UX signals, not new graph/report facts.
They help compare capture routes while preserving the canonical episode boundary.

Current summary-level metrics:

```text
inputs_by_funnel
inputs_by_media_kind
drafts_created_by_funnel
avg_draft_fields_by_funnel
gap_questions_by_funnel
gap_questions_by_target
avg_gap_questions_by_funnel
transcription_pending_by_funnel
input_rejections_by_reason
```

Interpretation rules:

- `inputs_by_funnel` and `inputs_by_media_kind` show which intake surfaces users
  attempt to use.
- `drafts_created_by_funnel` shows which funnels can produce usable provisional
  drafts.
- `avg_draft_fields_by_funnel` is an early completeness signal, not a quality
  score.
- `gap_questions_by_funnel` and `gap_questions_by_target` show how much
  follow-up questioning each route creates.
- `avg_gap_questions_by_funnel` averages follow-up questions per session for a
  funnel.
- `transcription_pending_by_funnel` shows where media support exists but cannot
  yet create drafts because transcription is unavailable.
- `input_rejections_by_reason` separates unsupported or malformed input from
  user drop-off.

Metrics that may graduate later after confirmation/save boundaries exist:

```text
draft_confirmed_by_funnel
draft_discarded_by_funnel
episodes_saved_by_funnel
```

Non-goals:

- do not store raw private text/audio/transcripts in aggregate UX summaries.
- do not infer clinical state, emotion-from-voice, or prosody from funnel events.
- do not treat media rejection as episode model failure.
- do not treat draft-field count as report readiness.

## Lifecycle

`prototype`

The event log exists and is useful, but analytics outputs are still lightweight.

`app.ux_analytics` writes files only when `--output-dir` is explicitly passed.
