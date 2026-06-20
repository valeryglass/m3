from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
LifeDomain = Literal[
    "work_study",
    "close_relationships_family",
    "health_body",
    "money_resources",
    "home_daily_life",
    "projects_creativity",
    "social_public",
    "unknown",
]
DomainRole = Literal["primary", "secondary"]
DomainMethod = Literal["deterministic_rule", "explicit_review"]
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
OutcomeHorizon = Literal["short_term", "long_term"]
OutcomeType = Literal[
    "relief",
    "control",
    "avoidance_cost",
    "unresolved",
    "escalation",
    "connection",
    "learning",
    "neutral_mixed",
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
NodeKind = Literal[
    "actor",
    "cognition",
    "emotion",
    "quote",
    "behavior",
    "short_outcome",
    "long_outcome",
]
NodeSourceField = Literal[
    "observed.actor",
    "observed.quote",
    "observed.automatic_thought",
    "observed.emotion",
    "observed.behavior",
    "observed.short_term_consequence",
    "observed.long_term_consequence",
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


class OutcomeAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^outcome-annotation-[0-9]+$")
    node_id: str | None = Field(
        default=None, pattern=r"^node-[0-9]+$"
    )
    horizon: OutcomeHorizon
    type: OutcomeType
    source_field: Literal[
        "observed.short_term_consequence",
        "observed.long_term_consequence",
    ]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class DomainAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^domain-annotation-[0-9]+$")
    domain: LifeDomain
    role: DomainRole
    method: DomainMethod
    source_field: Literal[
        "observed.situation",
        "observed.trigger",
        "observed.actor",
        "observed.quote",
    ]
    source_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_unknown_role(self):
        if self.domain == "unknown" and self.role != "primary":
            raise ValueError("unknown domain may only be primary")
        return self


class Observed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation: ObservedField
    trigger: ObservedField | None = None
    actor: ObservedField | None = None
    quote: ObservedField | None = None
    automatic_thought: ObservedField
    emotion: ObservedField
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
    outcome_annotations: list[OutcomeAnnotation] = Field(default_factory=list)
    domain_annotations: list[DomainAnnotation] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_domain_annotations(self):
        primary = [item for item in self.domain_annotations if item.role == "primary"]
        secondary = [item for item in self.domain_annotations if item.role == "secondary"]
        if len(primary) > 1:
            raise ValueError("domain annotations allow at most one primary")
        if len(secondary) > 1:
            raise ValueError("domain annotations allow at most one secondary")
        if secondary and not primary:
            raise ValueError("secondary domain requires a primary domain")
        if primary and primary[0].domain == "unknown" and secondary:
            raise ValueError("unknown primary domain cannot have a secondary domain")
        if primary and secondary and primary[0].domain == secondary[0].domain:
            raise ValueError("primary and secondary domains must differ")
        return self


def empty_derived_model() -> Derived:
    return Derived(
        nodes=[],
        trigger_annotations=[],
        actor_annotations=[],
        cognition_annotations=[],
        emotion_annotations=[],
        behavior_annotations=[],
        outcome_annotations=[],
        domain_annotations=[],
        relations=[],
    )


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^episode-[0-9]{8}-[0-9]+$")
    date: date
    source: str = Field(min_length=1)
    observed: Observed
    derived: Derived = Field(default_factory=empty_derived_model)
