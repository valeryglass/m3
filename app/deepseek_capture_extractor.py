from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.capture_extraction import PROMPT_VERSION, CaptureExtractionError
from app.openai_capture_extractor import SYSTEM_PROMPT
from app.schemas.capture import CaptureArtifact, CaptureExtractionResult


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MAX_TOKENS = 4096
DEEPSEEK_JSON_INSTRUCTIONS = """\
Return only one valid json object with this shape:
{
  "situation": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "trigger": null,
  "actor": null,
  "quote": null,
  "automatic_thought": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "emotion": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "behavior": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "physical": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "short_term_consequence": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0},
  "long_term_consequence": {"value": "...", "source_quote": "...", "source_piece_role": "...", "confidence": 0.0}
}
Use null for absent optional fields.
"""
DEEPSEEK_SYSTEM_PROMPT = f"{SYSTEM_PROMPT}\n{DEEPSEEK_JSON_INSTRUCTIONS}"


class DeepSeekCaptureExtractionProvider:
    provider_name = "deepseek.chat"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        client: Any | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DEEPSEEK_API_KEY is required")
        if not model.strip():
            raise ValueError("M3_CAPTURE_EXTRACTION_MODEL is required")
        self.model = model.strip()
        self.base_url = base_url.strip() or DEFAULT_DEEPSEEK_BASE_URL
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the openai package") from exc
            client = OpenAI(
                api_key=api_key,
                base_url=self.base_url,
                timeout=timeout_seconds,
            )
        self.client = client

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "mode": artifact.mode,
                                "pieces": [
                                    {"role": piece.role, "text": piece.text}
                                    for piece in artifact.pieces
                                ],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=DEEPSEEK_MAX_TOKENS,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except TimeoutError as exc:
            raise CaptureExtractionError("provider_timeout") from exc
        except Exception as exc:
            raise CaptureExtractionError("provider_error") from exc

        content = _first_message_text(response)
        if content is None:
            raise CaptureExtractionError("missing_output")
        try:
            return CaptureExtractionResult.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise CaptureExtractionError("invalid_schema") from exc


def _first_message_text(response: Any) -> str | None:
    choices = getattr(response, "choices", ())
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        return None
    return content
