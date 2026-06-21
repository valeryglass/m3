from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.capture_extraction import (
    PROMPT_VERSION,
    CaptureExtractionError,
    extraction_result_schema,
)
from app.schemas.capture import CaptureArtifact, CaptureExtractionResult


SYSTEM_PROMPT = """\
Extract one concrete CBT/ACT episode from the supplied capture evidence.
Return all seven required observed fields and optional context fields only when
grounded. Values may normalize the user's wording, but every source_quote must
be copied exactly from one declared source piece. Do not diagnose, advise,
invent events, or fill unsupported evidence. For three-block capture, use:
outside_context for situation/trigger/actor/quote; inner_context for
automatic_thought/emotion/physical; response_outcome for behavior and both
consequences.
"""


class OpenAICaptureExtractionProvider:
    provider_name = "openai.responses"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: Any | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required")
        if not model.strip():
            raise ValueError("M3_CAPTURE_EXTRACTION_MODEL is required")
        self.model = model.strip()
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the openai package") from exc
            client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.client = client

    def extract(self, artifact: CaptureArtifact) -> CaptureExtractionResult:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
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
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "capture_extraction",
                        "strict": True,
                        "schema": extraction_result_schema(),
                    }
                },
            )
        except TimeoutError as exc:
            raise CaptureExtractionError("provider_timeout") from exc
        except Exception as exc:
            raise CaptureExtractionError("provider_error") from exc

        if getattr(response, "status", None) == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None)
            if reason == "content_filter":
                raise CaptureExtractionError("content_filtered")
            raise CaptureExtractionError("incomplete")

        content = _first_message_content(response)
        if content is None:
            raise CaptureExtractionError("missing_output")
        if getattr(content, "type", None) == "refusal":
            raise CaptureExtractionError("refusal")
        if getattr(content, "type", None) != "output_text":
            raise CaptureExtractionError("missing_output")
        try:
            return CaptureExtractionResult.model_validate_json(content.text)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise CaptureExtractionError("invalid_schema") from exc


def _first_message_content(response: Any):
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) == "message":
            content = getattr(item, "content", ())
            return content[0] if content else None
    return None
