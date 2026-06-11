# Backlog · Generalized Signatures and Attractors

## Status

Deferred.

Current map pipeline may continue using:

```text
district = repeated signature
```

for v0.1.

No implementation required now.
This file is a concept holder for future compiler evolution.

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

Current:

```text
episodes
→ graph signatures
→ map payload
```

Future:

```text
episodes
→ feature combinations
→ recurrent signatures
→ attractors
→ map payload
→ topology
→ grid
→ renderer
```

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

Not for v0.1.

Do not:

* modify episode schema
* modify map payload contract
* replace existing district generation
* introduce clustering dependencies

This item exists to preserve the concept for future map/compiler evolution.
