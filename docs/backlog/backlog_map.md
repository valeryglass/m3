# Backlog · Hex World Map Layout

## Status

Active design backlog.

This file now tracks the map-layout pivot:

```text
map_payload
→ hex_world
→ renderer
```

The previous generalized signatures / attractors notes are preserved below as a
future semantic-compiler track. They are related, but they should not block the
spatial rendering pivot.

---

## Core Decision Candidate

Hex cells become the canonical spatial substrate for rendered map-oriented
entities.

`map_payload` remains the semantic compiler artifact. It answers:

```text
what graph-derived map entities exist?
what links/provenance do they have?
```

`hex_world` becomes the spatial compiler artifact. It answers:

```text
which cells exist?
which regions occupy cells?
which roads traverse cells?
which overlays affect cells?
which borders/anchors should renderers draw?
```

Renderers should draw `hex_world`; they should not invent semantic geography.

---

## Desired Pipeline

Current rough state:

```text
episodes / annotation-runs
→ graph_report
→ map_payload
→ map_payload_html
```

Target spatial pipeline:

```text
episodes / annotation-runs
→ graph_report
→ map_payload          # semantic map entities
→ map_topology         # abstract spatial candidates
→ hex_world            # canonical spatial layout
→ renderer             # HTML/SVG/canvas/isometric/etc.
```

Short phrase:

```text
Payload describes what exists.
Hex world decides where/how it exists spatially.
Renderer only draws the hex world.
```

---

## Why This Pivot Exists

Current HTML preview rendering has too much layout authority. It effectively
compiles visual geography directly from `map_payload`.

That makes the renderer do three jobs at once:

```text
semantic interpretation
spatial layout
visual drawing
```

The pivot separates them:

```text
map_payload    = semantic artifact
map_topology   = spatial candidates and relations
hex_world      = discrete layout artifact
renderer       = visual surface only
```

---

## District / Attractor Caution

Do not make current `district = repeated fixed signature` the long-term spatial
truth.

Current districts may be used as temporary region seeds, but the spatial layer
should use neutral language:

```text
region = spatialized graph-truth pattern area
```

For now:

```text
current district payload entity
→ temporary region seed
→ owned hex cells
```

Later:

```text
attractor / generalized signature cluster
→ region seed
→ owned hex cells
```

This keeps future attractor work from being blocked by the current rigid
district compiler.

---

## Hex Model

Use axial coordinates for storage and cube-compatible math for algorithms.

```text
stored: q, r
computed: s = -q - r
```

Cell ID convention draft:

```text
h:<q>:<r>
```

Example:

```json
{
  "id": "h:2:-1",
  "q": 2,
  "r": -1,
  "s": -1
}
```

Initial orientation:

```text
pointy-top hexes
```

Rationale:

* axial/cube math keeps neighbors, distances, rings, line drawing, and pathing
  simple.
* map-oriented entities need not only cells, but also borders, edges, vertices,
  neighbors, corners, and paths.

---

## Layer Stack

Draft rendering order:

```text
0. substrate grid
1. region ownership layer
2. architecture / internal-region layer
3. road / relation path layer
4. gate / landmark / crossroads anchor layer
5. climate / pressure field overlay layer
6. labels / debug layer
```

Important separation:

```text
region owns cells
climate weights cells
roads traverse cells
gates sit on borders / entry cells
landmarks anchor to cells
crossroads sit on path intersections
```

Climate should not own territory. It is a top overlay field.

---

## Entity Mapping Draft

| Semantic entity | Hex-world representation |
| --- | --- |
| district | temporary `region` seed |
| future attractor | preferred future `region` seed |
| region | owned cell set + anchor cell |
| road | ordered path of cell IDs |
| gate | boundary edge or border/entry cell |
| landmark | anchored cell |
| crossroads | path intersection anchor |
| climate | weighted cell field overlay |
| architecture | internal-region sublayer / tag / field |
| destination | external anchor / outer region |
| pressure zone | weighted cell field overlay |

---

## First Buildable Slice

Replace the broken draft files with importable modules:

```text
app/map_topology.py
app/map_grid.py
app/hex_world.py
```

Initial behavior:

* `map_topology.py`
  * extracts current district-like payload entities as neutral region seeds.
  * keeps `source_entity_type` and `source_entity_id` so districts are not
    canonized as the only future region source.
  * extracts neighbor links as topology relations.

* `map_grid.py`
  * owns axial/cube-compatible hex math.
  * creates deterministic hex cells.
  * exposes neighbors, distance, and straight hex-line helpers.

