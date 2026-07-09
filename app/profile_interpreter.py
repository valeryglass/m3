from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.graph_report import GraphReport
from app.insight_payload import InsightPayload, build_insight_payload
from app.journal import JournalLog, journal_event, record_journal_event
from app.report_view_model import (
    ReportViewModel,
    apply_claim_rewrites,
    build_report_view_model,
    render_details_view,
    render_summary_view,
)
from app.user_report import UserReport


PROMPT_VERSION = "profile-copy-editor-v2"
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
    "проаннотированы",
    "триггер",
    "подход",
    "компенсация",
    "исход",
    "в рамках сценария",
)
SYSTEM_PROMPT = """\
You are a cautious Russian copy editor for a prepared personal analytics report.
Return only one valid json object.
Rewrite only section claim text.
Preserve every section kind exactly.
Do not rewrite titles, evidence, support counts, limits, or questions.
Do not add findings, advice, numbers, explanations, labels, or new facts.
Do not diagnose, advise, infer stable traits, or imply causality.
Stay sample-bound: keep each claim about what is visible in the current sample.
Avoid schema-like words such as trigger, approach, compensation, outcome, annotated.
Do not mention backend/internal terms such as payload, graph, annotation, signature, ids, model, prompt, schema.
Do not quote or invent private source material.
"""
JSON_INSTRUCTIONS = """\
Expected JSON shape:
{
  "summary_claims": {"section_kind": "rewritten claim"},
  "details_claims": {"section_kind": "rewritten claim"},
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
    summary_claims: dict[str, str] = Field(default_factory=dict)
    details_claims: dict[str, str] = Field(default_factory=dict)
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
        view_model = build_report_view_model(payload)
        request_payload = _llm_request_payload(view_model)
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
        _require_matching_sections(parsed, view_model)
        rewritten = apply_claim_rewrites(
            view_model,
            summary_claims=parsed.summary_claims,
            details_claims=parsed.details_claims,
        )
        summary_text = render_summary_view(rewritten)
        details_text = render_details_view(rewritten)
        violations = profile_quality_violations(summary_text, details_text)
        if violations:
            raise ProfileInterpreterError(
                "unsafe_or_low_quality",
                details={"violations": violations},
            )
        _record_profile_success(journal_log, provider=self.provider_name, model=self.model, payload=payload)
        return ProfileInterpretation(
            report=UserReport(
                summary_text=summary_text,
                details_text=details_text,
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
    return tuple(
        term
        for term in (*INTERNAL_TERMS, *FORBIDDEN_WORDING)
        if _contains_guard_term(lowered, term)
    )


def profile_quality_violations(*texts: str) -> tuple[str, ...]:
    return profile_text_violations(*texts)


def _contains_guard_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _deterministic_interpretation(payload: InsightPayload) -> ProfileInterpretation:
    view_model = build_report_view_model(payload)
    return ProfileInterpretation(
        report=UserReport(
            summary_text=render_summary_view(view_model),
            details_text=render_details_view(view_model),
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
    view_model: ReportViewModel,
) -> dict[str, Any]:
    return {
        "task": "copy_edit_profile_report_claims",
        "prompt_version": PROMPT_VERSION,
        "language": "ru",
        "rules": {
            "copy_editor_only": True,
            "sample_bound": True,
            "no_diagnosis": True,
            "no_advice": True,
            "no_stable_trait_claims": True,
            "no_unsupported_causality": True,
            "no_internal_backend_terms": True,
            "preserve_section_kinds": True,
            "rewrite_claims_only": True,
            "do_not_rewrite_titles_evidence_limits_questions": True,
        },
        "report_view_model": view_model.to_dict(),
        "expected_output": {
            "summary_claims": {
                section.kind: "rewritten claim"
                for section in view_model.summary_sections
            },
            "details_claims": {
                section.kind: "rewritten claim"
                for section in view_model.details_sections
            },
            "safety_notes": [],
        },
    }


def _require_matching_sections(
    parsed: _ProfileResponse,
    view_model: ReportViewModel,
) -> None:
    expected_summary = {section.kind for section in view_model.summary_sections}
    expected_details = {section.kind for section in view_model.details_sections}
    if set(parsed.summary_claims) != expected_summary:
        raise ProfileInterpreterError("section_mismatch")
    if set(parsed.details_claims) != expected_details:
        raise ProfileInterpreterError("section_mismatch")
    empty_claims = [
        claim
        for claim in (*parsed.summary_claims.values(), *parsed.details_claims.values())
        if not claim.strip()
    ]
    if empty_claims:
        raise ProfileInterpreterError("section_mismatch")


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
