# Pattern Payloads

## Purpose

Project shared insight analytics and report-ready graph entities into
renderer-neutral map and spatial payloads. This module keeps machine payloads
separate from user-facing report text.

## Inputs

- report-ready episodes.
- shared `InsightPayload` analytics.
- spatial projections derived from the same `InsightPayload`.
- graph signatures when map-specific entities, topology, and provenance require
  report-ready episode material.

## Outputs

- Renderer-neutral map payload JSON explicit exports.
- Renderer-neutral hex-world layout JSON explicit exports.
- Standalone map / hex-world HTML preview exports.

## Dependencies

- Insight Payloads for shared deterministic motifs, forks, contrasts,
  counterexamples, outcomes, and support provenance.
- Graph Reporting for map-specific graph entities and episode provenance.
- Readiness gates for report inclusion.

## Interfaces

- `report_to_payload`

## Lifecycle

`experimental`

The payload is technical domain analytics, not diagnosis, profile
interpretation, or therapeutic advice.

`app/spatial_payload.py` projects the shared insight payload into paths, fork
markers, and outcome links without choosing coordinates or visual layout.

LLM report interpretation is currently separate from map projection and emits no
map-focus hints. This pause does not change `MapPayload`, coordinates, or
deterministic map semantics.

`app/map_payload.py` derives one-source map compiler payload JSON from graph
signatures for future SVG, voxel, canvas, or other renderers. It embeds the
shared insight and spatial payloads under `analytics` while retaining
map-specific semantic entities, links, topology, and provenance. Renderers
derive their own geometry.

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

Map payload file export requires an explicitly selected annotation-run, full
row coverage, and payload eligibility for every episode in the selected source.
It fails before writing when coverage or readiness is incomplete.
