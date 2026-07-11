import json
from types import SimpleNamespace

from app.analytics_loader import AnnotationCoverage
from app.config import load_settings
from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.journal import JournalLog
from app.profile_interpreter import (
    DeepSeekProfileInterpreter,
    interpret_profile_brief_for_settings,
    interpret_profile_expanded_for_settings,
    profile_text_violations,
    resolve_profile_report_mode,
)
from app.user_report import render_details, render_summary
from tests.test_user_report import _episode, _load_episode


class _ChatCompletions:
    def __init__(self, contents=None, error=None, usage=None):
        self.contents = list(contents or [])
        self.error = error
        self.calls = []
        self.usage = usage

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = self.contents.pop(0) if self.contents else None
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=self.usage,
        )


def _client(*contents, error=None, usage=None):
    completions = _ChatCompletions(contents=contents, error=error, usage=usage)
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


def test_deterministic_brief_and_expanded_match_current_reports():
    report = _report()
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    brief = interpret_profile_brief_for_settings(report, settings)
    expanded = interpret_profile_expanded_for_settings(report, settings)

    assert brief.mode == "deterministic"
    assert expanded.mode == "deterministic"
    assert brief.text == render_summary(report)
    assert expanded.text == render_details(report)


def test_deepseek_brief_uses_small_safe_contract_and_disables_thinking():
    client, completions = _client(_valid_brief_response())
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
    )

    result = interpreter.interpret_brief(_payload())

    assert result.mode == "llm"
    assert result.text.startswith("Короткий отчет")
    assert "В текущей выборке заметна одна основная линия" in result.text
    assert result.selected_artifact_ids
    request_call = completions.calls[0]
    assert request_call["model"] == "deepseek-v4-flash"
    assert request_call["response_format"] == {"type": "json_object"}
    assert request_call["extra_body"] == {"thinking": {"type": "disabled"}}
    request = json.loads(request_call["messages"][1]["content"])
    assert request["task"] == "render_evidence_bound_profile_brief"
    assert set(request["expected_output"]) == {
        "synthesis",
        "artifact_ids",
        "next_question",
    }
    serialized = request_call["messages"][1]["content"]
    assert "sections" not in request["expected_output"]
    assert "map_focus" not in serialized
    assert "allowed_map_roles" not in serialized
    _assert_safe_request(serialized)


def test_deepseek_profile_records_safe_usage_metadata():
    recorded = []
    client, _ = _client(
        _valid_brief_response(),
        usage=SimpleNamespace(
            prompt_tokens=30,
            completion_tokens=10,
            total_tokens=40,
        ),
    )
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
        usage_recorder=lambda *values: recorded.append(values),
    )

    interpreter.interpret_brief(_payload())

    assert recorded == [(30, 10, 40)]


def test_deepseek_expanded_uses_separate_contract_and_brief_focus():
    client, completions = _client(_valid_expanded_response())
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
    )

    result = interpreter.interpret_expanded(
        _payload(),
        brief_artifact_ids=("pattern:dominant_motif", "pattern:missing"),
    )

    assert result.mode == "llm"
    assert result.text.startswith("Подробный отчет")
    assert "Основная линия" in result.text
    request_call = completions.calls[0]
    assert request_call["extra_body"] == {"thinking": {"type": "disabled"}}
    request = json.loads(request_call["messages"][1]["content"])
    assert request["task"] == "render_evidence_bound_profile_expanded"
    assert request["brief_focus_artifact_ids"] == ["pattern:dominant_motif"]
    assert set(request["expected_output"]) == {
        "sections",
        "next_question",
        "limitations",
    }
    serialized = request_call["messages"][1]["content"]
    assert "map_focus" not in serialized
    _assert_safe_request(serialized)


def test_brief_and_expanded_are_two_provider_calls():
    client, completions = _client(
        _valid_brief_response(),
        _valid_expanded_response(),
    )
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
    )

    brief = interpreter.interpret_brief(_payload())
    expanded = interpreter.interpret_expanded(
        _payload(),
        brief_artifact_ids=brief.selected_artifact_ids,
    )

    assert brief.mode == "llm"
    assert expanded.mode == "llm"
    assert len(completions.calls) == 2
    tasks = [
        json.loads(call["messages"][1]["content"])["task"]
        for call in completions.calls
    ]
    assert tasks == [
        "render_evidence_bound_profile_brief",
        "render_evidence_bound_profile_expanded",
    ]


def test_brief_failure_does_not_prevent_expanded_success(tmp_path):
    report = _report()
    unsafe = json.loads(_valid_brief_response())
    unsafe["synthesis"] = "Это значит устойчивый диагноз. Другой вариант подтверждает вывод."
    brief_client, _ = _client(json.dumps(unsafe, ensure_ascii=False))
    expanded_client, _ = _client(_valid_expanded_response())

    brief = interpret_profile_brief_for_settings(
        report,
        _production_settings(),
        client=brief_client,
        journal_log=JournalLog(tmp_path / "journal.jsonl"),
    )
    expanded = interpret_profile_expanded_for_settings(
        report,
        _production_settings(),
        client=expanded_client,
        journal_log=JournalLog(tmp_path / "journal.jsonl"),
    )

    assert brief.mode == "deterministic"
    assert brief.fallback_reason == "unsafe_or_low_quality"
    assert expanded.mode == "llm"
    assert expanded.fallback_reason is None


