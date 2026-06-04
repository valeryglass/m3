# report_to_payload

## Contract

Graph Reporting provides report-ready episode summaries and signature counters
to Pattern Payloads.

## Input

- report-ready episode set.
- signature counters, pairings, outcome contours, and 1-week buckets.

## Output

- renderer-neutral map payload JSON.

## Guarantees

- payloads include provenance for graph-ready and skipped episodes.
- payloads avoid diagnostic claims and stable trait claims.
- timespan analytics use fixed 1-week buckets.
- map payloads expose graph-derived semantics and provenance without choosing a
  final visual renderer.

## Ownership

- producer: `graph_reporting`
- consumer: `pattern_payloads`
