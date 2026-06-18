# Pattern Payloads

## Purpose

Produce renderer-neutral pattern payloads from report-ready graph signatures.
This module keeps machine payloads separate from user-facing report text.

## Inputs

- report-ready episodes.
- graph signatures from Graph Reporting.

## Outputs

- Renderer-neutral map payload JSON explicit exports.
- Renderer-neutral hex-world layout JSON explicit exports.
- Standalone map / hex-world HTML preview exports.

## Dependencies

- Graph Reporting for derived episode signatures.
- Graph Reporting for shared pattern metrics with episode-level support
  provenance.
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

`app/map_topology.py`, `app/map_grid.py`, and `app/hex_world.py` form the
hex-world spatial compiler draft. The intended boundary is:

```text
map_payload
→ map_topology
→ hex_world
→ renderer
```

Current districts may be used as temporary region seeds, but renderers should
consume neutral hex-world regions rather than treating districts as permanent
spatial truth.

`app/map_payload_html.py` renders standalone HTML previews. During the transition
it may still consume map payload JSON directly, but the accepted direction is for
renderers to consume `hex_world` instead of inventing geography from semantic
payload entities.

`app/hex_world_html.py` renders standalone diagnostic HTML/SVG previews from
hex-world JSON. It is a visual validation surface, not the final map renderer.

Current local export commands write map payload artifacts under
`data/exports/map-payload/`. Future hex-world exports may use
`data/exports/hex-world/`. These directories are explicit tracked export
surfaces, not canonical model storage. Their JSON/HTML can contain derived
private data, so commit updates only when intentionally sharing map exports.
