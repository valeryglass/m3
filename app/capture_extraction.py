from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from pydantic import ValidationError

from app.capture_debug import (
    capture_debug_safe_summary,
    record_grounding_failure_debug,
)
from app.episode_drafts import EpisodeDraft
from app.journal import JournalLog, journal_event, record_journal_event
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
    def __init__(
        self,
        code: ExtractionFailureCode,
        message: str | None = None,
        *,
        partial_result: "PartialCaptureExtractionResult | None" = None,
    ):
        super().__init__(message or code)
        self.code = code
        self.partial_result = partial_result


class CaptureExtractionProvider(Protocol):
    provider_name: str
    model: str
    prompt_version: str

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        """Return a schema-shaped extraction proposal for one capture artifact."""


class UnavailableCaptureExtractionProvider:
    provider_name = "unavailable"
    prompt_version = PROMPT_VERSION
    _m3_run_inline_for_tests = True

    def __init__(self, model: str = "unconfigured") -> None:
        self.model = model or "unconfigured"

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        raise CaptureExtractionError("provider_unavailable")


@dataclass(frozen=True)
class CaptureExtractionOutcome:
    extraction: CaptureExtraction
    path: Path
    draft: EpisodeDraft | None
    partial: bool = False
    partial_fields: tuple[str, ...] = ()
    rejected_fields: dict[str, str] = field(default_factory=dict)
    missing_required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class PartialCaptureExtractionResult:
    observed: dict[str, dict[str, str]]
    accepted_fields: tuple[str, ...]
    rejected_fields: dict[str, str]
    missing_required_fields: tuple[str, ...]

    @property
    def has_observed(self) -> bool:
        return bool(self.observed)

    def draft(self) -> EpisodeDraft:
        return EpisodeDraft(observed=self.observed)


def validate_grounded_extraction(
    artifact: CaptureArtifact,
    result: CaptureExtractionResult,
) -> CaptureExtractionResult:
    for field_name, field_value in result:
        if field_value is None:
            continue
        _validate_grounded_field(artifact, field_name, field_value)

    for field_name in REQUIRED_FIELDS:
        field_value = getattr(result, field_name)
        if field_value is None or not field_value.value.strip():
            raise CaptureExtractionError(
                "insufficient_evidence",
                f"required observed field is missing: {field_name}",
            )
    return result


def partial_extraction_from_mapping(
    artifact: CaptureArtifact,
    payload: Mapping[str, Any],
) -> PartialCaptureExtractionResult:
    observed: dict[str, dict[str, str]] = {}
    accepted_fields: list[str] = []
    rejected_fields: dict[str, str] = {}
    for field_name in CaptureExtractionResult.model_fields:
        raw_field = payload.get(field_name)
        if raw_field is None:
            continue
        try:
            field_value = ExtractedObservedField.model_validate(raw_field)
            _validate_grounded_field(artifact, field_name, field_value)
        except CaptureExtractionError as exc:
            rejected_fields[field_name] = exc.code
            continue
        except (ValidationError, ValueError, TypeError):
            rejected_fields[field_name] = "invalid_schema"
            continue
        observed[field_name] = field_value.observed_field().model_dump()
        accepted_fields.append(field_name)
    missing_required = tuple(
        field_name for field_name in REQUIRED_FIELDS if field_name not in observed
    )
    return PartialCaptureExtractionResult(
        observed=observed,
        accepted_fields=tuple(accepted_fields),
        rejected_fields=rejected_fields,
        missing_required_fields=missing_required,
    )


def fallback_partial_draft_from_capture(
    artifact: CaptureArtifact,
) -> PartialCaptureExtractionResult:
    observed: dict[str, dict[str, str]] = {}
    if artifact.mode == "one_take_text":
        text = _piece_text(artifact, "one_take_text")
        if text:
            observed["situation"] = {"value": text, "source_quote": text}
    elif artifact.mode == "one_take_audio":
        text = _piece_text(artifact, "transcript")
        if text:
            observed["situation"] = {"value": text, "source_quote": text}
    elif artifact.mode == "three_block":
        for field_name, role in (
            ("situation", "outside_context"),
            ("automatic_thought", "inner_context"),
            ("behavior", "response_outcome"),
        ):
            text = _piece_text(artifact, role)
            if text:
                observed[field_name] = {"value": text, "source_quote": text}
    missing_required = tuple(
        field_name for field_name in REQUIRED_FIELDS if field_name not in observed
    )
    return PartialCaptureExtractionResult(
        observed=observed,
        accepted_fields=tuple(observed),
        rejected_fields={},
        missing_required_fields=missing_required,
    )


