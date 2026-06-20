# report_to_insight_payload

## Contract

Graph Reporting provides computed graph-ready report material to Insight
Payloads. Insight Payloads package deterministic analytics into a shared,
target-agnostic artifact for downstream consumers.

## Input

- `GraphReport` built from report-ready episodes.
- deterministic pattern metrics and support provenance.

## Output

- `InsightPayload` object or JSON export.

## Guarantees

- payload fields are deterministic for the same input report.
- analytics use distinct supporting episode IDs where support counts are shown.
- payloads retain provenance for supported motifs, forks, counterexamples,
  contrasts, and outcome patterns.
- payloads retain distinct episode provenance for primary/secondary life-domain
  support and compact primary-domain summaries.
- payloads contain raw analytics labels, not localized report copy.
- payloads avoid diagnostic claims and stable trait claims.
- file exports require explicit annotation-run selection, full selected-source
  coverage, and payload eligibility for every selected episode.

## Ownership

- producer: `graph_reporting`
- consumer: `insight_payloads`