def test_expanded_duplicate_section_falls_back_without_changing_brief():
    response = json.loads(_valid_expanded_response())
    response["sections"][1]["kind"] = "main_pattern"
    expanded_client, _ = _client(json.dumps(response, ensure_ascii=False))

    brief = interpret_profile_brief_for_settings(
        _report(),
        _production_settings(),
        client=_client(_valid_brief_response())[0],
    )
    expanded = interpret_profile_expanded_for_settings(
        _report(),
        _production_settings(),
        brief_artifact_ids=brief.selected_artifact_ids,
        client=expanded_client,
    )

    assert brief.mode == "llm"
    assert expanded.mode == "deterministic"
    assert expanded.fallback_reason == "unsafe_or_low_quality"


def test_brief_invalid_json_falls_back_with_safe_journal(tmp_path):
    client, _ = _client("not-json")
    journal_path = tmp_path / "journal.jsonl"

    result = interpret_profile_brief_for_settings(
        _report(),
        _production_settings(),
        client=client,
        journal_log=JournalLog(journal_path),
    )

    assert result.mode == "deterministic"
    assert result.fallback_reason == "invalid_schema"
    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["event_type"] == "profile_interpreter.brief_fallback"
    assert event["details"]["surface"] == "brief"
    assert event["details"]["parser_stage"] == "json_decode"
    assert "not-json" not in journal_path.read_text(encoding="utf-8")


def test_expanded_schema_mismatch_is_scoped_to_expanded(tmp_path):
    response = json.loads(_valid_expanded_response())
    response["next_question"] = "private generated question"
    response["unexpected private prose"] = "private generated value"
    client, _ = _client(json.dumps(response, ensure_ascii=False))
    journal_path = tmp_path / "journal.jsonl"

    result = interpret_profile_expanded_for_settings(
        _report(),
        _production_settings(),
        client=client,
        journal_log=JournalLog(journal_path),
    )

    assert result.mode == "deterministic"
    assert result.fallback_reason == "invalid_schema"
    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["event_type"] == "profile_interpreter.expanded_fallback"
    assert event["details"]["surface"] == "expanded"
    assert event["details"]["unexpected_top_level_count"] == 1
    journal_text = journal_path.read_text(encoding="utf-8")
    assert "private generated question" not in journal_text
    assert "unexpected private prose" not in journal_text


def test_unsupported_number_has_surface_specific_safe_diagnostics(tmp_path):
    response = json.loads(_valid_brief_response())
    response["synthesis"] = (
        "Этот переход встретился 99 раз. Другой вариант также присутствует."
    )
    client, _ = _client(json.dumps(response, ensure_ascii=False))
    journal_path = tmp_path / "journal.jsonl"

    result = interpret_profile_brief_for_settings(
        _report(),
        _production_settings(),
        client=client,
        journal_log=JournalLog(journal_path),
    )

    assert result.fallback_reason == "unsupported_fact"
    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["details"]["numeric_mismatches"] == [
        {
            "field_path": "brief.synthesis",
            "numbers": ["99"],
            "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
        }
    ]
    assert "Этот переход" not in journal_path.read_text(encoding="utf-8")


def test_global_sample_count_gets_deterministic_evidence_ref():
    response = json.loads(_valid_brief_response())
    response["synthesis"] = (
        "В текущей выборке есть 3 эпизода. "
        "Другой вариант показывает, что различие требует наблюдения."
    )
    client, _ = _client(json.dumps(response, ensure_ascii=False))

    result = interpret_profile_brief_for_settings(
        _report(),
        _production_settings(),
        client=client,
    )

    assert result.mode == "llm"
    assert result.interpretation is not None
    assert "evidence:sample" in result.interpretation.brief.artifact_ids


def test_missing_config_falls_back_independently_for_both_surfaces(tmp_path):
    settings = load_settings(
        {"TELEGRAM_BOT_TOKEN": "token", "M3_APP_MODE": "production"}
    )
    journal_path = tmp_path / "journal.jsonl"

    brief = interpret_profile_brief_for_settings(
        _report(),
        settings,
        journal_log=JournalLog(journal_path),
    )
    expanded = interpret_profile_expanded_for_settings(
        _report(),
        settings,
        journal_log=JournalLog(journal_path),
    )

    assert brief.fallback_reason == "missing_key_or_model"
    assert expanded.fallback_reason == "missing_key_or_model"
    events = _read_jsonl(journal_path)
    assert [event["details"]["surface"] for event in events] == [
        "brief",
        "expanded",
    ]