def _validate_grounded_field(
    artifact: CaptureArtifact,
    field_name: str,
    field_value: ExtractedObservedField,
) -> None:
    pieces = {piece.role: piece.text for piece in artifact.pieces}
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


def _piece_text(artifact: CaptureArtifact, role: str) -> str | None:
    for piece in artifact.pieces:
        if piece.role == role and piece.text.strip():
            return piece.text
    return None


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
    journal_log: JournalLog | Path | None = None,
) -> CaptureExtractionOutcome:
    _record_capture_event(
        journal_log,
        artifact=artifact,
        provider="deterministic.direct",
        model="classic-10q-projection",
        prompt_version="classic-10q-v1",
        stage="started",
        event_type="capture_extraction.started",
    )
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
    _record_capture_event(
        journal_log,
        artifact=artifact,
        extraction=extraction,
        extraction_path=path,
        provider=extraction.provider,
        model=extraction.model,
        prompt_version=extraction.prompt_version,
        stage="succeeded",
        event_type="capture_extraction.succeeded",
    )
    return CaptureExtractionOutcome(extraction=extraction, path=path, draft=draft)


def run_capture_extraction(
    artifact: CaptureArtifact,
    provider: CaptureExtractionProvider,
    output_root: Path,
    *,
    created_at: datetime | None = None,
    journal_log: JournalLog | Path | None = None,
    allow_partial_draft: bool = False,
) -> CaptureExtractionOutcome:
    timestamp = created_at or datetime.now(timezone.utc)
    _record_capture_event(
        journal_log,
        artifact=artifact,
        provider=provider.provider_name,
        model=provider.model,
        prompt_version=provider.prompt_version,
        stage="started",
        event_type="capture_extraction.started",
    )
    try:
        proposed = provider.extract(artifact)
        try:
            result = validate_grounded_extraction(artifact, proposed)
        except CaptureExtractionError as exc:
            exc.partial_result = partial_extraction_from_mapping(
                artifact,
                proposed.model_dump(mode="python"),
            )
            record_grounding_failure_debug(
                getattr(provider, "capture_debug_dir", None),
                artifact,
                result=proposed,
                failure_code=exc.code,
            )
            raise
    except CaptureExtractionError as exc:
        extraction = _failed_extraction(artifact, provider, timestamp, exc.code)
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        _record_capture_event(
            journal_log,
            artifact=artifact,
            extraction=extraction,
            extraction_path=path,
            provider=provider.provider_name,
            model=provider.model,
            prompt_version=provider.prompt_version,
            stage="failed",
            event_type="capture_extraction.failed",
            failure_code=exc.code,
            debug_summary=capture_debug_safe_summary(
                getattr(provider, "capture_debug_dir", None),
                artifact,
            ),
        )
        return _failed_outcome(
            artifact,
            extraction,
            path,
            exc.partial_result,
            allow_partial_draft=allow_partial_draft,
        )
    except (ValidationError, json.JSONDecodeError, ValueError):
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "invalid_schema",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        _record_capture_event(
            journal_log,
            artifact=artifact,
            extraction=extraction,
            extraction_path=path,
            provider=provider.provider_name,
            model=provider.model,
            prompt_version=provider.prompt_version,
            stage="failed",
            event_type="capture_extraction.failed",
            failure_code="invalid_schema",
            debug_summary=capture_debug_safe_summary(
                getattr(provider, "capture_debug_dir", None),
                artifact,
            ),
        )
        return _failed_outcome(
            artifact,
            extraction,
            path,
            None,
            allow_partial_draft=allow_partial_draft,
        )
    except TimeoutError:
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "provider_timeout",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        _record_capture_event(
            journal_log,
            artifact=artifact,
            extraction=extraction,
            extraction_path=path,
            provider=provider.provider_name,
            model=provider.model,
            prompt_version=provider.prompt_version,
            stage="failed",
            event_type="capture_extraction.failed",
            failure_code="provider_timeout",
            debug_summary=capture_debug_safe_summary(
                getattr(provider, "capture_debug_dir", None),
                artifact,
            ),
        )
        return _failed_outcome(
            artifact,
            extraction,
            path,
            None,
            allow_partial_draft=allow_partial_draft,
        )
    except Exception:
        extraction = _failed_extraction(
            artifact,
            provider,
            timestamp,
            "provider_error",
        )
        path = save_capture_extraction(output_root, artifact.chat_id, extraction)
        _record_capture_event(
            journal_log,
            artifact=artifact,
            extraction=extraction,
            extraction_path=path,
            provider=provider.provider_name,
            model=provider.model,
            prompt_version=provider.prompt_version,
            stage="failed",
            event_type="capture_extraction.failed",
            failure_code="provider_error",
            debug_summary=capture_debug_safe_summary(
                getattr(provider, "capture_debug_dir", None),
                artifact,
            ),
        )
        return _failed_outcome(
            artifact,
            extraction,
            path,
            None,
            allow_partial_draft=allow_partial_draft,
        )

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
    _record_capture_event(
        journal_log,
        artifact=artifact,
        extraction=extraction,
        extraction_path=path,
        provider=provider.provider_name,
        model=provider.model,
        prompt_version=provider.prompt_version,
        stage="succeeded",
        event_type="capture_extraction.succeeded",
        debug_summary=capture_debug_safe_summary(
            getattr(provider, "capture_debug_dir", None),
            artifact,
        ),
    )
    return CaptureExtractionOutcome(
        extraction=extraction,
        path=path,
        draft=EpisodeDraft(observed=result.observed_dict()),
    )


