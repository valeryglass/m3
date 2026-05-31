# report_to_profile

## Contract

Graph Reporting provides report-ready episode summaries and profile maturity
metrics to CBT Profile and CBT Analytics.

## Input

- report-ready episode set.
- profile maturity summary.
- signature counters, pairings, outcome contours, and 1-week buckets.

## Output

- user-facing evidence-bound domain report Markdown.
- internal CBT analytics Markdown.

## Guarantees

- profile maturity describes reliability of the profile, not diagnostic content.
- CBT profiles must include gaps when episodes are not graph-ready.
- CBT profiles must avoid diagnostic claims.
- timespan analytics use fixed 1-week buckets in v0.2.

## Ownership

- producer: `graph_reporting`
- consumers: `cbt_profile`, `cbt_analytics`