def test_insufficient_material_skips_provider_for_each_surface(tmp_path):
    client, completions = _client(_valid_brief_response(), _valid_expanded_response())
    journal_path = tmp_path / "journal.jsonl"

    brief = interpret_profile_brief_for_settings(
        _single_pattern_report(),
        _production_settings(),
        client=client,
        journal_log=JournalLog(journal_path),
    )
    expanded = interpret_profile_expanded_for_settings(
        _single_pattern_report(),
        _production_settings(),
        client=client,
        journal_log=JournalLog(journal_path),
    )

    assert brief.fallback_reason == "insufficient_interpretation_material"
    assert expanded.fallback_reason == "insufficient_interpretation_material"
    assert completions.calls == []


def test_success_journal_is_surface_scoped_and_excludes_generated_copy(tmp_path):
    client, _ = _client(_valid_brief_response(), _valid_expanded_response())
    journal_path = tmp_path / "journal.jsonl"
    interpreter = DeepSeekProfileInterpreter(
        api_key="test",
        model="deepseek-v4-flash",
        client=client,
    )

    brief = interpreter.interpret_brief(
        _payload(),
        journal_log=JournalLog(journal_path),
    )
    interpreter.interpret_expanded(
        _payload(),
        brief_artifact_ids=brief.selected_artifact_ids,
        journal_log=JournalLog(journal_path),
    )

    events = _read_jsonl(journal_path)
    assert [event["details"]["surface"] for event in events] == [
        "brief",
        "expanded",
    ]
    assert all(event["details"]["thinking"] == "disabled" for event in events)
    assert events[1]["counts"]["section_count"] == 2
    assert "Основная линия" not in journal_path.read_text(encoding="utf-8")


def test_provider_timeout_falls_back_only_requested_surface():
    client, _ = _client(error=TimeoutError("slow provider"))

    result = interpret_profile_expanded_for_settings(
        _report(),
        _production_settings(),
        client=client,
    )

    assert result.mode == "deterministic"
    assert result.fallback_reason == "provider_timeout"


def test_profile_text_guard_blocks_internal_and_safety_terms():
    assert "payload" in profile_text_violations("payload", "")
    assert "диагноз" in profile_text_violations("это диагноз", "")
    assert "проаннотированы" in profile_text_violations("эпизоды проаннотированы", "")


def test_profile_text_guard_allows_user_facing_analytical_terms():
    text = (
        "В рамках сценария триггер сменился, а подход приводит к компенсации исхода, "
        "потому что этот переход обусловлен наблюдаемой развилкой. Это значит, что "
        "паттерн пока устойчив."
    )

    assert profile_text_violations(text) == ()


def test_profile_text_guard_still_blocks_explicit_stable_trait_claims():
    assert "вам свойственно" in profile_text_violations("Вам свойственно избегать.")
    assert "вы всегда" in profile_text_violations("Вы всегда реагируете одинаково.")


def _assert_safe_request(serialized: str) -> None:
    assert "source_quote" not in serialized
    assert "episode-" not in serialized
    assert "They will judge me" not in serialized
    assert "Group chat" not in serialized
    assert "transcript" not in serialized


def _valid_brief_response() -> str:
    return json.dumps(
        {
            "synthesis": (
                "В текущей выборке заметна одна основная линия реакции. "
                "При сходных условиях встречается и другой вариант, поэтому различие пока требует наблюдения."
            ),
            "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
            "next_question": {
                "text": "Что появляется непосредственно перед расхождением вариантов?",
                "artifact_ids": ["question:fork", "exception:fork"],
            },
        },
        ensure_ascii=False,
    )


def _valid_expanded_response() -> str:
    return json.dumps(
        {
            "sections": [
                {
                    "kind": "main_pattern",
                    "title": "Основная линия",
                    "synthesis": (
                        "Повторяющийся сценарий соседствует с развилкой, где похожая основа заканчивается по-разному."
                    ),
                    "artifact_ids": ["pattern:dominant_motif", "exception:fork"],
                    "evidence_note": "Оба наблюдения поддержаны текущей выборкой.",
                },
                {
                    "kind": "outcomes",
                    "title": "Наблюдаемые последствия",
                    "synthesis": (
                        "После реакций повторяется один из отмеченных вариантов завершения."
                    ),
                    "artifact_ids": ["pattern:outcome_pattern"],
                    "evidence_note": None,
                },
            ],
            "next_question": {
                "text": "Что появляется непосредственно перед расхождением вариантов?",
                "artifact_ids": ["question:fork", "exception:fork"],
            },
            "limitations": [
                {
                    "text": "Вывод ограничен текущей выборкой.",
                    "artifact_ids": ["evidence:sample"],
                }
            ],
        },
        ensure_ascii=False,
    )


def _production_settings():
    return load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "DEEPSEEK_API_KEY": "test",
            "M3_PROFILE_LLM_MODEL": "deepseek-v4-flash",
        }
    )


def _payload():
    return build_insight_payload(_report())


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


def _single_pattern_report():
    return build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
        ],
        coverage=AnnotationCoverage(
            observed_count=2,
            annotation_row_count=2,
            annotated_count=2,
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
