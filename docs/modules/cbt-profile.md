# CBT Profile

## Purpose

Produce user-facing evidence-bound CBT domain reports from report-ready episodes.

## Inputs

- report-ready episodes.
- profile maturity metrics.
- CBT graph signatures and outcome contours.

## Outputs

- Markdown domain reports under `data/reports/cbt-profile/`.
- report shape follows `model/cbt-profile.template.md`.

## Dependencies

- Graph Reporting for maturity and signature aggregation logic.
- Readiness gates for profile eligibility.

## Interfaces

- `report_to_profile`

## Lifecycle

`experimental`

The profile is a local derived summary for users. It must stay evidence-bound
and avoid diagnostic claims.

Current implementation covers v0.2 domain report sections: observations,
patterns, exceptions, 1-week changes, questions, insights, and gaps. Rank-heavy
under-the-hood metrics belong to CBT Analytics, not this user-facing report.
