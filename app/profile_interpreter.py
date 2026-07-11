from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import Settings
from app.graph_report import GraphReport
from app.insight_payload import InsightPayload, build_insight_payload
from app.journal import JournalLog, journal_event, record_journal_event
from app.report_interpretation import (
    BriefReportInterpretation,
    ExpandedReportInterpretation,
    InterpretationBrief,
    InterpretationLimitation,
    InterpretationQuestion,
    InterpretationSection,
    attach_global_sample_evidence,
    brief_interpretation_violations,
    build_report_interpretation_input,
    expanded_interpretation_violations,
    render_interpretation_brief,
    render_interpretation_expanded,
    report_interpretation_is_eligible,
    report_interpretation_numeric_mismatches,
)
from app.report_view_model import (
    build_report_view_model,
    render_details_view,
    render_summary_view,
)
from app.provider_guard import api_failure_code, usage_counts


BRIEF_PROMPT_VERSION = "profile-brief-interpretation-v2"
EXPANDED_PROMPT_VERSION = "profile-expanded-interpretation-v2"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
BRIEF_MAX_TOKENS = 1800
EXPANDED_MAX_TOKENS = 3600
INTERNAL_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)
HARD_GUARD_WORDING = (
    "диагноз",
    "нарушение",
    "вы страдаете",
    "у вас проблема",
    "вам свойственно",
    "вы всегда",
    "ваша черта",
    "устойчивая черта",
    "stable trait",
    "caused by",
    "because of",
    "проаннотированы",
    "вам следует",
    "вам нужно",
    "попробуйте",
)
COMMON_SYSTEM_PROMPT = """\
You are a cautious Russian report interpreter over prepared analytics artifacts.
Return only one valid json object with exactly the requested fields.
Select, rank, and combine supplied artifacts instead of rendering one block per artifact.
Every generated claim and question must cite artifact_ids.
Do not add findings, advice, explanations, numbers, or facts absent from cited artifacts.
Numeric claims may only copy values present in the specifically cited artifacts.
Do not diagnose, advise, infer stable traits, or imply causality.
Stay sample-bound and interpret the report, never the person.
Prefer plain user-facing Russian. Natural Russian terms supplied by the artifacts may be reused.
Do not mention backend/internal terms such as payload, graph, annotation, signature, ids, model, prompt, schema.
Do not quote or invent private source material.
"""
BRIEF_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """\
Create only one coherent brief synthesis of two to five sentences.
Combine at least two analytical artifacts.
Use at most one global reflective question.
Do not create expanded sections, limitations, or map hints.
"""
BRIEF_JSON_INSTRUCTIONS = """\
Expected json shape:
{
  "synthesis": "Two to five Russian sentences.",
  "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
  "next_question": {
    "text": "One Russian reflective question?",
    "artifact_ids": ["question:fork", "exception:fork"]
  }
}
next_question may be null.
If synthesis repeats the total sample size, include evidence:sample in artifact_ids.
"""
EXPANDED_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """\
Create only a compact expanded interpretation with two to five meaning sections.
The first section kind must be main_pattern. Use every later section to add new material.
At least one section must combine two analytical artifacts.
Use one global reflective question at most. Do not add a question after each section.
Use brief_focus_artifact_ids as priority hints when they are supplied, while remaining grounded in the registry.
Do not create a brief or map hints.
"""
EXPANDED_JSON_INSTRUCTIONS = """\
Expected json shape:
{
  "sections": [
    {
      "kind": "main_pattern",
      "title": "Russian title",
      "synthesis": "Grounded synthesis.",
      "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
      "evidence_note": null
    },
    {
      "kind": "outcomes",
      "title": "Russian title",
      "synthesis": "Grounded synthesis that adds a new analytical artifact.",
      "artifact_ids": ["pattern:outcome_pattern"],
      "evidence_note": null
    }
  ],
  "next_question": {
    "text": "One Russian reflective question?",
    "artifact_ids": ["question:fork", "exception:fork"]
  },
  "limitations": [
    {
      "text": "One sample-bound limitation.",
      "artifact_ids": ["evidence:sample"]
    }
  ]
}
next_question may be null. limitations may be an empty array.
Section kind must be one of: main_pattern, choice_or_exception, outcomes, change, unexplained.
If generated text repeats the total sample size, include evidence:sample in that block's artifact_ids.
"""

