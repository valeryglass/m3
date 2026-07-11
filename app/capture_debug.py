from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.capture import CaptureArtifact, CaptureExtractionResult
from app.runtime_storage import atomic_write_json

SCHEMA_VERSION = "m3.capture_debug.v1"
DEFAULT_CAPTURE_DEBUG_DIR = Path("data/capture-debug")
REQUIRED_FIELDS = (
    "situation",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
)
SAFE_SUMMARY_KEYS = (
    "parser_stage",
    "response_chars",
    "json_parse_ok",
    "top_level_keys",
    "validation_error_count",
    "missing_required_count",
    "parsed_field_names",
    "missing_required_fields",
    "grounding_failure_code",
)


def capture_debug_path(root: Path, chat_id: int, capture_id: str) -> Path:
    return root / f"telegram-chat-{chat_id}" / f"debug-{capture_id}.json"


def build_provider_debug(
    artifact: CaptureArtifact,
    *,
    provider: str,
    model: str,
    prompt_version: str,
    response_text: str | None,
    failure_code: str | None = None,
    include_raw_provider_output: bool = False,
) -> dict[str, Any]:
    response_present = bool(response_text and response_text.strip())
    debug: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "capture_id": artifact.capture_id,
        "extraction_id": f"extraction-{artifact.capture_id}",
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "failure_code": failure_code,
        "response_present": response_present,
        "response_chars": len(response_text or ""),
        "json_parse_ok": False,
        "top_level_keys": [],
        "validation_error_paths": [],
        "validation_error_messages": [],
        "validation_error_count": 0,
        "parsed_field_names": [],
        "missing_required_fields": list(REQUIRED_FIELDS),
        "missing_required_count": len(REQUIRED_FIELDS),
        "parser_stage": "missing_output" if not response_present else "json_parse",
    }
    if include_raw_provider_output and response_text is not None:
        debug["raw_provider_output"] = response_text
    if not response_present:
        return debug

    try:
        parsed = json.loads(response_text or "")
    except json.JSONDecodeError as exc:
        debug["json_error"] = str(exc)
        return debug
    if isinstance(parsed, dict):
        debug["json_parse_ok"] = True
        debug["top_level_keys"] = sorted(str(key) for key in parsed)
        debug["parser_stage"] = "schema_validation"
    else:
        debug["parser_stage"] = "schema_validation"
        debug["validation_error_messages"] = ["provider JSON output must be an object"]
        debug["validation_error_count"] = 1
        return debug

    try:
        result = CaptureExtractionResult.model_validate(parsed)
    except ValidationError as exc:
        errors = exc.errors()
        debug["validation_error_paths"] = [
            ".".join(str(part) for part in error.get("loc", ())) for error in errors
        ]
        debug["validation_error_messages"] = [
            str(error.get("msg", "")) for error in errors
        ]
        debug["validation_error_count"] = len(errors)
        return debug

    parsed_fields = _present_fields(result)
    missing_required = [
        field_name for field_name in REQUIRED_FIELDS if field_name not in parsed_fields
    ]
    debug["parser_stage"] = "parsed"
    debug["parsed_field_names"] = parsed_fields
    debug["missing_required_fields"] = missing_required
    debug["missing_required_count"] = len(missing_required)
    return debug


def record_provider_debug(
    root: Path | None,
    artifact: CaptureArtifact,
    *,
    provider: str,
    model: str,
    prompt_version: str,
    response_text: str | None,
    failure_code: str | None = None,
    include_raw_provider_output: bool = False,
) -> Path | None:
    if root is None:
        return None
    debug = build_provider_debug(
        artifact,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        response_text=response_text,
        failure_code=failure_code,
        include_raw_provider_output=include_raw_provider_output,
    )
    return write_capture_debug(root, artifact, debug)


def record_grounding_failure_debug(
    root: Path | None,
    artifact: CaptureArtifact,
    *,
    result: CaptureExtractionResult,
    failure_code: str,
) -> Path | None:
    if root is None:
        return None
    path = capture_debug_path(root, artifact.chat_id, artifact.capture_id)
    debug = _read_existing_debug(path)
    parsed_fields = _present_fields(result)
    missing_required = [
        field_name for field_name in REQUIRED_FIELDS if field_name not in parsed_fields
    ]
    debug.update(
        {
            "parser_stage": "grounding",
            "grounding_failure_code": failure_code,
            "parsed_field_names": parsed_fields,
            "missing_required_fields": missing_required,
            "missing_required_count": len(missing_required),
        }
    )
    return write_capture_debug(root, artifact, debug)


def write_capture_debug(
    root: Path,
    artifact: CaptureArtifact,
    debug: dict[str, Any],
) -> Path | None:
    try:
        path = capture_debug_path(root, artifact.chat_id, artifact.capture_id)
        atomic_write_json(path, debug, sort_keys=True)
        return path
    except Exception:
        return None


def capture_debug_safe_summary(
    root: Path | None,
    artifact: CaptureArtifact,
) -> dict[str, Any]:
    if root is None:
        return {}
    path = capture_debug_path(root, artifact.chat_id, artifact.capture_id)
    if not path.exists():
        return {}
    debug = _read_existing_debug(path)
    summary = {key: debug[key] for key in SAFE_SUMMARY_KEYS if key in debug}
    summary["debug_path"] = path.as_posix()
    return summary


def _read_existing_debug(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _present_fields(result: CaptureExtractionResult) -> list[str]:
    return sorted(
        field_name
        for field_name, field_value in result
        if field_value is not None and field_value.value.strip()
    )
