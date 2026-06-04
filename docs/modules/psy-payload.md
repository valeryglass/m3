# Psy Payload

## Purpose

Produce domain-boxed loop, pattern, frequency, fork, outcome, and one-week
change metrics from report-ready episodes.

## Inputs

- report-ready episodes.
- graph signatures from Graph Reporting.

## Outputs

- Markdown payload reports under `data/reports/psy-payload/`.
- Renderer-neutral map payload JSON artifacts under `data/reports/map-payload/`.
- Standalone map payload HTML previews under `data/reports/map-payload/`.

## Dependencies

- Graph Reporting for derived episode signatures.
- Readiness gates for report inclusion.

## Interfaces

- `report_to_payload`

## Lifecycle

`experimental`

The payload is technical domain analytics, not diagnosis, profile
interpretation, or therapeutic advice.

`app/map_payload.py` derives one-source map compiler payload JSON from graph
signatures for future SVG, voxel, canvas, or other renderers. The payload
contains semantic entities and links only; renderers derive their own geometry.

`app/map_payload_html.py` renders standalone HTML previews from map payload JSON.
It is a preview surface over the payload contract, not a second compiler.
