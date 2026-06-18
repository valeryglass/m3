from __future__ import annotations

from app.schemas.episode import (
    ActorAnnotation,
    BehaviorAnnotation,
    BehaviorType,
    CognitionAnnotation,
    CognitionKind,
    Derived,
    EmotionAnnotation,
    EmotionLabel,
    Episode,
    GraphRelation,
    Node,
    OutcomeAnnotation,
    OutcomeType,
    TriggerAnnotation,
    TriggerType,
)

CONFIDENCE = 0.7


def annotate_episode(episode: Episode) -> Derived:
    """Build deterministic derived annotations from observed episode fields.

    This is the minimal local producer for annotation-runs. It does not call an
    LLM, mutate the input episode, read files, or write files.
    """
    builder = _DerivedBuilder()
    observed = episode.observed

    trigger_node_id = None
    if observed.trigger is not None and observed.trigger.value.strip():
        trigger_node_id = builder.add_node(
            kind="quote",
            text=observed.trigger.value,
            source_field="observed.quote",
            source_quote=observed.trigger.source_quote,
        )
        builder.trigger_annotations.append(
            TriggerAnnotation(
                id=builder.next_id("trigger-annotation"),
                node_id=trigger_node_id,
                type=_trigger_type(observed.trigger.value),
                source_field="observed.trigger",
                source_quote=observed.trigger.source_quote,
                confidence=CONFIDENCE,
            )
        )

    if observed.actor is not None and observed.actor.value.strip():
        actor_node_id = builder.add_node(
            kind="actor",
            text=observed.actor.value,
            source_field="observed.actor",
            source_quote=observed.actor.source_quote,
        )
        builder.actor_annotations.append(
            ActorAnnotation(
                id=builder.next_id("actor-annotation"),
                node_id=actor_node_id,
                role="unknown",
                label=observed.actor.value,
                source_field="observed.actor",
                source_quote=observed.actor.source_quote,
                confidence=CONFIDENCE,
            )
        )

    cognition_node_id = builder.add_node(
        kind="cognition",
        text=observed.automatic_thought.value,
        source_field="observed.automatic_thought",
        source_quote=observed.automatic_thought.source_quote,
    )
    builder.cognition_annotations.append(
        CognitionAnnotation(
            id=builder.next_id("cognition-annotation"),
            node_id=cognition_node_id,
            text=observed.automatic_thought.value,
            kind=_cognition_kind(observed.automatic_thought.value),
            source_field="observed.automatic_thought",
            source_quote=observed.automatic_thought.source_quote,
            confidence=CONFIDENCE,
        )
    )

    emotion_node_id = builder.add_node(
        kind="emotion",
        text=observed.emotion.value,
        source_field="observed.emotion",
        source_quote=observed.emotion.source_quote,
    )
    emotion_label = _emotion_label(observed.emotion.value)
    valence, arousal = _emotion_coordinates(emotion_label)
    builder.emotion_annotations.append(
        EmotionAnnotation(
            id=builder.next_id("emotion-annotation"),
            node_id=emotion_node_id,
            label=emotion_label,
            intensity=None,
            valence=valence,
            arousal=arousal,
            source_field="observed.emotion",
            source_quote=observed.emotion.source_quote,
            confidence=CONFIDENCE,
        )
    )

    behavior_node_id = builder.add_node(
        kind="behavior",
        text=observed.behavior.value,
        source_field="observed.behavior",
        source_quote=observed.behavior.source_quote,
    )
    builder.behavior_annotations.append(
        BehaviorAnnotation(
            id=builder.next_id("behavior-annotation"),
            node_id=behavior_node_id,
            type=_behavior_type(observed.behavior.value),
            source_field="observed.behavior",
            source_quote=observed.behavior.source_quote,
            confidence=CONFIDENCE,
        )
    )

    short_node_id = builder.add_node(
        kind="short_outcome",
        text=observed.short_term_consequence.value,
        source_field="observed.short_term_consequence",
        source_quote=observed.short_term_consequence.source_quote,
    )
    builder.outcome_annotations.append(
        OutcomeAnnotation(
            id=builder.next_id("outcome-annotation"),
            node_id=short_node_id,
            horizon="short_term",
            type=_outcome_type(observed.short_term_consequence.value),
            source_field="observed.short_term_consequence",
            source_quote=observed.short_term_consequence.source_quote,
            confidence=CONFIDENCE,
        )
    )

    long_node_id = builder.add_node(
        kind="long_outcome",
        text=observed.long_term_consequence.value,
        source_field="observed.long_term_consequence",
        source_quote=observed.long_term_consequence.source_quote,
    )
    builder.outcome_annotations.append(
        OutcomeAnnotation(
            id=builder.next_id("outcome-annotation"),
            node_id=long_node_id,
            horizon="long_term",
            type=_outcome_type(observed.long_term_consequence.value),
            source_field="observed.long_term_consequence",
            source_quote=observed.long_term_consequence.source_quote,
            confidence=CONFIDENCE,
        )
    )

    if trigger_node_id is not None:
        builder.add_relation(
            type="elicits",
            from_ref=trigger_node_id,
            to_ref=emotion_node_id,
            source_field="observed.trigger",
            source_quote=observed.trigger.source_quote,  # type: ignore[union-attr]
        )
    builder.add_relation(
        type="elicits",
        from_ref=cognition_node_id,
        to_ref=emotion_node_id,
        source_field="observed.automatic_thought",
        source_quote=observed.automatic_thought.source_quote,
    )
    builder.add_relation(
        type="expressed_as",
        from_ref=emotion_node_id,
        to_ref=behavior_node_id,
        source_field="observed.behavior",
        source_quote=observed.behavior.source_quote,
    )
    builder.add_relation(
        type="leads_to",
        from_ref=behavior_node_id,
        to_ref=short_node_id,
        source_field="observed.short_term_consequence",
        source_quote=observed.short_term_consequence.source_quote,
    )
    builder.add_relation(
        type="reinforces",
        from_ref=short_node_id,
        to_ref=long_node_id,
        source_field="observed.long_term_consequence",
        source_quote=observed.long_term_consequence.source_quote,
    )

    return builder.derived()


