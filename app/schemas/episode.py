from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EmotionLabel = Literal[
    "нейтраль/мешанные",
    "любовь/тепло",
    "радость",
    "отвращение",
    "стыд",
    "грусть",
    "злость",
    "страх",
]
TriggerType = Literal["external", "internal", "social", "physical", "memory", "thought"]
ActorRole = Literal["self", "other", "group", "institution", "unknown"]
CognitionKind = Literal[
    "evaluation",
    "prediction",
    "rule",
    "meaning",
    "memory",
    "image",
    "urge",
    "question",
]
BehaviorType = Literal[
    "approach",
    "avoid",
    "freeze",
    "attack",
    "submit",
    "compensate",
    "distract",
]
NodeOrigin = Literal["observed", "support"]
RelationType = Literal[
    "belongs_to",
    "derived_from",
    "precedes",
    "leads_to",
    "co_occurs_with",
    "elicits",
    "expressed_as",
    "reinforces",
    "contrasts_with",
    "acts_in",
    "occurs_in",
]
ObservedRefField = Literal[
    "observed.situation",
    "observed.trigger",
    "observed.actor",
    "observed.quote",
    "observed.behavior",
    "observed.short_term_consequence",
    "observed.long_term_consequence",
    "observed.automatic_thought",
    "observed.emotion",
    "observed.physical",
]
NodeKind = Literal["actor", "cognition", "emotion", "quote", "behavior"]
NodeSourceField = Literal[
    "observed.actor",
    "observed.quote",
    "observed.automatic_thought",
    "observed.emotion",
    "observed.emotion.items",
    "observed.emotion.free_text",
    "observed.behavior",
]


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^node-[0-9]+$")
    node_origin: NodeOrigin = "observed"
    kind: NodeKind
    text: str = Field(min_length=1)
    source_field: NodeSourceField
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class GraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^relation-[0-9]+$")
    type: RelationType
    from_ref: str = Field(
        pattern=(
            r"^(episode|observed\.(situation|trigger|actor|quote|behavior|"
            r"short_term_consequence|long_term_consequence|automatic_thought|"
            r"emotion|physical)|node-[0-9]+)$"
        )
    )
    to_ref: str = Field(
        pattern=(
            r"^(episode|observed\.(situation|trigger|actor|quote|behavior|"
            r"short_term_consequence|long_term_consequence|automatic_thought|"
            r"emotion|physical)|node-[0-9]+)$"
        )
    )
    source_field: ObservedRefField
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ObservedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    source_quote: str


class EmotionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: EmotionLabel
    intensity: float = Field(ge=0.0, le=1.0)
    source_quote: str = Field(min_length=1)


class EmotionField(ObservedField):
    items: list[EmotionItem] | None = None
    free_text: str | None = None


class TriggerAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^trigger-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    type: TriggerType
    source_field: Literal[
        "observed.trigger",
        "observed.situation",
        "observed.automatic_thought",
    ]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ActorAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^actor-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    role: ActorRole
    label: str = Field(min_length=1)
    source_field: Literal["observed.actor", "observed.quote", "observed.situation"]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class CognitionAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^cognition-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    text: str = Field(min_length=1)
    kind: CognitionKind
    source_field: Literal["observed.automatic_thought"]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class EmotionAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^emotion-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    label: EmotionLabel
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    valence: float = Field(ge=-1.0, le=1.0)
    arousal: float = Field(ge=0.0, le=1.0)
    source_field: Literal[
        "observed.emotion",
        "observed.emotion.items",
        "observed.emotion.free_text",
    ]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class BehaviorAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^behavior-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    type: BehaviorType
    source_field: Literal["observed.behavior"]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class Observed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation: ObservedField
    trigger: ObservedField | None = None
    actor: ObservedField | None = None
    quote: ObservedField | None = None
    automatic_thought: ObservedField
    emotion: EmotionField
    behavior: ObservedField
    physical: ObservedField
    short_term_consequence: ObservedField
    long_term_consequence: ObservedField


class Derived(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[Node]
    trigger_annotations: list[TriggerAnnotation]
    actor_annotations: list[ActorAnnotation]
    cognition_annotations: list[CognitionAnnotation]
    emotion_annotations: list[EmotionAnnotation]
    behavior_annotations: list[BehaviorAnnotation]
    relations: list[GraphRelation] = Field(default_factory=list)


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^episode-[0-9]{8}-[0-9]+$")
    date: date
    source: str = Field(min_length=1)
    observed: Observed
    derived: Derived
