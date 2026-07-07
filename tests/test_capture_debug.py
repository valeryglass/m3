import json
from datetime import datetime, timezone

from app.capture_artifacts import build_capture_artifact
from app.capture_debug import (
    build_provider_debug,
    capture_debug_safe_summary,
    capture_debug_path,
    record_grounding_failure_debug,
    record_provider_debug,
)
from app.capture_extraction import source_piece
from app.schemas.capture import CaptureExtractionResult


NOW = datetime(2026, 6, 21, tzinfo=timezone.utc)


def test_capture_debug_writes_safe_metadata_without_raw_output_by_default(tmp_path):
    artifact = _artifact()
    path = record_provider_debug(
        tmp_path,
        artifact,
        provider="deepseek.chat",
        model="deepseek-v4-flash",
        prompt_version="capture-observed-v1",
        response_text=json.dumps(_payload()),
    )

    assert path == capture_debug_path(tmp_path, 42, artifact.capture_id)
    data = _read_json(path)
    assert data["schema_version"] == "m3.capture_debug.v1"
    assert data["response_present"] is True
    assert data["json_parse_ok"] is True
    assert data["parser_stage"] == "parsed"
    assert data["parsed_field_names"] == [
        "automatic_thought",
        "behavior",
        "emotion",
        "long_term_consequence",
        "physical",
        "short_term_consequence",
        "situation",
    ]
    assert "raw_provider_output" not in data


def test_capture_debug_raw_provider_output_requires_toggle():
    debug = build_provider_debug(
        _artifact(),
        provider="deepseek.chat",
        model="deepseek-v4-flash",
        prompt_version="capture-observed-v1",
        response_text='{"private": "output"}',
        include_raw_provider_output=True,
    )

    assert debug["raw_provider_output"] == '{"private": "output"}'


def test_capture_debug_records_invalid_json():
    debug = build_provider_debug(
        _artifact(),
        provider="deepseek.chat",
        model="deepseek-v4-flash",
        prompt_version="capture-observed-v1",
        response_text="{",
        failure_code="invalid_schema",
    )

    assert debug["failure_code"] == "invalid_schema"
    assert debug["parser_stage"] == "json_parse"
    assert debug["json_parse_ok"] is False
    assert debug["response_chars"] == 1
    assert "json_error" in debug


def test_capture_debug_records_schema_error_paths():
    debug = build_provider_debug(
        _artifact(),
        provider="deepseek.chat",
        model="deepseek-v4-flash",
        prompt_version="capture-observed-v1",
        response_text=json.dumps({"situation": {"value": "x"}}),
        failure_code="invalid_schema",
    )

    assert debug["json_parse_ok"] is True
    assert debug["parser_stage"] == "schema_validation"
    assert "automatic_thought" in debug["validation_error_paths"]
    assert debug["validation_error_count"] > 0


def test_capture_debug_records_grounding_failure(tmp_path):
    artifact = _artifact()
    result = CaptureExtractionResult(
        situation=source_piece("one_take_text", "normalized", "missing quote"),
        trigger=None,
        actor=None,
        quote=None,
        automatic_thought=source_piece("one_take_text", "normalized", "same evidence"),
        emotion=source_piece("one_take_text", "normalized", "same evidence"),
        behavior=source_piece("one_take_text", "normalized", "same evidence"),
        physical=source_piece("one_take_text", "normalized", "same evidence"),
        short_term_consequence=source_piece("one_take_text", "normalized", "same evidence"),
        long_term_consequence=source_piece("one_take_text", "normalized", "same evidence"),
    )

    record_provider_debug(
        tmp_path,
        artifact,
        provider="deepseek.chat",
        model="deepseek-v4-flash",
        prompt_version="capture-observed-v1",
        response_text=json.dumps(_payload()),
    )
    path = record_grounding_failure_debug(
        tmp_path,
        artifact,
        result=result,
        failure_code="invalid_source_quote",
    )

    data = _read_json(path)
    assert data["parser_stage"] == "grounding"
    assert data["grounding_failure_code"] == "invalid_source_quote"
    summary = capture_debug_safe_summary(tmp_path, artifact)
    assert summary["grounding_failure_code"] == "invalid_source_quote"
    assert "raw_provider_output" not in summary


def _artifact():
    return build_capture_artifact(
        chat_id=42,
        mode="one_take_text",
        media_kind="text",
        pieces=(("one_take_text", "same evidence"),),
        created_at=NOW,
    )


def _payload():
    field = {
        "value": "normalized",
        "source_quote": "same evidence",
        "source_piece_role": "one_take_text",
        "confidence": 0.9,
    }
    return {
        "situation": field,
        "trigger": None,
        "actor": None,
        "quote": None,
        "automatic_thought": field,
        "emotion": field,
        "behavior": field,
        "physical": field,
        "short_term_consequence": field,
        "long_term_consequence": field,
    }


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))
