# 0006: Hex World Spatial Substrate

## Status

Accepted as draft direction.

## Context

The current map pipeline has a semantic payload compiler and an HTML preview
renderer:

```text
graph/report-ready episodes
→ map_payload
→ map_payload_html
```

`map_payload` is the correct semantic boundary, but the current HTML preview has
too much layout responsibility. It draws map geography directly from semantic
payload entities and therefore mixes:

```text
semantic interpretation
spatial layout
visual rendering
```

The project needs a renderer-neutral spatial layer before map previews grow into
SVG, canvas, PixiJS, isometric, voxel, or strategy-map renderers.

There is also a domain caution: current `district` entities are produced from a
fixed repeated-signature shape. They are useful bootstrap entities, but they
should not become permanent spatial truth. Future graph-truth regions may come
from attractors, generalized signatures, graph communities, or other recurrent
pattern families.

## Decision

Introduce `hex_world` as the canonical spatial representation for rendered
map-oriented entities.

The target pipeline becomes:

```text
episodes / annotation-runs
→ graph_report
→ map_payload          # semantic map entities
→ map_topology         # spatial candidates and relations
→ hex_world            # canonical hex-cell layout
→ renderer             # visual surface only
```

The core boundary is:

```text
Payload describes what exists.
Hex world decides where/how it exists spatially.
Renderer only draws the hex world.
```

## Hex Policy

Use pointy-top axial hex coordinates for storage:

```text
q, r
```

and cube-compatible math for algorithms:

```text
s = -q - r
```

Cell IDs use the draft convention:

```text
h:<q>:<r>
```

The hex world may expose cells, regions, paths, fields, anchors, and boundaries.

## Region Policy

Do not canonize current districts as the final spatial source of truth.

Current behavior may be:

```text
payload district
→ temporary topology region seed
→ owned hex cells
```

Future behavior may be:

```text
attractor / generalized-signature cluster / graph community
→ topology region seed
→ owned hex cells
```

Renderers and grid logic must depend on neutral `region` placements, not on the
current district compiler.

## Layer Policy

Draft layer order:

```text
0. substrate grid
1. region ownership layer
2. architecture / internal-region layer
3. road / relation path layer
4. gate / landmark / crossroads anchor layer
5. climate / pressure field overlay layer
6. labels / debug layer
```

Important distinctions:

* regions own cells.
* climate is a weighted overlay field, not territory.
* roads are ordered cell paths.
* gates should eventually live on borders or cell edges.
* landmarks and crossroads are anchors.

## Road Policy

For the first slice, roads may be straight hex lines between region anchor cells.

Do not implement A* pathfinding yet.
Do not introduce terrain costs yet.
Do not block roads by ownership yet.

The renderer-facing artifact should already be an ordered `cell_ids` path so the
implementation can later swap straight-line paths for pathfinding without
changing renderers.

## Persistence Policy

The hex world is derived and generative.

Do not:

* write hex coordinates into episode JSON.
* write hex coordinates into annotation-runs.
* treat layout as active storage.
* preserve historical map positions as a compatibility promise.

Allowed explicit export surface:

```text
data/exports/hex-world/
```

These exports are rebuildable derived artifacts and may contain private derived
data.

## Consequences

Positive:

* renderers stop inventing geography.
* future renderers can share the same spatial artifact.
* current districts can be used without becoming long-term map truth.
* attractor/generalized-signature work can evolve separately from rendering.
* roads, borders, gates, climate, and regions get clearer spatial contracts.

Negative:

* there is one more derived artifact to keep coherent.
* existing HTML preview must eventually be refactored to consume `hex_world`.
* early region ownership will be heuristic until better graph-truth region seeds
  exist.

## Non-Goals

This decision does not:

* modify episode schema.
* modify annotation-run schema.
* modify graph readiness gates.
* replace the map payload contract.
* implement generalized signatures.
* implement attractor discovery.
* add geospatial/H3 dependencies.
* require locked layout persistence.