_KNOWN_SCHEMA_PATH_PARTS = frozenset(
    {
        "synthesis",
        "artifact_ids",
        "next_question",
        "sections",
        "kind",
        "title",
        "evidence_note",
        "text",
        "limitations",
    }
)


@dataclass(frozen=True)
class ProfileBriefResult:
    text: str
    mode: str
    provider: str
    model: str
    fallback_reason: str | None = None
    interpretation: BriefReportInterpretation | None = None

    @property
    def selected_artifact_ids(self) -> tuple[str, ...]:
        if self.interpretation is None:
            return ()
        ids = list(self.interpretation.brief.artifact_ids)
        if self.interpretation.next_question is not None:
            ids.extend(self.interpretation.next_question.artifact_ids)
        return tuple(dict.fromkeys(ids))


@dataclass(frozen=True)
class ProfileExpandedResult:
    text: str
    mode: str
    provider: str
    model: str
    fallback_reason: str | None = None
    interpretation: ExpandedReportInterpretation | None = None


class _QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    artifact_ids: list[str]


class _BriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthesis: str
    artifact_ids: list[str]
    next_question: _QuestionResponse | None = None


class _SectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    title: str
    synthesis: str
    artifact_ids: list[str]
    evidence_note: str | None = None


class _LimitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    artifact_ids: list[str]


class _ExpandedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[_SectionResponse]
    next_question: _QuestionResponse | None = None
    limitations: list[_LimitationResponse]


def interpret_profile_brief_for_settings(
    report: GraphReport,
    settings: Settings,
    *,
    journal_log: JournalLog | None = None,
    client: Any | None = None,
    usage_recorder: Callable[[int, int, int], None] | None = None,
) -> ProfileBriefResult:
    payload = build_insight_payload(report)
    deterministic = _deterministic_brief(payload)
    if resolve_profile_report_mode(settings) == "deterministic":
        return deterministic

    interpretation_input = build_report_interpretation_input(payload)
    if not report_interpretation_is_eligible(interpretation_input):
        return _brief_fallback(
            deterministic,
            settings,
            payload,
            journal_log,
            "insufficient_interpretation_material",
        )
    try:
        interpreter = _deepseek_interpreter_for_settings(
            settings,
            client=client,
            usage_recorder=usage_recorder,
        )
        return interpreter.interpret_brief(payload, journal_log=journal_log)
    except Exception as exc:
        return _brief_fallback(
            deterministic,
            settings,
            payload,
            journal_log,
            _failure_reason(exc),
            failure_details=_failure_details(exc),
        )


def interpret_profile_expanded_for_settings(
    report: GraphReport,
    settings: Settings,
    *,
    brief_artifact_ids: tuple[str, ...] = (),
    journal_log: JournalLog | None = None,
    client: Any | None = None,
    usage_recorder: Callable[[int, int, int], None] | None = None,
) -> ProfileExpandedResult:
    payload = build_insight_payload(report)
    deterministic = _deterministic_expanded(payload)
    if resolve_profile_report_mode(settings) == "deterministic":
        return deterministic

    interpretation_input = build_report_interpretation_input(payload)
    if not report_interpretation_is_eligible(interpretation_input):
        return _expanded_fallback(
            deterministic,
            settings,
            payload,
            journal_log,
            "insufficient_interpretation_material",
        )
    try:
        interpreter = _deepseek_interpreter_for_settings(
            settings,
            client=client,
            usage_recorder=usage_recorder,
        )
        return interpreter.interpret_expanded(
            payload,
            brief_artifact_ids=brief_artifact_ids,
            journal_log=journal_log,
        )
    except Exception as exc:
        return _expanded_fallback(
            deterministic,
            settings,
            payload,
            journal_log,
            _failure_reason(exc),
            failure_details=_failure_details(exc),
        )


def resolve_profile_report_mode(settings: Settings) -> str:
    configured = getattr(settings, "profile_report_mode", "auto")
    if configured == "auto":
        return "llm" if getattr(settings, "app_mode", "ml") == "production" else "deterministic"
    return configured


