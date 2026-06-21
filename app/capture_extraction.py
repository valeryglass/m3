from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.episode_drafts import EpisodeDraft
from app.schemas.capture import (
    CaptureArtifact,
    CaptureExtraction,
    CaptureExtractionResult,
    CapturePieceRole,
    ExtractedObservedField,
    ExtractionFailureCode,
)


PROMPT_VERSION = "capture-observed-v1"
REQUIRED_FIELDS = (
    "situation",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
)
THREE_BLOCK_FIELD_ROLES: dict[str, frozenset[str]] = {
    "situation": frozenset({"outside_context"}),
    "trigger": frozenset({"outside_context"}),
    "actor": frozenset({"outside_context"}),
    "quote": frozenset({"outside_context"}),
    "automatic_thought": frozenset({"inner_context"}),
    "emotion": frozenset({"inner_context"}),
    "physical": frozenset({"inner_context"}),
    "behavior": frozenset({"response_outcome"}),
    "short_term_consequence": frozenset({"response_outcome"}),
    "long_term_consequence": frozenset({"response_outcome"}),
}


class CaptureExtractionError(RuntimeError):
    def __init__(self, code: ExtractionFailureCode, message: str | None = None):
        super().__init__(message or code)
        self.code = code


class CaptureExtractionProvider(Protocol):
    provider_name: str
    model: str
    prompt_version: str

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        """Return a schema-shaped extraction proposal for one capture artifact."""


class UnavailableCaptureExtractionProvider:
    provider_name = "unavailable"
    prompt_version = PROMPT_VERSION

    def __init__(self, model: str = "unconfigured") -> None:
        self.model = model or "unconfigured"

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        raise CaptureExtractionError("provider_unavailable")


@dataclass(frozen=True)
class CaptureExtractionOutcome:
    extraction: CaptureExtraction
    path: Path
    draft: EpisodeDraft | None


def validate_grounded_extraction(
    artifact: CaptureArtifact,
    result: CaptureExtractionResult,
) -> CaptureExtractionResult:
    pieces = {piece.role: piece.text for piece in artifact.pieces}
    for field_name, field_value in result:
        if field_value is None:
            continue
        piece_text = pieces.get(field_value.source_piece_role)
        if piece_text is None:
            raise CaptureExtractionError(
                "invalid_piece_role",
                f"{field_name} references an unavailable capture piece",
            )
        if field_value.source_quote not in piece_text:
            raise CaptureExtractionError(
                "invalid_source_quote",
                f"{field_name} source quote is not exact capture evidence",
            )
        if artifact.mode == "three_block":
            allowed = THREE_BLOCK_FIELD_ROLES[field_name]
            if field_value.source_piece_role not in allowed:
                raise CaptureExtractionError(
                    "invalid_piece_role",
                    f"{field_name} uses the wrong three-block evidence group",
                )
        elif artifact.mode == "one_take_text":
            if field_value.source_piece_role != "one_take_text":
                raise CaptureExtractionError("invalid_piece_role")
        elif artifact.mode == "one_take_audio":
            if field_value.source_piece_role != "transcript":
                raise CaptureExtractionError("invalid_piece_role")
        elif field_value.source_piece_role != field_name:
            raise CaptureExtractionError("invalid_piece_role")

    for field_name in REQUIRED_FIELDS:
        field_value = getattr(result, field_name)
        if field_value is None or not field_value.value.strip():
            raise CaptureExtractionError(
                "insufficient_evidence",
                f"required observed field is missing: {field_name}",
            )
    return result


def extract_classic_10q_draft(artifact: CaptureArtifact) -> EpisodeDraft:
    if artifact.mode != "classic_10q":
        raise ValueError("classic extraction requires classic_10q artifact")
    observed = {
        piece.role: {
            "value": piece.text,
            "source_quote": piece.text,
        }
        for piece in artifact.pieces
    }
    missing = [field for field in REQUIRED_FIELDS if field not in observed]
    if missing:
        raise CaptureExtractionError("insufficient_evidence")
    return EpisodeDraft(observed=observed)


