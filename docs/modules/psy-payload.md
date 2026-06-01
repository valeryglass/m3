# Psy Payload

## Purpose

Produce domain-boxed loop, pattern, frequency, fork, outcome, and one-week
change metrics from report-ready episodes.

## Inputs

- report-ready episodes.
- graph signatures from Graph Reporting.

## Outputs

- Markdown payload reports under `data/reports/psy-payload/`.

## Dependencies

- Graph Reporting for derived episode signatures.
- Readiness gates for report inclusion.

## Interfaces

- `report_to_payload`

## Lifecycle

`experimental`

The payload is technical domain analytics, not diagnosis, profile
interpretation, or therapeutic advice.
