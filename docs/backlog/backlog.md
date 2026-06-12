# Backlog

## ALARA Docker runtime for Telegram bot

Add a minimal local Docker/Compose runtime capsule for `app.telegram_bot`.
Use `pyproject.toml` as the dependency source, keep `data/` writable, mount
`config/`, `model/`, and `roles/` read-only, and keep the change runtime-only:
no schema, graph, report, annotation, storage contract, or bot behavior changes.

## Codex task: pivot map rendering to hex world

## Goal

Introduce a renderer-neutral `hex_world` layer between `map_payload` and visual
renderers.

Target direction:

```text
map_payload
-> map_topology
-> hex_world
-> renderer
```

`map_grid` owns axial/cube-compatible hex math. `hex_world` owns the derived
spatial artifact. Renderers should draw `hex_world` instead of inventing layout
from semantic payload entities.

The goal is not to change semantic payload generation.
The goal is to introduce a discrete hex-cell representation for future HTML/SVG,
PixiJS, isometric, voxel, and strategy-map renderers.

## Add / repair files

```text
app/map_topology.py
app/map_grid.py
app/hex_world.py
tests/test_map_topology.py
tests/test_map_grid.py
tests/test_hex_world.py
```

## Do not change

```text
model/episode.schema.json
annotation-run schema
app/graph_report.py readiness logic
map_payload JSON contract
Makefile
generated reports
```

## Responsibilities

### `map_topology.py`

Answers:

```text
what semantic entities become spatial candidates?
what is near what?
where are approximate continuous seed centers?
```

Should expose:

```python
TopologyEntity
TopologyRelation
MapTopology
build_topology(payload, width=1200, height=800)
```

Initial implementation may map current district entities to neutral `region`
seeds. This should preserve `source_entity_type` and `source_entity_id` so the
future attractor compiler can replace districts without changing renderers.

### `map_grid.py`

Answers:

```text
which cells exist?
how do axial/cube coordinates work?
which cells are neighbors?
what is the straight hex line between two cells?
```

Should expose:

```python
HexCoord
GridCell
GridModel
build_hex_grid(topology, cell_size=28.0)
hex_neighbors(coord)
hex_distance(a, b)
hex_line(a, b)
pixel_to_axial(x, y, cell_size=...)
axial_to_pixel(q, r, cell_size=...)
```

Initial implementation:

* deterministic pointy-top axial hex grid.
* cube-compatible `s = -q - r` math.
* temporary nearest-region ownership.
* no rendering.
* no terrain/biome assumptions.

### `hex_world.py`

Answers:

```text
which regions own cells?
which paths traverse cells?
which overlays weight cells?
which anchors and boundaries exist?
```

Should expose:

```python
HexWorld
RegionPlacement
HexPath
HexField
HexAnchor
HexBoundary
build_hex_world(payload, width=1200, height=800, cell_size=28.0)
hex_world_to_dict(world)
write_hex_world(payload, output_path, ...)
```

Initial implementation:

* compiles `map_payload -> map_topology -> hex_world`.
* treats current districts as temporary region seeds.
* creates straight hex-line paths for region neighbor relations.
* keeps climate as a separate top overlay field.
* does not lock historical map positions.

## Tests

Cover:

* `build_topology()` returns deterministic region seeds for district entities.
* topology ignores neighbor links with missing region IDs.
* topology preserves width/height.
* `build_hex_grid()` returns deterministic pointy-top axial cells.
* cell IDs round-trip through `parse_hex_id()`.
* `hex_neighbors()`, `hex_distance()`, and `hex_line()` behave predictably.
* `build_hex_world()` returns cells, regions, and straight paths.
* current districts appear only as `source_entity_type`, not as renderer truth.
* climate appears as field overlay, not ownership.
* no SVG/HTML appears in topology/grid/hex-world modules.

## Future notes

Do not overbuild now.

Later possible extensions:

* attractor-backed region seeds.
* generalized-signature region seeds.
* weighted Voronoi territories.
* true boundary edges / vertices.
* gate placement on cell edges.
* road pathfinding across grid.
* climate / pressure interpolation.
* isometric projection.
* voxel export.

## External methodology backlog

Tracked external-methodology drafts also preserve non-code work for later.
These are backlog candidates, not implementation requirements for the
topology/grid task.

### External architecture

* create an external architecture diagram
* describe deployment and hosting
* write a short security review summary
* define integration story for external partners
* align terminology with the future product name

### Data governance

* define production retention periods
* review access control
* document backup lifecycle details
* list external processors
* define user export format
* define deletion verification process
* outline incident response procedure

### Beta validation

Turn `H01` through `H08` from
`docs/external-methodology/custdev-ba-po/micro-hypotheses_ru.md` into future
beta validation tasks.

Do not treat those hypotheses as implementation work. They belong to product
validation and custdev follow-up.
