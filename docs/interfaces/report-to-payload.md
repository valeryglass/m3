# report_to_payload

## Contract

Graph Reporting provides report-ready episode summaries and signature counters
to Psy Payload.

## Input

- report-ready episode set.
- signature counters, pairings, outcome contours, and 1-week buckets.

## Output

- technical domain payload Markdown.
- renderer-neutral map payload JSON.

## Guarantees

- payload reports include gaps when episodes are not graph-ready.
- payload reports avoid diagnostic claims and stable trait claims.
- timespan analytics use fixed 1-week buckets.
- map payloads expose graph-derived semantics and provenance without choosing a
  final visual renderer.

## Ownership

- producer: `graph_reporting`
- consumer: `psy_payload`
