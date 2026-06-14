# 0007: Input Funnels And Episode Drafts

## Decision

Separate user input surfaces, normalized capture artifacts, provisional episode
drafts, reusable gap hydration, and persisted observed episodes.

The system may accept multiple input forms, including Telegram text, Telegram
voice notes, uploaded audio files, and future structured forms. These inputs do
not create separate episode types. They are normalized into input artifacts,
then converted into provisional episode drafts. Only confirmed drafts may become
saved observed episodes conforming to the canonical episode schema.

```text
input != episode
transcript != episode
draft != episode
episode != annotation
annotation != graph
graph != report
report != source of truth
```

## Why

The current Telegram capture flow is organized around a classic multi-question
text sequence. That flow is usable, but it makes the capture strategy look like
the architecture boundary.

Audio and one-take capture create a stronger need for a stable intake pipeline:
users should be able to speak or write naturally, while the system still
protects the observed episode contract and asks only for missing evidence.

This decision keeps the episode schema sacred while allowing new capture views:

```text
Telegram text / voice / audio / future form
  -> input funnel
  -> input artifact
  -> episode draft
  -> gap hydration
  -> confirmation
  -> observed episode
```

## Consequences

Positive:

- input modes can evolve without changing the episode schema
- the 10-question flow becomes one draft-filling strategy, not the whole intake
  architecture
- gap hydration can be reused across text, voice, one-take, three-block, and
  future capture views
- raw audio and transcripts can be treated as support evidence, not canonical
  source records
- confirmation becomes the explicit boundary before persistence

Negative:

- capture code needs an additional draft boundary
- runtime session state may need to distinguish raw input, draft state, and
  confirmed episode fields
- tests must cover incomplete drafts and gap selection, not only completed
  episode persistence

## Policy

Input artifacts are pre-episode capture records. They may include raw text,
transcripts, Telegram file metadata, duration, MIME type, and source message
metadata.

Episode drafts are provisional. They may contain partial observed fields,
missing-field lists, weak-field notes, source quotes, and confidence notes.
Drafts are not source-of-truth records.

Gap hydration is a reusable draft operation. It receives a partial draft and
selects the smallest useful next question needed to improve or complete it.

Only user-confirmed drafts may be persisted as observed episode files. Persisted
episode files remain observed source artifacts and must validate against the
canonical episode schema.

Raw audio is not persisted by default. Storing raw audio requires a separate
explicit decision about retention, privacy, and user expectations.

## Non-goals

- no audio-specific episode schema
- no graph/report changes
- no diagnostic inference changes
- no voice emotion recognition
- no prosody analysis
- no long-form audio processing commitment
- no public or community audio features