* `hex_world.py`
  * compiles `map_payload → map_topology → hex_world`.
  * assigns cells to temporary regions.
  * creates straight hex-line roads between region anchors.
  * keeps climate as separate field overlay.

---

## Road Policy For Now

Use the simplest smart road model:

```text
road = straight hex line between anchor cells
```

Do not implement A* yet.
Do not add terrain cost yet.
Do not block roads on ownership yet.

Later, straight lines can be replaced by pathfinding without changing the
renderer contract:

```text
path_cell_ids remain the renderer-facing artifact
```

---

## Generative Layout Policy

The layout is purely generative for now.

Do not lock old map positions.
Do not persist user-facing promises about old districts.
Do not write cell IDs into episodes or annotation-runs.

Allowed explicit export:

```text
data/exports/hex-world/
```

This export is derived, rebuildable, and not source-of-truth storage.

---

## Non-Goals For This Slice

Do not:

* modify episode schema.
* modify annotation-run contracts.
* modify graph readiness logic.
* replace the current map payload contract.
* implement generalized signatures.
* implement attractor discovery.
* introduce clustering dependencies.
* introduce H3 or geospatial dependencies.
* implement A* pathfinding.
* build isometric / voxel rendering.
* make current districts canonical long-term map truth.

---

## Open Questions

* What graph-truth signal should eventually become the preferred region seed:
  attractor, generalized signature cluster, graph community, or something else?
* Can regions overlap, or must each cell have one owner and many overlays?
* Should roads prefer neutral cells, border cells, or direct center lines?
* Should gates be modeled first as border cells or true cell-edge records?
* How should rare but high-salience signatures appear: landmark, pressure zone,
  isolated region, or annotation prompt?
* When climate and architecture conflict visually, which layer wins?

---

# Preserved Concept · Generalized Signatures and Attractors

## Status

Deferred semantic-compiler evolution.

Current map pipeline may continue using:

```text
district = repeated signature
```

for early payload generation.

No implementation required now.
This section preserves the concept for future compiler evolution.

---

## Problem

Current district generation assumes a fixed signature shape:

```text
trigger + emotion + behavior
```

This is useful for bootstrapping but likely too restrictive.

Many meaningful recurring patterns exist across arbitrary dimensions:

```text
social + anger
evaluation + avoid
social + evaluation + anger
external + shame
joy + approach
physical + shame + approach
```

The future system should not assume a single canonical signature structure.

---

## Desired Direction

Move from:

```text
episode
→ fixed signature
→ district
```

towards:

```text
episode
→ multidimensional combinations
→ recurrent signatures
→ attractors
→ map entities
```

---

## Conceptual Model

### Atomic Feature

Smallest analytical element.

Examples:

```text
social
external
anger
shame
avoid
approach
evaluation
prediction
```

---

### Signature

Repeated combination of arbitrary features.

Examples:

```text
social + anger
anger + avoid
social + evaluation + anger
```

A signature should not require a fixed field structure.

---

### Attractor

Stable family of related signatures.

Examples:

```text
Attractor: Social Conflict

social + anger
social + anger + avoid
social + anger + freeze
social + shame + avoid
```

An attractor is not necessarily a single signature.

---

### Map Entity

Visual representation derived from attractors and other patterns.

Examples:

```text
district
road
landmark
gate
pressure zone
crossroads
```

---

## Future Research

Investigate:

```text
frequent itemsets
association rules
pattern mining
community detection
signature clustering
hypergraph motifs
```

Potentially derive attractors from recurring multidimensional feature
combinations instead of predefined signature schemas.

---

## Potential Pipeline Evolution

Semantic evolution:

```text
episodes
→ feature combinations
→ recurrent signatures
→ attractors
→ map payload
```

Spatial evolution:

```text
map payload
→ topology
→ hex world
→ renderer
```

These tracks are compatible but should remain separate until attractor discovery
has enough evidence.

---

## Open Questions

* What minimum support defines a signature?
* What similarity metric groups signatures into an attractor?
* Can attractors overlap?
* Should districts represent attractors or attractor regions?
* How should rare but high-salience signatures appear on the map?
* How should multidimensional signatures interact with climate, architecture,
  and road generation?

---

## Non-Goals

Not for the first hex-world slice.

Do not:

* modify episode schema.
* modify map payload contract.
* replace existing district generation.
* introduce clustering dependencies.

This item exists to preserve the concept for future map/compiler evolution.
