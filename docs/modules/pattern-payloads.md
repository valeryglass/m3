# Pattern Payloads

## Purpose

Produce renderer-neutral pattern payloads from report-ready graph signatures.
This module keeps machine payloads separate from user-facing report text.

## Inputs

- report-ready episodes.
- graph signatures from Graph Reporting.

## Outputs

- Renderer-neutral map payload JSON explicit exports.
- Standalone map payload HTML preview exports.

## Dependencies

- Graph Reporting for derived episode signatures.
- Shared pattern metrics for loops, forks, recurrence, novelty, rarity, and
  surprise markers.
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

Current local export commands may write these artifacts under
`data/reports/map-payload/`, but that directory is an optional private export
location, not active storage.
