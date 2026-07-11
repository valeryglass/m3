import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.capture_artifacts import build_capture_artifact
from app.capture_extraction import CaptureExtractionError
from app.openai_capture_extractor import OpenAICaptureExtractionProvider


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


class _Responses:
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
    responses = _Responses(response, error)
    client = SimpleNamespace(responses=responses)
    return (
        OpenAICaptureExtractionProvider(
            api_key="test", model="explicit-model", client=client
        ),
        responses,
    )


def _response(content=None, *, status="completed", reason=None):
    output = []
    if content is not None:
        output = [SimpleNamespace(type="message", content=[content])]
    return SimpleNamespace(
        status=status,
        incomplete_details=SimpleNamespace(reason=reason),
        output=output,
    )


def test_openai_adapter_uses_strict_responses_schema():
    content = SimpleNamespace(type="output_text", text=json.dumps(_payload()))
    provider, responses = _provider(_response(content))
    result = provider.extract(_artifact())
    assert result.situation.value == "normalized"
    format_spec = responses.kwargs["text"]["format"]
    assert format_spec["type"] == "json_schema"
    assert format_spec["strict"] is True
    assert responses.kwargs["model"] == "explicit-model"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response(SimpleNamespace(type="refusal")), "refusal"),
        (_response(status="incomplete", reason="max_output_tokens"), "incomplete"),
        (_response(status="incomplete", reason="content_filter"), "content_filtered"),
        (_response(), "missing_output"),
        (_response(SimpleNamespace(type="output_text", text="{")), "invalid_schema"),
    ],
)
def test_openai_adapter_maps_response_failures(response, code):
    provider, _ = _provider(response)
    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())
    assert exc.value.code == code


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError(), "provider_timeout"),
        (RuntimeError(), "provider_error"),
        (type("RateLimitError", (RuntimeError,), {})("limited"), "rate_limited"),
    ],
)
def test_openai_adapter_maps_api_failures(error, code):
    provider, _ = _provider(error=error)
    with pytest.raises(CaptureExtractionError) as exc:
        provider.extract(_artifact())
    assert exc.value.code == code


def test_openai_adapter_requires_explicit_credentials_and_model():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAICaptureExtractionProvider(api_key="", model="x", client=object())
    with pytest.raises(ValueError, match="M3_CAPTURE_EXTRACTION_MODEL"):
        OpenAICaptureExtractionProvider(api_key="x", model="", client=object())
