## Extension module: PROFILE layer (separate from CBT-core)

**Goal:** aggregate cross-episode signals without polluting core CBT entities.

---

## Folder

```id="9g0m2l"
profile/
```

---

## Design rules

* read-only aggregation from:

  * episodes
  * thoughts
  * beliefs
* no direct “truth claims”
* every statement must link to ≥2 episodes
* confidence + frequency required

---

## Entity: profile page

```markdown id="z8t4p1"
# profile-user

**Summary**: aggregated behavioral + cognitive tendencies

**Last updated**: YYYY-MM-DD

---

## Cognitive patterns

### fear-of-rejection
- thoughts:
  - [[thought-rejection-fear]]
- episodes:
  - [[episode-20260424-1]]
  - [[episode-20260420-2]]
- frequency: 6
- confidence: medium

---

## Behavioral patterns

### avoidance-job-search
- behavior: closing job sites quickly
- episodes:
  - [[episode-20260424-1]]
  - [[episode-20260418-1]]
- trigger:
  - [[thought-rejection-fear]]

---

## Emotional baseline

| emotion | avg | peak |
|--------|-----|------|
| anxiety | 55 | 85 |

(source: episodes)

---

## Belief landscape

- [[belief-incompetent]] (strength: 80 → 65)
- [[belief-judged-by-others]]

---

## Writing signals (auto-writing / logs)

### recurring phrases
- “I could but I don’t want”
- “no point”

### tone markers
- detached
- analytical
- low affect spikes

(source: raw + episodes)

---

## Contradictions

- claims “doesn’t care” vs repeated anxiety spikes

---

## Open hypotheses

- avoidance driven by evaluation fear
- possible mismatch: interest vs perceived competence

(no validation yet)

---

## Related

- [[belief-incompetent]]
- [[thought-rejection-fear]]
```

---

## Derived entities (optional modules)

### 1. pattern nodes

```id="l7d3sv"
profile/cbt/patterns/
```

```markdown id="9w2k0a"
# pattern-avoidance-loop

**Summary**: trigger → anxiety → avoidance → relief

**Chain**:
- [[thought-rejection-fear]]
→ anxiety
→ close tab
→ relief

**Episodes**:
- [[episode-20260424-1]]
- [[episode-20260418-1]]
```

---

### 2. traits (lightweight, non-diagnostic)

```markdown id="q6h2yx"
# trait-high-avoidance-threshold

**Evidence**:
- [[episode-20260424-1]]
- [[episode-20260418-1]]

**Description**:
action drops when uncertainty > threshold

**Confidence**: low
```

---

### 3. signals (from raw text)

```id="l4j9kq"
profile/cbt/signals/
```

```markdown id="2yq0n8"
# signal-low-agency-language

**Examples**:
- “can’t”
- “no point”
- “later”

**Occurrences**:
- raw logs
- episodes

**Linked patterns**:
- [[pattern-avoidance-loop]]
```

---

## Ingest extension workflow

When new episode added:

1. update episode
2. update thought node
3. check pattern:

   * exists → increment frequency
   * no → create candidate
4. update profile:

   * increment counters
   * update averages
5. append to log

---

## Minimal aggregation logic

```id="n5e2y4"
if thought appears ≥3 times:
  promote → pattern

if pattern appears ≥5 times:
  link → profile

if belief linked ≥3 patterns:
  increase confidence
```

---

## Constraints

* no diagnosis
* no MBTI / typology injection
* no conclusions without traceability
* keep hypotheses separate from facts
