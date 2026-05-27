# Profile Brief

## Purpose

Produce evidence-bound CBT pattern briefs from report-ready episodes.

## Inputs

- report-ready episodes.
- profile maturity metrics.
- graph signature counters.

## Outputs

- Markdown profile briefs under `data/reports/profile/`.

## Dependencies

- Graph Reporting for maturity and signature aggregation logic.
- Readiness gates for profile eligibility.

## Interfaces

- `report_to_profile`

## Lifecycle

`experimental`

The brief is a local derived summary. It must stay evidence-bound and avoid
diagnostic claims.
