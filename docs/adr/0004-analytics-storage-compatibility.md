# 0004: Analytics Storage Compatibility Layer

## Decision

Separate the project concepts of observed episodes, selected derived
annotations, computed graph views, and rendered exports.

The first implementation kept existing episode files valid, including embedded
`derived`, and added annotation-run loading as an additional analytics source.

After the strip-derived migration, observed-only episode persistence became the
default. Episode files are observed source artifacts. Annotation-runs are
durable derived graph artifacts. Analytics loaders hydrate runtime
`Episode.derived` from the selected annotation-run or compatibility fallback.

```text
episode != annotation
annotation != graph
graph != report
report != source of truth
```

## Why

The alpha data model stored observed facts and derived graph interpretation in
the same episode file. That was convenient, but made it unclear which artifacts
were canonical and which could be regenerated.

Separating the concepts allows new annotation versions without rewriting
observed episode records, while keeping existing alpha flows working.

## Consequences

Positive:

- observed episodes can remain stable source artifacts
- annotation runs can be versioned and selected for analytics
- `GraphReport` is clarified as a computed graph view
- reports stay disposable on-demand projections
- map payloads stay explicit generated exports

Negative:

- compatibility loading must support old and new layouts during migration
- existing `Episode` objects still carry selected derived annotations for
  current code paths
- embedded derived remains readable for legacy compatibility

## Policy

Do not treat generated reports, payloads, map payloads, or graph Markdown as
source-of-truth data. They are projections from episodes plus selected
annotations. Persistent report files are optional debug/export snapshots; map
payload JSON and map HTML are explicit export artifacts.
