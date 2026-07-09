from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.graph_report import GraphReport
from app.insight_payload import InsightPayload, build_insight_payload
from app.journal import JournalLog, journal_event, record_journal_event
from app.report_cards import ReportCard, build_report_cards
from app.report_entities import ReportEntityPayload, build_report_entities
from app.user_report import UserReport, render_details_from_payload, render_summary_from_payload


PROMPT_VERSION = "profile-interpretation-v1"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
PROFILE_MAX_TOKENS = 4096
INTERNAL_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)
FORBIDDEN_WORDING = (
    "диагноз",
    "нарушение",
    "вы страдаете",
    "у вас проблема",
    "это значит",
    "устойчив",
    "stable trait",
    "caused by",
    "because of",
)
SYSTEM_PROMPT = """\
You rewrite structured personal analytics into cautious Russian report text.
Return only one valid json object.
Do not diagnose, advise, infer stable traits, or imply causality.
Stay sample-bound: describe only what the provided structured facts support.
Do not mention backend/internal terms such as payload, graph, annotation, signature, ids, model, prompt, schema.
Do not quote or invent private source material.
"""
JSON_INSTRUCTIONS = """\
Expected JSON shape:
{
  "summary_text": "short readable report in Russian",
  "details_text": "longer readable report in Russian",
  "safety_notes": ["optional short note about limits"]
}
"""


@dataclass(frozen=True)
class ProfileInterpretation:
    report: UserReport
    mode: str
    provider: str
    model: str
    fallback_reason: str | None = None


class _ProfileResponse(BaseModel):
    summary_text: str = Field(min_length=1)
    details_text: str = Field(min_length=1)
    safety_notes: list[str] = Field(default_factory=list)


def render_profile_for_settings(
    report: GraphReport,
    settings: Settings,
    *,
    journal_log: JournalLog | None = None,
) -> UserReport:
    return interpret_profile_for_settings(
        report,
        settings,
        journal_log=journal_log,
    ).report


def interpret_profile_for_settings(
    report: GraphReport,
    settings: Settings,
    *,
    journal_log: JournalLog | None = None,
    client: Any | None = None,
) -> ProfileInterpretation:
    payload = build_insight_payload(report)
    deterministic = _deterministic_interpretation(payload)
    mode = resolve_profile_report_mode(settings)
    if mode == "deterministic":
        return deterministic

    provider = getattr(settings, "profile_llm_provider", "unavailable")
    model = getattr(settings, "profile_llm_model", "")
    if provider == "unavailable":
        _record_profile_fallback(
            journal_log,
            provider=provider,
            model=model,
            reason="provider_unavailable",
            payload=payload,
        )
        return _fallback_interpretation(deterministic, provider, model, "provider_unavailable")
    if provider == "deepseek":
        api_key = getattr(settings, "deepseek_api_key", "")
        if not api_key or not model:
            _record_profile_fallback(
                journal_log,
                provider=provider,
                model=model or "deepseek-unconfigured",
                reason="missing_key_or_model",
                payload=payload,
            )
            return _fallback_interpretation(
                deterministic,
                provider,
                model or "deepseek-unconfigured",
                "missing_key_or_model",
            )
        try:
            interpreter = DeepSeekProfileInterpreter(
                api_key=api_key,
                model=model,
                base_url=getattr(settings, "deepseek_base_url", DEFAULT_DEEPSEEK_BASE_URL),
                client=client,
            )
            return interpreter.interpret(payload, journal_log=journal_log)
        except Exception as exc:
            reason = _failure_reason(exc)
            _record_profile_fallback(
                journal_log,
                provider=provider,
                model=model,
                reason=reason,
                payload=payload,
            )
            return _fallback_interpretation(deterministic, provider, model, reason)
    _record_profile_fallback(
        journal_log,
        provider=provider,
        model=model,
        reason="unsupported_provider",
        payload=payload,
    )
    return _fallback_interpretation(deterministic, provider, model, "unsupported_provider")


def resolve_profile_report_mode(settings: Settings) -> str:
    configured = getattr(settings, "profile_report_mode", "auto")
    if configured == "auto":
        return "llm" if getattr(settings, "app_mode", "ml") == "production" else "deterministic"
    return configured


