## CBT data schema (based on LLM Wiki pattern)

### Purpose

Structured storage of CBT process:

* episodes
* thoughts
* beliefs
* experiments
* progress over time

---

## Folder structure

```
raw/                -- untouched input (journals, chat logs)

profile/
  cbt/
  index.md          -- navigation
  log.md            -- append-only changes

  cbt/episodes/         -- atomic cases
  cbt/thoughts/         -- recurring ATs
  cbt/beliefs/          -- rules + core beliefs
  cbt/experiments/      -- behavioral tests
  cbt/patterns/         -- aggregated insights (optional, later)
```

---

## Core principles

* **Episode = primary unit**
* Everything else links to episodes
* No global interpretation without multiple episode support
* Append-only mindset (no destructive edits)

---

## Entity model

### 1. Episode

```
id: ep-YYYYMMDD-N
```

```markdown
# episode-20260424-1

**Summary**: Closed job site after 3 minutes, anxiety spike

**Date**: 2026-04-24
**Context**: job search

---

## Situation
Concrete facts

## Automatic thought
Exact wording

## Emotion
- anxiety: 80

## Body
(optional)

## Behavior
what you did

## Consequence
short-term / long-term

---

## Links

- Thought: [[thought-rejection-fear]]
- Belief: [[belief-incompetent]]
- Experiment: [[experiment-apply-low-stakes]]
```

---

### 2. Thought (AT node)

```
id: thought-*
```

```markdown
# thought-rejection-fear

**Summary**: “They will reject me”

**Occurrences**:
- [[episode-20260424-1]]
- [[episode-20260420-2]]

**Belief links**:
- [[belief-incompetent]]

---

## Evidence (aggregated)
from episodes

## Counter-evidence
from episodes

## Alternatives (tested)
list of generated reframes
```

---

### 3. Belief

```markdown
# belief-incompetent

**Summary**: “I am not capable / good enough”

**Level**: core

**Supported by**:
- [[thought-rejection-fear]]

**Episodes**:
- [[episode-20260424-1]]

---

## Rules (if present)
“If I fail → I should stop”

## Strength
80/100 (track over time)
```

---

### 4. Experiment

```markdown
# experiment-apply-low-stakes

**Summary**: Send one low-risk application

**Linked belief**:
- [[belief-incompetent]]

---

## Hypothesis
“If I apply → negative reaction”

## Action
Send 1 application

## Result
(no reply)

## Learning
“Rejection is not immediate”

## Episodes
- [[episode-20260425-1]]
```

---

## Ingest workflow (CBT-specific)

When a new case appears:

1. Extract **one episode**
2. Create `episodes/episode-*`
3. Check:

   * does thought already exist?

     * yes → link
     * no → create new
4. Check belief:

   * if repeated → create/attach
5. If action taken → create experiment
6. Update:

   * `index.md`
   * `log.md`

---

## Index structure

```markdown
# CBT Index

## Episodes
- [[episode-20260424-1]] — job avoidance spike

## Thoughts
- [[thought-rejection-fear]]

## Beliefs
- [[belief-incompetent]]

## Experiments
- [[experiment-apply-low-stakes]]
```

---

## Log (append-only)

```markdown
2026-04-24
- added episode-20260424-1
- created thought-rejection-fear
- linked belief-incompetent
```

---

## Scaling rules

### Level 1 (MVP)

* episodes + thoughts
* manual linking

### Level 2

* beliefs emerge from repetition
* track intensity over time

### Level 3

* patterns page:

  * clusters of thoughts
  * behavioral loops

---

## What NOT to store

* abstract interpretations without episode refs
* “insights” without links

---

## Minimal graph

```
Episode → Thought → Belief → Behavior → Experiment → Episode
```

---

## Key property

* reversible
* traceable
* composable

Every belief must be traceable to episodes.
