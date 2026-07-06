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


def _provider(response=None, error=None):
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
