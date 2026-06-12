# Backlog · Hex World Map Layout

## Status

Active map-layout backlog.

The first hex-world compiler slice is now integrated enough to run on the full
annotated map payload.

Validated input:

```text
data/exports/map-payload/all-annotated.json
```

Temporary validation output:

```text
/tmp/all-annotated.hex-world.json
```

Observed result:

```text
kind: hex_world
source: all-annotated
cells: 520
owned_cells: 168
regions: 12
paths: 21
fields: 6
anchors: 11
boundaries: 115
```

This confirms the first spatial compiler path:

```text
map_payload
→ map_topology
→ map_grid
→ hex_world
```

The next active slice is visual validation:

```text
hex_world
→ diagnostic HTML/SVG preview
```

The previous generalized signatures / attractors notes are preserved below as a
future semantic-compiler track. They are related, but they should not block the
spatial rendering pivot.

---

## Core Decision

Hex cells are the canonical spatial substrate for rendered map-oriented
entities.

`map_payload` remains the semantic compiler artifact. It answers:

```text
what graph-derived map entities exist?
what links/provenance do they have?
```

`hex_world` is the spatial compiler artifact. It answers:

```text
which cells exist?
which regions occupy cells?
which roads traverse cells?
which overlays affect cells?
which borders/anchors should renderers draw?
```

Renderers should draw `hex_world`; they should not invent semantic geography.

Short phrase:

```text
Payload describes what exists.
Hex world decides where/how it exists spatially.
Renderer only draws the hex world.
```

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
→ map_grid             # axial/cube-compatible grid math
→ hex_world            # canonical spatial layout
→ renderer             # HTML/SVG/canvas/isometric/etc.
```

Current validated compiler path:

```text
map_payload
→ map_topology
→ map_grid
→ hex_world
```

Next validation path:

```text
hex_world
→ diagnostic HTML/SVG preview
```

Later renderer refactor path:

```text
map_payload_html
→ consume hex_world instead of inventing layout
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
map_grid       = coordinate math and cell model
hex_world      = discrete layout artifact
renderer       = visual surface only
```

The immediate goal is not final beauty. The immediate goal is to see whether
`hex_world` is a trustworthy spatial artifact.

---

## Evidence From Full Payload Run

The compiler successfully generated a renderer-neutral `hex_world` from
`all-annotated.json`.

Summary:

```text
cells: 520
owned_cells: 168
regions: 12
paths: 21
fields: 6
anchors: 11
boundaries: 115
```

Example region placements:

```text
region:district-1   social + злость + approach       anchor h:10:4   cells 27
region:district-2   social + злость + avoid          anchor h:12:5   cells 18
region:district-4   external + злость + approach     anchor h:12:10  cells 15
```

Example path:

```text
path:district_similarity-1
region:district-1 -> region:district-2
cells=4
```

Interpretation:

```text
compiler works
renderer-neutral layout exists
visual inspection is now the next useful artifact
```

Risk:

```text
without preview, more compiler tuning is blind
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

Cell ID convention:

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

| Semantic entity  | Hex-world representation               |
| ---------------- | -------------------------------------- |
| district         | temporary `region` seed                |
| future attractor | preferred future `region` seed         |
| region           | owned cell set + anchor cell           |
| road             | ordered path of cell IDs               |
| gate             | boundary edge or border/entry cell     |
| landmark         | anchored cell                          |
| crossroads       | path intersection anchor               |
| climate          | weighted cell field overlay            |
| architecture     | internal-region sublayer / tag / field |
| destination      | external anchor / outer region         |
| pressure zone    | weighted cell field overlay            |

---

## Completed Slice · Hex World Compiler Draft

Initial modules:

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

  * compiles `map_payload → map_topology → map_grid → hex_world`.
  * assigns cells to temporary regions.
  * creates straight hex-line roads between region anchors.
  * keeps climate as separate field overlay.
  * serializes renderer-neutral spatial layout.

Validation:

```text
all-annotated map payload compiles into hex_world
```

---

## Active Next Slice · Diagnostic Hex World Renderer

Build a small diagnostic renderer before refactoring the existing map preview.

Add:

```text
app/hex_world_html.py
```

Purpose:

```text
hex_world.json
→ standalone diagnostic HTML/SVG preview
```

This renderer is not the final map renderer. It is a validation artifact.

It should answer:

```text
are regions placed sanely?
are owned cells readable?
are roads connecting expected regions?
are climate fields useful as overlays?
are boundaries signal or noise?
is label density tolerable?
```

Required visual layers:

```text
substrate hex cells
region-owned cells
region anchors
straight hex paths
climate / field overlays
optional boundaries
labels / debug summary
```

Suggested CLI:

```bash
python3 -m app.hex_world_html \
  --input /tmp/all-annotated.hex-world.json \
  --output data/exports/hex-world/all-annotated.preview.html
```

Acceptance criteria:

* given a `hex_world.json`, creates a standalone HTML file.
* HTML contains inline SVG.
* preview renders cells, owned regions, anchors, paths, and fields.
* optional boundaries render in debug mode or can be hidden.
* handles empty/missing optional sections gracefully.
* does not modify `map_payload`, episode data, annotation data, or graph
  readiness logic.
* does not refactor `map_payload_html.py` yet.

Non-goal:

```text
beautiful final map
```

Goal:

```text
visible spatial truth artifact
```

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

## Renderer Migration Policy

Do not immediately replace the existing `map_payload_html` renderer.

Migration should happen in stages:

```text
1. build hex_world compiler
2. validate hex_world with diagnostic renderer
3. compare old map_payload_html preview with hex_world preview
4. refactor or replace old renderer only after visual evidence
```

Reason:

```text
the old renderer is still useful as a comparison artifact
```

The old renderer may remain as a legacy preview until the hex-world preview is
good enough.

---

## Non-Goals For Current Slice

Do not:

* modify episode schema.
* modify annotation-run contracts.
* modify graph readiness logic.
* replace the current map payload contract.
* refactor `map_payload_html.py`.
* implement generalized signatures.
* implement attractor discovery.
* introduce clustering dependencies.
* introduce H3 or geospatial dependencies.
* implement A* pathfinding.
* build isometric / voxel rendering.
* make current districts canonical long-term map truth.
* commit generated preview HTML or generated `hex_world.json`.

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
* Should diagnostic renderer expose layer toggles, or should first version stay
  static?
* Should boundaries render by default, or only in debug mode?
* Should region labels use semantic titles, source IDs, or both?

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

Not for the first hex-world / renderer validation slices.

Do not:

* modify episode schema.
* modify map payload contract.
* replace existing district generation.
* introduce clustering dependencies.

This item exists to preserve the concept for future map/compiler evolution.
