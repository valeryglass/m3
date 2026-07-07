import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.capture_artifacts import build_capture_artifact
from app.capture_extraction import CaptureExtractionError
from app.deepseek_capture_extractor import DeepSeekCaptureExtractionProvider


def _artifact():
    return build_capture_artifact(
        chat_id=42,
        mode="one_take_text",
        media_kind="text",
        pieces=(("one_take_text", "same evidence"),),
        created_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
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


class _ChatCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def _provider(response=None, error=None, *, capture_debug_dir=None, raw_debug=False):
    completions = _ChatCompletions(response, error)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    return (
        DeepSeekCaptureExtractionProvider(
            api_key="test",
            model="deepseek-v4-flash",
            base_url="https://deepseek.test",
            client=client,
            capture_debug_dir=capture_debug_dir,
            capture_debug_raw_provider_output=raw_debug,
        ),
        completions,
    )


def _response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


def test_deepseek_adapter_uses_chat_json_mode_and_disables_thinking():
    provider, completions = _provider(_response(json.dumps(_payload())))

    result = provider.extract(_artifact())

    assert result.situation.value == "normalized"
    assert completions.kwargs["model"] == "deepseek-v4-flash"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "json" in completions.kwargs["messages"][0]["content"].lower()
    assert completions.kwargs["max_tokens"] >= 1000


def test_deepseek_adapter_writes_success_debug_sidecar(tmp_path):
    provider, _ = _provider(
        _response(json.dumps(_payload())),
        capture_debug_dir=tmp_path,
    )

    provider.extract(_artifact())

    debug = _read_debug(tmp_path)
    assert debug["parser_stage"] == "parsed"
    assert debug["json_parse_ok"] is True
    assert debug["response_chars"] > 0
    assert "raw_provider_output" not in debug


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response(""), "missing_output"),
        (_response("{"), "invalid_schema"),
        (SimpleNamespace(choices=[]), "missing_output"),
    ],
)
def test_deepseek_adapter_maps_response_failures(response, code):
    provider, _ = _provider(response)
    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())
    assert exc.value.code == code


def test_deepseek_adapter_debug_records_malformed_json(tmp_path):
    provider, _ = _provider(_response("{"), capture_debug_dir=tmp_path)

    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())

    debug = _read_debug(tmp_path)
    assert exc.value.code == "invalid_schema"
    assert debug["failure_code"] == "invalid_schema"
    assert debug["parser_stage"] == "json_parse"
    assert debug["response_chars"] == 1


def test_deepseek_adapter_debug_records_schema_mismatch(tmp_path):
    provider, _ = _provider(
        _response(json.dumps({"situation": {"value": "x"}})),
        capture_debug_dir=tmp_path,
    )

    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())

    debug = _read_debug(tmp_path)
    assert exc.value.code == "invalid_schema"
    assert debug["parser_stage"] == "schema_validation"
    assert debug["validation_error_count"] > 0


def test_deepseek_adapter_schema_mismatch_carries_partial_fields(tmp_path):
    payload = _payload()
    payload["physical"] = {"value": "tense"}
    provider, _ = _provider(
        _response(json.dumps(payload)),
        capture_debug_dir=tmp_path,
    )

    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())

    assert exc.value.code == "invalid_schema"
    assert exc.value.partial_result is not None
    assert "situation" in exc.value.partial_result.observed
    assert "physical" not in exc.value.partial_result.observed
    assert exc.value.partial_result.rejected_fields == {"physical": "invalid_schema"}


def test_deepseek_adapter_debug_records_missing_output(tmp_path):
    provider, _ = _provider(_response(""), capture_debug_dir=tmp_path)

    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())

    debug = _read_debug(tmp_path)
    assert exc.value.code == "missing_output"
    assert debug["failure_code"] == "missing_output"
    assert debug["response_present"] is False


def test_deepseek_adapter_raw_debug_output_requires_toggle(tmp_path):
    content = json.dumps({"wrong": "shape"})
    provider, _ = _provider(
        _response(content),
        capture_debug_dir=tmp_path,
        raw_debug=True,
    )

    with pytest.raises(CaptureExtractionError):
        provider.extract(_artifact())

    debug = _read_debug(tmp_path)
    assert debug["raw_provider_output"] == content


@pytest.mark.parametrize(
    ("error", "code"),
    [(TimeoutError(), "provider_timeout"), (RuntimeError(), "provider_error")],
)
def test_deepseek_adapter_maps_api_failures(error, code):
    provider, _ = _provider(error=error)
    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())
    assert exc.value.code == code


def test_deepseek_adapter_requires_explicit_credentials_and_model():
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekCaptureExtractionProvider(api_key="", model="x", client=object())
    with pytest.raises(ValueError, match="M3_CAPTURE_EXTRACTION_MODEL"):
        DeepSeekCaptureExtractionProvider(api_key="x", model="", client=object())


def _read_debug(root):
    paths = list(root.rglob("debug-*.json"))
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))
