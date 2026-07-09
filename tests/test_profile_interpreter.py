import json
from types import SimpleNamespace

from app.analytics_loader import AnnotationCoverage
from app.config import load_settings
from app.graph_report import build_report
from app.journal import JournalLog
from app.profile_interpreter import (
    DeepSeekProfileInterpreter,
    interpret_profile_for_settings,
    profile_text_violations,
    resolve_profile_report_mode,
)
from app.report_view_model import build_report_view_model
from app.schemas.episode import Episode
from app.user_report import render_details, render_summary


class _ChatCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


def _client(content=None, error=None):
    completions = _ChatCompletions(content=content, error=error)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_profile_report_mode_resolves_from_runtime_mode():
    ml = load_settings({"TELEGRAM_BOT_TOKEN": "token"})
    production = load_settings(
        {"TELEGRAM_BOT_TOKEN": "token", "M3_APP_MODE": "production"}
    )
    forced = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "M3_PROFILE_REPORT_MODE": "deterministic",
        }
    )

    assert resolve_profile_report_mode(ml) == "deterministic"
    assert resolve_profile_report_mode(production) == "llm"
    assert resolve_profile_report_mode(forced) == "deterministic"


def test_deterministic_profile_interpreter_matches_current_report():
    report = _report()
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    interpreted = interpret_profile_for_settings(report, settings)

    assert interpreted.mode == "deterministic"
    assert interpreted.report.summary_text == render_summary(report)
    assert interpreted.report.details_text == render_details(report)


def test_deepseek_profile_interpreter_uses_safe_structured_payload_only():
    view_model = build_report_view_model(_payload_ready_report_payload())
    client, completions = _client(
        _response_for_view_model(view_model)
    )
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
    )

    result = interpreter.interpret(_payload_ready_report_payload())

    assert result.mode == "llm"
    assert result.report.summary_text.startswith("Короткий отчет")
    assert "В этой части видно повторение." in result.report.summary_text
    assert "Поддержка:" in result.report.summary_text
    assert "Вопрос:" in result.report.summary_text
    assert completions.kwargs["model"] == "deepseek-v4-flash"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    request = json.loads(completions.kwargs["messages"][1]["content"])
    assert request["task"] == "copy_edit_profile_report_claims"
    assert "report_view_model" in request
    assert "insight_payload" not in request
    assert "report_entities" not in request
    assert "report_cards" not in request
    assert "source_quote" not in completions.kwargs["messages"][1]["content"]


def test_llm_unsafe_wording_falls_back_to_deterministic_and_journals(tmp_path):
    report = _report()
    client, _ = _client(
        json.dumps(
            {
                "summary_claims": {
                    section.kind: "Это значит устойчивый диагноз."
                    for section in build_report_view_model(
                        _payload_ready_report_payload()
                    ).summary_sections
                },
                "details_claims": {
                    section.kind: "Подробный отчет"
                    for section in build_report_view_model(
                        _payload_ready_report_payload()
                    ).details_sections
                },
                "safety_notes": [],
            },
            ensure_ascii=False,
        )
    )
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "DEEPSEEK_API_KEY": "test",
            "M3_PROFILE_LLM_MODEL": "deepseek-v4-flash",
        }
    )
    journal_path = tmp_path / "journal.jsonl"

    interpreted = interpret_profile_for_settings(
        report,
        settings,
        journal_log=JournalLog(journal_path),
        client=client,
    )

    assert interpreted.mode == "deterministic"
    assert interpreted.fallback_reason == "unsafe_or_low_quality"
    assert interpreted.report.summary_text == render_summary(report)
    text = journal_path.read_text(encoding="utf-8")
    assert "profile_interpreter.fallback" in text
    assert "Это значит" not in text


def test_llm_section_mismatch_falls_back_to_deterministic(tmp_path):
    report = _report()
    view_model = build_report_view_model(_payload_ready_report_payload())
    summary_claims = {
        section.kind: "В этой части видно повторение."
        for section in view_model.summary_sections
    }
    summary_claims.pop(view_model.summary_sections[0].kind)
    client, _ = _client(
        json.dumps(
            {
                "summary_claims": summary_claims,
                "details_claims": {
                    section.kind: "В этой части видно повторение."
                    for section in view_model.details_sections
                },
                "safety_notes": [],
            },
            ensure_ascii=False,
        )
    )
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "DEEPSEEK_API_KEY": "test",
            "M3_PROFILE_LLM_MODEL": "deepseek-v4-flash",
        }
    )
    journal_path = tmp_path / "journal.jsonl"

    interpreted = interpret_profile_for_settings(
        report,
        settings,
        journal_log=JournalLog(journal_path),
        client=client,
    )

    assert interpreted.mode == "deterministic"
    assert interpreted.fallback_reason == "section_mismatch"
    assert interpreted.report.details_text == render_details(report)


