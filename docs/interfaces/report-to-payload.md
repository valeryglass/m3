# report_to_payload

## Contract

Insight Payloads provide shared deterministic analytics to Pattern Payloads.
Pattern Payloads project those analytics into renderer-neutral map and spatial
payload JSON.

## Input

- `InsightPayload` shared analytics artifact.
- report-ready episode set when map-specific graph entities still need direct
  provenance and topology.
- optional spatial projection derived from the same `InsightPayload`.

## Output

- renderer-neutral map payload JSON.
- standalone map HTML preview exports.
- tracked explicit map exports under `data/exports/map-payload/`.

## Guarantees

- payloads include provenance for graph-ready and skipped episodes.
- reports and maps consume the same shared analytics payload for primary motifs,
  forks, contrasts, counterexamples, and outcome patterns.
- payloads avoid diagnostic claims and stable trait claims.
- map payloads and previews are explicit exports, not canonical source
  artifacts.
- tracked map exports may contain derived private data and should be committed
  only when intentionally sharing that export surface.
- timespan analytics use fixed 1-week buckets.
- map payloads expose graph-derived semantics and provenance without choosing a
  final visual renderer.
- file exports fail before writing unless an explicit annotation-run gives full
  coverage and payload eligibility for every selected-source episode.

## Ownership

- producer: `insight_payloads`
- consumer: `pattern_payloads`
