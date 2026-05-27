# report_to_profile

## Contract

Graph Reporting provides report-ready episode summaries and profile maturity
metrics to Profile Brief.

## Input

- report-ready episode set.
- profile maturity summary.
- signature counters and pairings.

## Output

- evidence-bound CBT pattern brief Markdown.

## Guarantees

- profile maturity describes reliability of the profile, not diagnostic content.
- profile briefs must include gaps when episodes are not graph-ready.
- profile briefs must avoid diagnostic claims.

## Ownership

- producer: `graph_reporting`
- consumer: `profile_brief`
