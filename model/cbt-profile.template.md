# Domain Report

- scope: {{source}}
- episodes: {{episode_count}}
- report_ready: {{report_ready_count}}
- profile_eligible: {{profile_eligible_count}}
- timespan_quant: 1week

## Observations

- Evidence base: {{eligible_episode_count}} profile-eligible episodes.
- Coverage: {{coverage_percent}}% of collected episodes are report-ready.
- Pattern diversity: {{signature_diversity_count}} distinct graph signatures.
- Freshness: latest episode is {{latest_episode_date}}.
- Confidence band: {{confidence_band}}.

## Patterns

- Repeated loops:
  - {{trigger_type}} -> {{emotion_label}} -> {{behavior_type}}: {{episode_count}} episodes
- Behavior to outcome contours:
  - {{behavior_type}} -> {{outcome_type}}: {{episode_count}} episodes

## Exceptions

- Same context can lead to different behaviors:
  - {{trigger_type}} -> {{emotion_label}}: {{behavior_type}} ({{episode_count}}), {{behavior_type}} ({{episode_count}})
- Rare loops:
  - {{trigger_type}} -> {{emotion_label}} -> {{behavior_type}}: {{episode_count}} episode

## Changes

- Temporal grouping uses fixed 1week buckets.
- New in latest week: {{new_patterns}}.
- Stable across weeks: {{stable_patterns}}.

## Questions

- {{evidence_bound_question}}

## Insights

- {{short_non_diagnostic_synthesis}}

## Gaps

- {{gap_reason}}: {{episode_count}}
