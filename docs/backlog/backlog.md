# Codex task: add renderer-neutral map grid layer

## Goal

Add a renderer-neutral grid layer below `map_payload` and topology rendering.

Current direction:

```text
map_payload
-> map_topology
-> map_grid
-> map_payload_html
```

The goal is not to change semantic payload generation.
The goal is to introduce a discrete matrix/grid representation for future SVG,
PixiJS, isometric, voxel, and strategy-map renderers.

## Add files

```text
app/map_topology.py
app/map_grid.py
tests/test_map_topology.py
tests/test_map_grid.py
```

## Do not change

```text
app/map_payload.py
map_payload JSON contract
Makefile
generated reports
```

## Responsibilities

### `map_topology.py`

Answers:

```text
what exists spatially?
what is near what?
where are approximate continuous centers?
```

Should expose:

```python
TopologyNode
TopologyEdge
MapTopology
build_topology(payload, width=1200, height=800)
```

Initial implementation may focus only on district entities and neighbor links.

### `map_grid.py`

Answers:

```text
which cells exist?
which district owns which cells?
```

Should expose:

```python
GridCell
GridModel
build_hex_grid(topology, cell_size=28.0)
```

Initial implementation:

* deterministic hex grid
* nearest-node ownership
* ownership limited by `radius_hint`
* no rendering
* no terrain/biome assumptions

## Tests

Cover:

* `build_topology()` returns deterministic nodes for district entities
* topology ignores neighbor links with missing district IDs
* topology preserves width/height
* `build_hex_grid()` returns deterministic cells
* cells may have `owner_id`
* changing node position changes ownership
* no SVG/HTML appears in topology/grid modules

## Future notes

Do not overbuild now.

Later possible extensions:

* weighted Voronoi territories
* border cells
* district clusters as parent territories
* road pathfinding across grid
* climate overlays
* isometric projection
* voxel export

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
