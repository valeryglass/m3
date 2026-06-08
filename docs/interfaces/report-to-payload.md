# report_to_payload

## Contract

Graph Reporting provides computed graph-view summaries and signature counters to
Pattern Payloads.

## Input

- report-ready episode set.
- signature counters, pairings, outcome contours, and 1-week buckets.

## Output

- renderer-neutral map payload JSON.
- standalone map HTML preview exports.
- tracked explicit map exports under `data/exports/map-payload/`.

## Guarantees

- payloads include provenance for graph-ready and skipped episodes.
- payloads avoid diagnostic claims and stable trait claims.
- map payloads and previews are explicit exports, not canonical source
  artifacts.
- tracked map exports may contain derived private data and should be committed
  only when intentionally sharing that export surface.
- timespan analytics use fixed 1-week buckets.
- map payloads expose graph-derived semantics and provenance without choosing a
  final visual renderer.

## Ownership

- producer: `graph_reporting`
- consumer: `pattern_payloads`