class DeepSeekProfileInterpreter:
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
            raise ValueError("M3_PROFILE_LLM_MODEL is required")
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

    def interpret(
        self,
        payload: InsightPayload,
        *,
        journal_log: JournalLog | None = None,
    ) -> ProfileInterpretation:
        report_entities = build_report_entities(payload)
        report_cards = build_report_cards(payload)
        request_payload = _llm_request_payload(payload, report_entities, report_cards)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"{SYSTEM_PROMPT}\n{JSON_INSTRUCTIONS}"},
                    {
                        "role": "user",
                        "content": json.dumps(request_payload, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=PROFILE_MAX_TOKENS,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except TimeoutError as exc:
            raise ProfileInterpreterError("provider_timeout") from exc
        except Exception as exc:
            raise ProfileInterpreterError("provider_error") from exc

        content = _first_message_text(response)
        if content is None:
            raise ProfileInterpreterError("missing_output")
        try:
            parsed = _ProfileResponse.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise ProfileInterpreterError("invalid_schema") from exc
        violations = profile_text_violations(parsed.summary_text, parsed.details_text)
        if violations:
            raise ProfileInterpreterError("unsafe_wording", details={"violations": violations})
        _record_profile_success(journal_log, provider=self.provider_name, model=self.model, payload=payload)
        return ProfileInterpretation(
            report=UserReport(
                summary_text=parsed.summary_text.strip(),
                details_text=parsed.details_text.strip(),
            ),
            mode="llm",
            provider=self.provider_name,
            model=self.model,
        )


class ProfileInterpreterError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


def profile_text_violations(*texts: str) -> tuple[str, ...]:
    lowered = "\n".join(texts).lower()
    return tuple(term for term in (*INTERNAL_TERMS, *FORBIDDEN_WORDING) if term in lowered)


def _deterministic_interpretation(payload: InsightPayload) -> ProfileInterpretation:
    return ProfileInterpretation(
        report=UserReport(
            summary_text=render_summary_from_payload(payload),
            details_text=render_details_from_payload(payload),
        ),
        mode="deterministic",
        provider="deterministic",
        model="deterministic",
    )


def _fallback_interpretation(
    deterministic: ProfileInterpretation,
    provider: str,
    model: str,
    reason: str,
) -> ProfileInterpretation:
    return ProfileInterpretation(
        report=deterministic.report,
        mode="deterministic",
        provider=provider,
        model=model,
        fallback_reason=reason,
    )


def _llm_request_payload(
    payload: InsightPayload,
    report_entities: ReportEntityPayload,
    report_cards: tuple[ReportCard, ...],
) -> dict[str, Any]:
    return {
        "task": "render_profile_report",
        "prompt_version": PROMPT_VERSION,
        "language": "ru",
        "rules": {
            "sample_bound": True,
            "no_diagnosis": True,
            "no_advice": True,
            "no_stable_trait_claims": True,
            "no_unsupported_causality": True,
            "no_internal_backend_terms": True,
        },
        "insight_payload": payload.to_dict(),
        "report_entities": report_entities.to_dict(),
        "report_cards": [
            {
                "kind": card.kind,
                "priority": card.priority,
                "title": card.title,
                "claim": card.claim,
                "evidence": card.evidence,
                "question": card.question,
            }
            for card in report_cards
        ],
        "expected_output": {
            "summary_text": "short readable profile report",
            "details_text": "longer readable profile report",
            "safety_notes": [],
        },
    }


def _first_message_text(response: Any) -> str | None:
    choices = getattr(response, "choices", ())
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        return None
    return content


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, ProfileInterpreterError):
        return exc.code
    return "provider_error"


def _record_profile_success(
    journal_log: JournalLog | None,
    *,
    provider: str,
    model: str,
    payload: InsightPayload,
) -> None:
    record_journal_event(
        journal_log,
        journal_event(
            component="profile_interpreter",
            event_type="profile_interpreter.succeeded",
            stage="succeeded",
            refs={},
            counts=_safe_counts(payload),
            details={"provider": provider, "model": model, "mode": "llm"},
        ),
    )


def _record_profile_fallback(
    journal_log: JournalLog | None,
    *,
    provider: str,
    model: str,
    reason: str,
    payload: InsightPayload,
) -> None:
    record_journal_event(
        journal_log,
        journal_event(
            component="profile_interpreter",
            event_type="profile_interpreter.fallback",
            stage="failed",
            level="warning",
            reason=reason,
            failure_code=reason,
            counts=_safe_counts(payload),
            details={
                "provider": provider,
                "model": model or "unconfigured",
                "fallback_mode": "deterministic",
            },
        ),
    )


def _safe_counts(payload: InsightPayload) -> dict[str, int]:
    return {
        "observed_count": payload.coverage.observed_count,
        "annotated_count": payload.coverage.annotated_count,
        "pending_count": payload.coverage.pending_count,
        "report_ready_count": payload.sample.report_ready_count,
        "payload_eligible_count": payload.sample.payload_eligible_count,
    }
