from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Confidence = Literal["low", "medium", "high"]
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


class AtomicThought(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^atomic-thought-[0-9]+$")
    text: str = Field(min_length=1)
    source_field: Literal["observed.automatic_thought"]
    source_quote: str = Field(min_length=1)
    confidence: Confidence


class CognitiveDistortion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    source_atomic_thought: str = Field(pattern=r"^atomic-thought-[0-9]+$")
    source_field: Literal["observed.automatic_thought"]
    source_quote: str = Field(min_length=1)
    confidence: Confidence


class Observed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation: ObservedField
    trigger: ObservedField | None = None
    actors: ObservedField | None = None
    speech: ObservedField | None = None
    automatic_thought: ObservedField
    emotion: EmotionField
    body: ObservedField
    behavior: ObservedField
    short_term_consequence: ObservedField
    long_term_consequence: ObservedField


class Derived(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atomic_thoughts: list[AtomicThought]
    cognitive_distortions: list[CognitiveDistortion]


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^episode-[0-9]{8}-[0-9]+$")
    date: date
    source: str = Field(min_length=1)
    observed: Observed
    derived: Derived
