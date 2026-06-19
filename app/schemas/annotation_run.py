from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.episode import Derived


class AnnotationProducerProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producer: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    generated_strategy: str = Field(min_length=1)
    generated_prompt_version: str = Field(min_length=1)
    base_annotation_run_id: str | None = None
    base_prompt_version: str | None = None


class AnnotationRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_run_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    created_at: datetime
    source_episode_count: int = Field(ge=0)
    carried_forward_count: int | None = Field(default=None, ge=0)
    generated_count: int | None = Field(default=None, ge=0)
    final_snapshot_count: int | None = Field(default=None, ge=0)
    producer_provenance: AnnotationProducerProvenance | None = None


class AnnotationRunRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(pattern=r"^episode-[0-9]{8}-[0-9]+$")
    derived: Derived
