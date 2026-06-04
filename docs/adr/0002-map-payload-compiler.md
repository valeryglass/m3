# 0002: Map Payload Compiler

## Decision

Add a renderer-neutral map payload JSON artifact under Pattern Payloads. The
compiler builds one-source map payloads from graph signatures and writes private
runtime JSON artifacts under `data/reports/map-payload/`.

## Why

The project needs a stable semantic map layer before committing to any concrete
renderer. A JSON compiler artifact keeps graph-derived entities, links,
clusters, similarity, and provenance separate from SVG, canvas, voxel, or other
presentation choices.

## Consequences

Positive:

- map semantics can be tested without visual rendering
- multiple renderers can consume the same payload contract
- map generation remains downstream of graph/report-ready episodes

Negative:

- map payload shape becomes another interface to keep coherent
- preview renderers can drift from the compiler if not tested together

## Policy

The map compiler must not change episode schema or graph readiness logic.
Generated map artifacts remain private runtime outputs under `data/reports/`.
Renderers must consume the map payload instead of re-deriving graph semantics.
