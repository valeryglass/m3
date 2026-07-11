# 0016: Split Profile Interpretation Calls

## Status

Accepted and implemented for RM-A10.

## Context

RM-A9 asked one probabilistic provider response to contain a brief, expanded
sections, limitations, one question, and map-focus hints. A schema or grounding
failure in any component discarded the complete response and made both Telegram
report surfaces fall back together.

The Telegram interaction already separates the brief `/profile` command from
the explicit `profile:details` callback. The provider boundary should follow
that user flow.

## Decision

Production profile interpretation uses two independent calls over the same safe
`ReportInterpretationInput` registry:

```text
/profile -> BriefReportInterpretation
Подробнее -> ExpandedReportInterpretation
```

- The brief call returns one synthesis and at most one grounded question.
- The expanded call returns two to five meaning sections, optional limitations,
  and at most one grounded question.
- Validated artifact IDs selected by the brief may be passed to expanded as
  priority hints. Generated brief prose is not passed between calls.
- Expanded generation is lazy. It runs only when the details callback has no
  cached expanded text.
- Brief and expanded have independent deterministic fallbacks and journal
  events.
- Both DeepSeek calls use the explicit profile model with thinking disabled.
- LLM map-focus generation is paused. Deterministic `MapPayload`, map primitive,
  and operator export contracts remain unchanged.

## Consequences

- A malformed expanded response cannot discard a valid brief, and a failed brief
  does not prevent an expanded attempt.
- Users who do not open details incur only the brief provider call.
- Opening details may incur a second provider call; repeated details callbacks
  reuse Telegram `chat_data` cache while the process remains alive.
- Report JSON contracts are smaller and can be diagnosed per surface.
- No episode, annotation-run, `InsightPayload`, or `MapPayload` schema changes.

## Rejected Alternative

Keep one provider bundle and add more normalization. This preserves one request
but retains all-or-nothing failure coupling between unrelated report and map
components.