class _DerivedBuilder:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.trigger_annotations: list[TriggerAnnotation] = []
        self.actor_annotations: list[ActorAnnotation] = []
        self.cognition_annotations: list[CognitionAnnotation] = []
        self.emotion_annotations: list[EmotionAnnotation] = []
        self.behavior_annotations: list[BehaviorAnnotation] = []
        self.outcome_annotations: list[OutcomeAnnotation] = []
        self.relations: list[GraphRelation] = []
        self._counters: dict[str, int] = {}

    def next_id(self, prefix: str) -> str:
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return f"{prefix}-{value}"

    def add_node(self, *, kind, text, source_field, source_quote) -> str:
        node_id = self.next_id("node")
        self.nodes.append(
            Node(
                id=node_id,
                node_origin="observed",
                kind=kind,
                text=text,
                source_field=source_field,
                source_quote=source_quote,
                confidence=CONFIDENCE,
            )
        )
        return node_id

    def add_relation(self, *, type, from_ref, to_ref, source_field, source_quote) -> None:
        self.relations.append(
            GraphRelation(
                id=self.next_id("relation"),
                type=type,
                from_ref=from_ref,
                to_ref=to_ref,
                source_field=source_field,
                source_quote=source_quote,
                confidence=CONFIDENCE,
            )
        )

    def derived(self) -> Derived:
        return Derived(
            nodes=self.nodes,
            trigger_annotations=self.trigger_annotations,
            actor_annotations=self.actor_annotations,
            cognition_annotations=self.cognition_annotations,
            emotion_annotations=self.emotion_annotations,
            behavior_annotations=self.behavior_annotations,
            outcome_annotations=self.outcome_annotations,
            relations=self.relations,
        )


def _trigger_type(text: str) -> TriggerType:
    lowered = text.lower()
    if any(word in lowered for word in ("люд", "человек", "коллег", "друг", "чат")):
        return "social"
    if any(word in lowered for word in ("тело", "боль", "устал", "сон")):
        return "physical"
    if any(word in lowered for word in ("вспом", "памят")):
        return "memory"
    if any(word in lowered for word in ("подум", "мысл")):
        return "thought"
    return "external"


def _cognition_kind(text: str) -> CognitionKind:
    lowered = text.lower()
    if "?" in text:
        return "question"
    if any(word in lowered for word in ("долж", "нужно", "надо")):
        return "rule"
    if any(word in lowered for word in ("буд", "случ", "получ")):
        return "prediction"
    if any(word in lowered for word in ("знач", "смысл")):
        return "meaning"
    return "evaluation"


def _emotion_label(text: str) -> EmotionLabel:
    lowered = text.lower()
    labels: tuple[EmotionLabel, ...] = (
        "нейтраль/мешанные",
        "любовь/тепло",
        "радость",
        "отвращение",
        "стыд",
        "грусть",
        "злость",
        "страх",
    )
    for label in labels:
        if label in lowered:
            return label
    return "нейтраль/мешанные"


def _emotion_coordinates(label: EmotionLabel) -> tuple[float, float]:
    if label in {"радость", "любовь/тепло"}:
        return 0.7, 0.5
    if label == "нейтраль/мешанные":
        return 0.0, 0.3
    if label in {"злость", "страх"}:
        return -0.7, 0.8
    return -0.6, 0.5


def _behavior_type(text: str) -> BehaviorType:
    lowered = text.lower()
    if any(word in lowered for word in ("избег", "дистан", "уш", "молч")):
        return "avoid"
    if any(word in lowered for word in ("замер", "ступор")):
        return "freeze"
    if any(word in lowered for word in ("атак", "дав", "спор")):
        return "attack"
    if any(word in lowered for word in ("соглас", "подстро")):
        return "submit"
    return "approach"


def _outcome_type(text: str) -> OutcomeType:
    lowered = text.lower()
    if any(word in lowered for word in ("облегч", "легче")):
        return "relief"
    if any(word in lowered for word in ("контрол")):
        return "control"
    if any(word in lowered for word in ("избег", "потер", "цена")):
        return "avoidance_cost"
    if any(word in lowered for word in ("связ", "контакт", "близ")):
        return "connection"
    if any(word in lowered for word in ("понял", "науч", "вывод")):
        return "learning"
    if any(word in lowered for word in ("хуже", "эскал")):
        return "escalation"
    return "neutral_mixed"
