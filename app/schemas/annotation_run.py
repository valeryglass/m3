from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.episode import Derived


class AnnotationRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_run_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    created_at: datetime
    source_episode_count: int = Field(ge=0)


class AnnotationRunRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(pattern=r"^episode-[0-9]{8}-[0-9]+$")
    derived: Derived