def project_classic_10q(
    artifact: CaptureArtifact,
    output_root: Path,
    *,
    created_at: datetime | None = None,
) -> CaptureExtractionOutcome:
    draft = extract_classic_10q_draft(artifact)
    fields = {
        piece.role: ExtractedObservedField(
            value=piece.text,
            source_quote=piece.text,
            source_piece_role=piece.role,
            confidence=1.0,
        )
        for piece in artifact.pieces
    }
    result = CaptureExtractionResult(
        **{
            field_name: fields.get(field_name)
            for field_name in CaptureExtractionResult.model_fields
        }
    )
    timestamp = created_at or datetime.now(timezone.utc)
    extraction = CaptureExtraction(
        extraction_id=f"extraction-{artifact.capture_id}",
        capture_id=artifact.capture_id,
        created_at=timestamp,
        status="succeeded",
        provider="deterministic.direct",
        model="classic-10q-projection",
        prompt_version="classic-10q-v1",
        result=result,
    )
    path = save_capture_extraction(output_root, artifact.chat_id, extraction)
    return CaptureExtractionOutcome(extraction=extraction, path=path, draft=draft)


def run_capture_extraction(
    artifact: CaptureArtifact,
    provider: CaptureExtractionProvider,
    output_root: Path,
    *,
    created_at: datetime | None = None,
) -> CaptureExtractionOutcome:
    timestamp = created_at or datetime.now(timezone.utc)
    try:
        proposed = provider.extract(artifact)
        result = validate_grounded_extraction(artifact, proposed)
    except CaptureExtractionError as exc:
        extraction = _failed_extraction(artifact, provider, timestamp, exc.code)
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)
    except (ValidationError, json.JSONDecodeError, ValueError):
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "invalid_schema",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)
    except TimeoutError:
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "provider_timeout",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)
    except Exception:
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "provider_error",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)

    extraction = CaptureExtraction(
        extraction_id=f"extraction-{artifact.capture_id}",
        capture_id=artifact.capture_id,
        created_at=timestamp,
        status="succeeded",
        provider=provider.provider_name,
        model=provider.model,
        prompt_version=provider.prompt_version,
        result=result,
    )
    path = save_capture_extraction(output_root, artifact.chat_id, extraction)
    return CaptureExtractionOutcome(
        extraction=extraction,
        path=path,
        draft=EpisodeDraft(observed=result.observed_dict()),
    )


def extraction_path(root: Path, chat_id: int, capture_id: str) -> Path:
    return root / f"telegram-chat-{chat_id}" / f"extraction-{capture_id}.json"


def save_capture_extraction(
    root: Path,
    chat_id: int,
    extraction: CaptureExtraction,
) -> Path:
    path = extraction_path(root, chat_id, extraction.capture_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            extraction.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def load_capture_extraction(path: Path) -> CaptureExtraction:
    return CaptureExtraction.model_validate_json(path.read_text(encoding="utf-8"))


def link_capture_extraction_to_episode(
    path: Path,
    episode_id: str,
) -> CaptureExtraction:
    extraction = load_capture_extraction(path)
    linked = extraction.model_copy(update={"episode_id": episode_id})
    save_capture_extraction(path.parents[1], _chat_id_from_path(path), linked)
    return linked


def _failed_extraction(
    artifact: CaptureArtifact,
    provider: CaptureExtractionProvider,
    created_at: datetime,
    code: ExtractionFailureCode,
) -> CaptureExtraction:
    return CaptureExtraction(
        extraction_id=f"extraction-{artifact.capture_id}",
        capture_id=artifact.capture_id,
        created_at=created_at,
        status="failed",
        provider=provider.provider_name,
        model=provider.model,
        prompt_version=provider.prompt_version,
        failure_code=code,
    )


def _chat_id_from_path(path: Path) -> int:
    prefix = "telegram-chat-"
    name = path.parent.name
    if not name.startswith(prefix):
        raise ValueError("capture extraction path has no chat id")
    return int(name[len(prefix):])


def extraction_result_schema() -> dict:
    return CaptureExtractionResult.model_json_schema()


def source_piece(
    role: CapturePieceRole,
    value: str,
    quote: str,
    *,
    confidence: float = 1.0,
) -> ExtractedObservedField:
    return ExtractedObservedField(
        value=value,
        source_quote=quote,
        source_piece_role=role,
        confidence=confidence,
    )