def _failed_outcome(
    artifact: CaptureArtifact,
    extraction: CaptureExtraction,
    path: Path,
    partial_result: PartialCaptureExtractionResult | None,
    *,
    allow_partial_draft: bool,
) -> CaptureExtractionOutcome:
    if not allow_partial_draft or artifact.mode == "classic_10q":
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)
    partial = partial_result
    if partial is None or not partial.has_observed:
        partial = fallback_partial_draft_from_capture(artifact)
    if not partial.has_observed:
        return CaptureExtractionOutcome(extraction=extraction, path=path, draft=None)
    return CaptureExtractionOutcome(
        extraction=extraction,
        path=path,
        draft=partial.draft(),
        partial=True,
        partial_fields=partial.accepted_fields,
        rejected_fields=partial.rejected_fields,
        missing_required_fields=partial.missing_required_fields,
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


def _record_capture_event(
    journal_log: JournalLog | Path | None,
    *,
    artifact: CaptureArtifact,
    provider: str,
    model: str,
    prompt_version: str,
    stage: str,
    event_type: str,
    extraction: CaptureExtraction | None = None,
    extraction_path: Path | None = None,
    failure_code: ExtractionFailureCode | None = None,
    debug_summary: dict[str, Any] | None = None,
) -> None:
    refs: dict[str, str] = {"capture_id": artifact.capture_id}
    if extraction is not None:
        refs["extraction_id"] = extraction.extraction_id
    if extraction_path is not None:
        refs["extraction_path"] = extraction_path.as_posix()
    details = {
        "mode": artifact.mode,
        "media_kind": artifact.media_kind,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
    }
    if debug_summary:
        details.update(debug_summary)
    record_journal_event(
        journal_log,
        journal_event(
            component="capture_extraction",
            event_type=event_type,
            stage=stage,
            level="error" if stage == "failed" else "info",
            failure_code=failure_code,
            refs=refs,
            counts={
                "capture_piece_count": len(artifact.pieces),
                "capture_text_chars": sum(len(piece.text) for piece in artifact.pieces),
            },
            details=details,
        ),
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