def test_llm_schema_smell_wording_falls_back_to_deterministic(tmp_path):
    report = _report()
    view_model = build_report_view_model(_payload_ready_report_payload())
    client, _ = _client(
        json.dumps(
            {
                "summary_claims": {
                    section.kind: "В рамках сценария этот триггер ведет в подход."
                    for section in view_model.summary_sections
                },
                "details_claims": {
                    section.kind: "В этой части видно повторение."
                    for section in view_model.details_sections
                },
                "safety_notes": [],
            },
            ensure_ascii=False,
        )
    )
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "DEEPSEEK_API_KEY": "test",
            "M3_PROFILE_LLM_MODEL": "deepseek-v4-flash",
        }
    )

    interpreted = interpret_profile_for_settings(report, settings, client=client)

    assert interpreted.mode == "deterministic"
    assert interpreted.fallback_reason == "unsafe_or_low_quality"


def test_missing_profile_llm_config_falls_back_safely(tmp_path):
    report = _report()
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
        }
    )
    journal_path = tmp_path / "journal.jsonl"

    interpreted = interpret_profile_for_settings(
        report,
        settings,
        journal_log=JournalLog(journal_path),
    )

    assert interpreted.mode == "deterministic"
    assert interpreted.fallback_reason == "missing_key_or_model"
    assert "missing_key_or_model" in journal_path.read_text(encoding="utf-8")


def test_profile_text_guard_blocks_internal_and_diagnostic_terms():
    assert "payload" in profile_text_violations("payload", "")
    assert "диагноз" in profile_text_violations("это диагноз", "")
    assert "триггер" in profile_text_violations("этот триггер", "")


def _payload_ready_report_payload():
    from app.insight_payload import build_insight_payload

    return build_insight_payload(_report())


def _response_for_view_model(view_model):
    return json.dumps(
        {
            "summary_claims": {
                section.kind: "В этой части видно повторение."
                for section in view_model.summary_sections
            },
            "details_claims": {
                section.kind: "В этой части видно повторение."
                for section in view_model.details_sections
            },
            "safety_notes": ["sample-bound"],
        },
        ensure_ascii=False,
    )


def _report():
    return build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260430-3", behavior_type="approach")),
        ],
        coverage=AnnotationCoverage(
            observed_count=3,
            annotation_row_count=3,
            annotated_count=3,
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
    )


def _load_episode(data):
    return Episode.model_validate(data)


def _episode(episode_id, *, behavior_type="avoid"):
    nodes = [
        {
            "id": "node-1",
            "node_origin": "observed",
            "kind": "cognition",
            "text": "They will judge me.",
            "source_field": "observed.automatic_thought",
            "source_quote": "they will judge me",
            "confidence": 0.9,
        },
        {
            "id": "node-2",
            "node_origin": "observed",
            "kind": "short_outcome",
            "text": "Relief.",
            "source_field": "observed.short_term_consequence",
            "source_quote": "Relief.",
            "confidence": 0.85,
        },
    ]
    return {
        "id": episode_id,
        "date": f"{episode_id[8:12]}-{episode_id[12:14]}-{episode_id[14:16]}",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "страх", "source_quote": "страх"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed the chat.", "source_quote": "Closed the chat."},
            "short_term_consequence": {"value": "Relief.", "source_quote": "Relief."},
            "long_term_consequence": {
                "value": "Still unresolved.",
                "source_quote": "Still unresolved.",
            },
        },
        "derived": {
            "nodes": nodes,
            "trigger_annotations": [
                {
                    "id": "trigger-annotation-1",
                    "type": "social",
                    "source_field": "observed.situation",
                    "source_quote": "group chat",
                    "confidence": 0.8,
                }
            ],
            "actor_annotations": [],
            "cognition_annotations": [
                {
                    "id": "cognition-annotation-1",
                    "node_id": "node-1",
                    "text": "They will judge me.",
                    "kind": "prediction",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.85,
                }
            ],
            "emotion_annotations": [
                {
                    "id": "emotion-annotation-1",
                    "label": "страх",
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": behavior_type,
                    "source_field": "observed.behavior",
                    "source_quote": "Closed the chat.",
                    "confidence": 0.9,
                }
            ],
            "outcome_annotations": [
                {
                    "id": "outcome-annotation-1",
                    "node_id": "node-2",
                    "horizon": "short_term",
                    "type": "relief",
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
                }
            ],
            "relations": [
                {
                    "id": "relation-1",
                    "type": "belongs_to",
                    "from_ref": "node-1",
                    "to_ref": "episode",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 1.0,
                }
            ],
        },
    }