class DeepSeekProfileInterpreter:
    provider_name = "deepseek.chat"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        client: Any | None = None,
        timeout_seconds: float = 60.0,
        usage_recorder: Callable[[int, int, int], None] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DEEPSEEK_API_KEY is required")
        if not model.strip():
            raise ValueError("M3_PROFILE_LLM_MODEL is required")
        self.model = model.strip()
        self.base_url = base_url.strip() or DEFAULT_DEEPSEEK_BASE_URL
        self.usage_recorder = usage_recorder
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

    def interpret_brief(
        self,
        payload: InsightPayload,
        *,
        journal_log: JournalLog | None = None,
    ) -> ProfileBriefResult:
        interpretation_input = build_report_interpretation_input(payload)
        if not report_interpretation_is_eligible(interpretation_input):
            raise ProfileInterpreterError("insufficient_interpretation_material")
        response_data, response_chars = self._complete(
            system_prompt=f"{BRIEF_SYSTEM_PROMPT}\n{BRIEF_JSON_INSTRUCTIONS}",
            request_payload=_brief_request_payload(interpretation_input.to_dict()),
            max_tokens=BRIEF_MAX_TOKENS,
        )
        parsed = _validate_response(
            _BriefResponse,
            response_data,
            response_chars=response_chars,
            known_fields={"synthesis", "artifact_ids", "next_question"},
        )
        interpretation = attach_global_sample_evidence(
            interpretation_input,
            _brief_interpretation_from_response(parsed),
        )
        if not isinstance(interpretation, BriefReportInterpretation):
            raise ProfileInterpreterError("invalid_schema")
        violations = brief_interpretation_violations(
            interpretation_input,
            interpretation,
        )
        _raise_for_interpretation_violations(
            interpretation_input,
            interpretation,
            violations,
        )
        text = render_interpretation_brief(interpretation_input, interpretation)
        quality_violations = profile_quality_violations(text)
        if quality_violations:
            raise ProfileInterpreterError(
                "unsafe_or_low_quality",
                details={"violations": quality_violations},
            )
        _record_profile_success(
            journal_log,
            surface="brief",
            provider=self.provider_name,
            model=self.model,
            payload=payload,
            artifact_ids=_brief_artifact_ids(interpretation),
            question_present=interpretation.next_question is not None,
        )
        return ProfileBriefResult(
            text=text,
            mode="llm",
            provider=self.provider_name,
            model=self.model,
            interpretation=interpretation,
        )

    def interpret_expanded(
        self,
        payload: InsightPayload,
        *,
        brief_artifact_ids: tuple[str, ...] = (),
        journal_log: JournalLog | None = None,
    ) -> ProfileExpandedResult:
        interpretation_input = build_report_interpretation_input(payload)
        if not report_interpretation_is_eligible(interpretation_input):
            raise ProfileInterpreterError("insufficient_interpretation_material")
        known_ids = interpretation_input.artifacts_by_id()
        safe_focus_ids = tuple(
            dict.fromkeys(
                artifact_id
                for artifact_id in brief_artifact_ids
                if artifact_id in known_ids
            )
        )
        response_data, response_chars = self._complete(
            system_prompt=f"{EXPANDED_SYSTEM_PROMPT}\n{EXPANDED_JSON_INSTRUCTIONS}",
            request_payload=_expanded_request_payload(
                interpretation_input.to_dict(),
                brief_artifact_ids=safe_focus_ids,
            ),
            max_tokens=EXPANDED_MAX_TOKENS,
        )
        parsed = _validate_response(
            _ExpandedResponse,
            response_data,
            response_chars=response_chars,
            known_fields={"sections", "next_question", "limitations"},
        )
        interpretation = attach_global_sample_evidence(
            interpretation_input,
            _expanded_interpretation_from_response(parsed),
        )
        if not isinstance(interpretation, ExpandedReportInterpretation):
            raise ProfileInterpreterError("invalid_schema")
        violations = expanded_interpretation_violations(
            interpretation_input,
            interpretation,
        )
        _raise_for_interpretation_violations(
            interpretation_input,
            interpretation,
            violations,
        )
        text = render_interpretation_expanded(interpretation_input, interpretation)
        quality_violations = profile_quality_violations(text)
        if quality_violations:
            raise ProfileInterpreterError(
                "unsafe_or_low_quality",
                details={"violations": quality_violations},
            )
        artifact_ids = {
            *(artifact_id for section in interpretation.sections for artifact_id in section.artifact_ids),
            *(artifact_id for item in interpretation.limitations for artifact_id in item.artifact_ids),
            *(
                interpretation.next_question.artifact_ids
                if interpretation.next_question is not None
                else ()
            ),
        }
        _record_profile_success(
            journal_log,
            surface="expanded",
            provider=self.provider_name,
            model=self.model,
            payload=payload,
            artifact_ids=tuple(artifact_ids),
            question_present=interpretation.next_question is not None,
            section_count=len(interpretation.sections),
            limitation_count=len(interpretation.limitations),
        )
        return ProfileExpandedResult(
            text=text,
            mode="llm",
            provider=self.provider_name,
            model=self.model,
            interpretation=interpretation,
        )

    def _complete(
        self,
        *,
        system_prompt: str,
        request_payload: dict[str, Any],
        max_tokens: int,
    ) -> tuple[dict[str, Any], int]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(request_payload, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except TimeoutError as exc:
            raise ProfileInterpreterError("provider_timeout") from exc
        except Exception as exc:
            raise ProfileInterpreterError(api_failure_code(exc)) from exc

        if self.usage_recorder is not None:
            self.usage_recorder(*usage_counts(response))

        content = _first_message_text(response)
        if content is None:
            raise ProfileInterpreterError("missing_output")
        try:
            response_data = json.loads(content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProfileInterpreterError(
                "invalid_schema",
                details={
                    "parser_stage": "json_decode",
                    "response_chars": len(content),
                    "json_parse_ok": False,
                    "validation_error_count": 1,
                },
            ) from exc
        if not isinstance(response_data, dict):
            raise ProfileInterpreterError(
                "invalid_schema",
                details={
                    "parser_stage": "top_level_shape",
                    "response_chars": len(content),
                    "json_parse_ok": True,
                    "validation_error_count": 1,
                },
            )
        return response_data, len(content)


class ProfileInterpreterError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


def profile_text_violations(*texts: str) -> tuple[str, ...]:
    lowered = "\n".join(texts).lower()
    return tuple(
        term
        for term in (*INTERNAL_TERMS, *HARD_GUARD_WORDING)
        if _contains_guard_term(lowered, term)
    )


def profile_quality_violations(*texts: str) -> tuple[str, ...]:
    return profile_text_violations(*texts)


def _contains_guard_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _deepseek_interpreter_for_settings(
    settings: Settings,
    *,
    client: Any | None,
    usage_recorder: Callable[[int, int, int], None] | None = None,
) -> DeepSeekProfileInterpreter:
    provider = getattr(settings, "profile_llm_provider", "unavailable")
    model = getattr(settings, "profile_llm_model", "")
    if provider == "unavailable":
        raise ProfileInterpreterError("provider_unavailable")
    if provider != "deepseek":
        raise ProfileInterpreterError("unsupported_provider")
    api_key = getattr(settings, "deepseek_api_key", "")
    if not api_key or not model:
        raise ProfileInterpreterError("missing_key_or_model")
    return DeepSeekProfileInterpreter(
        api_key=api_key,
        model=model,
        base_url=getattr(settings, "deepseek_base_url", DEFAULT_DEEPSEEK_BASE_URL),
        client=client,
        usage_recorder=usage_recorder,
    )


def _deterministic_brief(payload: InsightPayload) -> ProfileBriefResult:
    return ProfileBriefResult(
        text=render_summary_view(build_report_view_model(payload)),
        mode="deterministic",
        provider="deterministic",
        model="deterministic",
    )


def _deterministic_expanded(payload: InsightPayload) -> ProfileExpandedResult:
    return ProfileExpandedResult(
        text=render_details_view(build_report_view_model(payload)),
        mode="deterministic",
        provider="deterministic",
        model="deterministic",
    )


def _brief_fallback(
    deterministic: ProfileBriefResult,
    settings: Settings,
    payload: InsightPayload,
    journal_log: JournalLog | None,
    reason: str,
    *,
    failure_details: dict[str, Any] | None = None,
) -> ProfileBriefResult:
    _record_profile_fallback(
        journal_log,
        surface="brief",
        provider=getattr(settings, "profile_llm_provider", "unavailable"),
        model=getattr(settings, "profile_llm_model", ""),
        reason=reason,
        payload=payload,
        failure_details=failure_details,
    )
    return ProfileBriefResult(
        text=deterministic.text,
        mode="deterministic",
        provider=getattr(settings, "profile_llm_provider", "unavailable"),
        model=getattr(settings, "profile_llm_model", ""),
        fallback_reason=reason,
    )


def _expanded_fallback(
    deterministic: ProfileExpandedResult,
    settings: Settings,
    payload: InsightPayload,
    journal_log: JournalLog | None,
    reason: str,
    *,
    failure_details: dict[str, Any] | None = None,
) -> ProfileExpandedResult:
    _record_profile_fallback(
        journal_log,
        surface="expanded",
        provider=getattr(settings, "profile_llm_provider", "unavailable"),
        model=getattr(settings, "profile_llm_model", ""),
        reason=reason,
        payload=payload,
        failure_details=failure_details,
    )
    return ProfileExpandedResult(
        text=deterministic.text,
        mode="deterministic",
        provider=getattr(settings, "profile_llm_provider", "unavailable"),
        model=getattr(settings, "profile_llm_model", ""),
        fallback_reason=reason,
    )


def _brief_request_payload(interpretation_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": "render_evidence_bound_profile_brief",
        "prompt_version": BRIEF_PROMPT_VERSION,
        "language": "ru",
        "rules": _common_request_rules(),
        "report_interpretation_input": interpretation_input,
        "expected_output": {
            "synthesis": "Two to five Russian sentences.",
            "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
            "next_question": {
                "text": "One Russian reflective question?",
                "artifact_ids": ["question:fork", "exception:fork"],
            },
        },
    }


def _expanded_request_payload(
    interpretation_input: dict[str, Any],
    *,
    brief_artifact_ids: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "task": "render_evidence_bound_profile_expanded",
        "prompt_version": EXPANDED_PROMPT_VERSION,
        "language": "ru",
        "rules": {
            **_common_request_rules(),
            "section_count": {"minimum": 2, "maximum": 5},
            "allowed_section_kinds": [
                "main_pattern",
                "choice_or_exception",
                "outcomes",
                "change",
                "unexplained",
            ],
        },
        "brief_focus_artifact_ids": list(brief_artifact_ids),
        "report_interpretation_input": interpretation_input,
        "expected_output": {
            "sections": [
                {
                    "kind": "main_pattern",
                    "title": "Russian title",
                    "synthesis": "Grounded synthesis.",
                    "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
                    "evidence_note": None,
                },
                {
                    "kind": "outcomes",
                    "title": "Russian title",
                    "synthesis": "Grounded synthesis that adds new material.",
                    "artifact_ids": ["pattern:outcome_pattern"],
                    "evidence_note": None,
                },
            ],
            "next_question": {
                "text": "One Russian reflective question?",
                "artifact_ids": ["question:fork", "exception:fork"],
            },
            "limitations": [
                {
                    "text": "One sample-bound limitation.",
                    "artifact_ids": ["evidence:sample"],
                }
            ],
        },
    }


def _common_request_rules() -> dict[str, Any]:
    return {
        "report_interpreter_only": True,
        "sample_bound": True,
        "no_diagnosis": True,
        "no_advice": True,
        "no_stable_trait_claims": True,
        "no_unsupported_causality": True,
        "no_internal_backend_terms": True,
        "artifact_ids_required": True,
        "combine_multiple_artifacts": True,
        "one_global_question_maximum": True,
        "numeric_facts_require_cited_artifacts": True,
    }


def _brief_interpretation_from_response(parsed: _BriefResponse) -> BriefReportInterpretation:
    return BriefReportInterpretation(
        brief=InterpretationBrief(
            synthesis=parsed.synthesis.strip(),
            artifact_ids=tuple(parsed.artifact_ids),
        ),
        next_question=_question_from_response(parsed.next_question),
    )


def _expanded_interpretation_from_response(
    parsed: _ExpandedResponse,
) -> ExpandedReportInterpretation:
    return ExpandedReportInterpretation(
        sections=tuple(
            InterpretationSection(
                kind=section.kind,
                title=section.title.strip(),
                synthesis=section.synthesis.strip(),
                artifact_ids=tuple(section.artifact_ids),
                evidence_note=(
                    section.evidence_note.strip()
                    if section.evidence_note is not None
                    else None
                ),
            )
            for section in parsed.sections
        ),
        next_question=_question_from_response(parsed.next_question),
        limitations=tuple(
            InterpretationLimitation(
                text=item.text.strip(),
                artifact_ids=tuple(item.artifact_ids),
            )
            for item in parsed.limitations
        ),
    )


def _question_from_response(
    parsed: _QuestionResponse | None,
) -> InterpretationQuestion | None:
    if parsed is None:
        return None
    return InterpretationQuestion(
        text=parsed.text.strip(),
        artifact_ids=tuple(parsed.artifact_ids),
    )


def _validate_response(
    model_type,
    response_data: dict[str, Any],
    *,
    response_chars: int,
    known_fields: set[str],
):
    try:
        return model_type.model_validate(response_data)
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_input=False)
        present_fields = sorted(field for field in response_data if field in known_fields)
        raise ProfileInterpreterError(
            "invalid_schema",
            details={
                "parser_stage": "schema_validation",
                "response_chars": response_chars,
                "json_parse_ok": True,
                "present_fields": present_fields,
                "unexpected_top_level_count": len(response_data) - len(present_fields),
                "validation_error_count": len(errors),
                "validation_error_paths": [
                    _safe_validation_path(error.get("loc", ()))
                    for error in errors[:12]
                ],
                "validation_error_types": sorted(
                    {str(error.get("type", "unknown")) for error in errors}
                )[:12],
            },
        ) from exc


def _raise_for_interpretation_violations(
    interpretation_input,
    interpretation,
    violations: tuple[str, ...],
) -> None:
    if "artifact_ref_mismatch" in violations:
        raise ProfileInterpreterError(
            "artifact_ref_mismatch",
            details={"violations": violations},
        )
    if "unsupported_number" in violations:
        mismatches = report_interpretation_numeric_mismatches(
            interpretation_input,
            interpretation,
        )
        raise ProfileInterpreterError(
            "unsupported_fact",
            details={
                "violations": violations,
                "numeric_mismatches": [item.to_dict() for item in mismatches[:12]],
            },
        )
    if violations:
        raise ProfileInterpreterError(
            "unsafe_or_low_quality",
            details={"violations": violations},
        )


def _brief_artifact_ids(
    interpretation: BriefReportInterpretation,
) -> tuple[str, ...]:
    ids = list(interpretation.brief.artifact_ids)
    if interpretation.next_question is not None:
        ids.extend(interpretation.next_question.artifact_ids)
    return tuple(dict.fromkeys(ids))


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


def _failure_details(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, ProfileInterpreterError):
        return {}
    return dict(exc.details)


def _safe_validation_path(location: Any) -> str:
    parts: list[str] = []
    for part in location:
        if isinstance(part, int):
            parts.append("[]")
        elif str(part) in _KNOWN_SCHEMA_PATH_PARTS:
            parts.append(str(part))
        else:
            parts.append("<unexpected>")
    return ".".join(parts) or "<root>"


def _record_profile_success(
    journal_log: JournalLog | None,
    *,
    surface: str,
    provider: str,
    model: str,
    payload: InsightPayload,
    artifact_ids: tuple[str, ...],
    question_present: bool,
    section_count: int = 0,
    limitation_count: int = 0,
) -> None:
    record_journal_event(
        journal_log,
        journal_event(
            component="profile_interpreter",
            event_type=f"profile_interpreter.{surface}_succeeded",
            stage="succeeded",
            refs={},
            counts={
                **_safe_counts(payload),
                "selected_artifact_count": len(set(artifact_ids)),
                "section_count": section_count,
                "limitation_count": limitation_count,
            },
            details={
                "surface": surface,
                "provider": provider,
                "model": model,
                "mode": "llm_split_interpretation",
                "question_present": question_present,
                "thinking": "disabled",
            },
        ),
    )


def _record_profile_fallback(
    journal_log: JournalLog | None,
    *,
    surface: str,
    provider: str,
    model: str,
    reason: str,
    payload: InsightPayload,
    failure_details: dict[str, Any] | None = None,
) -> None:
    details = {
        "surface": surface,
        "provider": provider,
        "model": model or "unconfigured",
        "fallback_mode": "deterministic",
        "thinking": "disabled",
    }
    if failure_details:
        details.update(failure_details)
    record_journal_event(
        journal_log,
        journal_event(
            component="profile_interpreter",
            event_type=f"profile_interpreter.{surface}_fallback",
            stage="failed",
            level="warning",
            reason=reason,
            failure_code=reason,
            counts=_safe_counts(payload),
            details=details,
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
