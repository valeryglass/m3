# 0002: Map Payload Compiler

## Decision

Add a renderer-neutral map payload JSON artifact under Pattern Payloads. The
compiler builds one-source map payloads from graph signatures as explicit
technical exports for map experiments.

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

The map compiler must not change episode schema or graph readiness logic. Map
payload JSON and map HTML are explicit export artifacts, not active report
storage or source-of-truth data. Renderers must consume the map payload instead
of re-deriving graph semantics.
