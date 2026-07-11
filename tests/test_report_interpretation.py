import json
from dataclasses import replace

from app.graph_report import build_report
from app.insight_payload import build_insight_payload
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
from tests.test_user_report import _episode, _load_episode


def test_interpretation_registry_is_safe_deduplicated_and_report_only():
    interpretation_input = _interpretation_input()
    serialized = json.dumps(interpretation_input.to_dict(), ensure_ascii=False)
    artifacts = interpretation_input.artifacts_by_id()

    assert interpretation_input.kind == "report_interpretation_input"
    assert "pattern:dominant_motif" in artifacts
    assert "exception:fork" in artifacts
    assert "pattern:outcome_pattern" in artifacts
    assert "finding:dominant_motif_observation" not in artifacts
    assert "allowed_map_roles" not in serialized
    assert "episode-" not in serialized
    assert "source_quote" not in serialized
    assert "They will judge me" not in serialized
    assert "Group chat" not in serialized


def test_interpretation_requires_three_analytical_artifacts_and_a_pattern():
    interpretation_input = _interpretation_input()

    assert report_interpretation_is_eligible(interpretation_input)
    reduced = replace(
        interpretation_input,
        artifacts=tuple(
            artifact
            for artifact in interpretation_input.artifacts
            if artifact.artifact_id != "pattern:outcome_pattern"
        ),
    )
    assert not report_interpretation_is_eligible(reduced)


def test_split_interpretations_render_distinct_brief_and_expanded_views():
    interpretation_input = _interpretation_input()

    brief = render_interpretation_brief(
        interpretation_input,
        _valid_brief_interpretation(),
    )
    expanded = render_interpretation_expanded(
        interpretation_input,
        _valid_expanded_interpretation(),
    )

    assert brief.startswith("Короткий отчет\n────────────\nВ выборке: 3 эпизода.")
    assert brief.count("────────────") == 3
    assert "────────────\nВопрос:" in brief
    assert "Основная линия" not in brief
    assert expanded.startswith("Подробный отчет\n────────────\nВ выборке: 3 эпизода.")
    assert "────────────\nОсновная линия\n\n" in expanded
    assert "────────────\nОграничения\n\n" in expanded
    assert "────────────\nЧто наблюдать дальше\n\n" in expanded
    assert "────────────\n\n────────────" not in expanded
    assert "Основная линия" in expanded
    assert "Наблюдаемые последствия" in expanded
    assert expanded.count("Что наблюдать дальше") == 1
    assert "Вопрос:" not in expanded


def test_valid_brief_and_expanded_pass_independent_guards():
    interpretation_input = _interpretation_input()

    assert brief_interpretation_violations(
        interpretation_input,
        _valid_brief_interpretation(),
    ) == ()
    assert expanded_interpretation_violations(
        interpretation_input,
        _valid_expanded_interpretation(),
    ) == ()


def test_brief_rejects_unknown_refs_and_reports_numeric_mismatch():
    interpretation_input = _interpretation_input()
    interpretation = _valid_brief_interpretation()
    invalid = replace(
        interpretation,
        brief=replace(
            interpretation.brief,
            synthesis=(
                "Этот переход встретился 99 раз. "
                "Другой вариант остается в текущей выборке."
            ),
            artifact_ids=("pattern:missing",),
        ),
    )

    violations = brief_interpretation_violations(interpretation_input, invalid)

    assert "artifact_ref_mismatch" in violations


def test_numeric_mismatch_names_surface_field_number_and_safe_refs():
    interpretation_input = _interpretation_input()
    interpretation = _valid_brief_interpretation()
    numbered = replace(
        interpretation,
        brief=replace(
            interpretation.brief,
            synthesis=(
                "Этот переход встретился 99 раз. "
                "Другой вариант остается в текущей выборке."
            ),
        ),
    )

    mismatches = report_interpretation_numeric_mismatches(
        interpretation_input,
        numbered,
    )

    assert tuple(item.to_dict() for item in mismatches) == (
        {
            "field_path": "brief.synthesis",
            "numbers": ("99",),
            "artifact_ids": ("pattern:dominant_motif", "exception:fork"),
        },
    )


def test_global_sample_evidence_is_attached_independently_to_both_surfaces():
    interpretation_input = _interpretation_input()
    brief = _valid_brief_interpretation()
    expanded = _valid_expanded_interpretation()
    brief = replace(
        brief,
        brief=replace(
            brief.brief,
            synthesis=(
                "В текущей выборке есть 3 эпизода. "
                "Другой вариант оставляет различие открытым."
            ),
        ),
    )
    expanded = replace(
        expanded,
        sections=(
            replace(
                expanded.sections[0],
                synthesis="В выборке из 3 эпизодов основная линия имеет развилку.",
            ),
            *expanded.sections[1:],
        ),
    )

    normalized_brief = attach_global_sample_evidence(interpretation_input, brief)
    normalized_expanded = attach_global_sample_evidence(
        interpretation_input,
        expanded,
    )

    assert isinstance(normalized_brief, BriefReportInterpretation)
    assert "evidence:sample" in normalized_brief.brief.artifact_ids
    assert isinstance(normalized_expanded, ExpandedReportInterpretation)
    assert "evidence:sample" in normalized_expanded.sections[0].artifact_ids
    assert "unsupported_number" not in brief_interpretation_violations(
        interpretation_input,
        normalized_brief,
    )
    assert "unsupported_number" not in expanded_interpretation_violations(
        interpretation_input,
        normalized_expanded,
    )


def test_expanded_rejects_duplicate_sections_without_map_contract():
    interpretation_input = _interpretation_input()
    interpretation = _valid_expanded_interpretation()
    duplicate = replace(interpretation.sections[1], kind="main_pattern")

    violations = expanded_interpretation_violations(
        interpretation_input,
        replace(
            interpretation,
            sections=(interpretation.sections[0], duplicate),
        ),
    )

    assert "duplicate_section_kind" in violations


def _valid_brief_interpretation() -> BriefReportInterpretation:
    return BriefReportInterpretation(
        brief=InterpretationBrief(
            synthesis=(
                "В текущей выборке заметна одна основная линия реакции. "
                "При сходных условиях встречается и другой вариант, поэтому различие пока требует наблюдения."
            ),
            artifact_ids=("pattern:dominant_motif", "exception:fork"),
        ),
        next_question=InterpretationQuestion(
            text="Что появляется непосредственно перед расхождением вариантов?",
            artifact_ids=("question:fork", "exception:fork"),
        ),
    )


def _valid_expanded_interpretation() -> ExpandedReportInterpretation:
    return ExpandedReportInterpretation(
        sections=(
            InterpretationSection(
                kind="main_pattern",
                title="Основная линия",
                synthesis=(
                    "Повторяющийся сценарий соседствует с развилкой, где похожая основа заканчивается по-разному."
                ),
                artifact_ids=("pattern:dominant_motif", "exception:fork"),
                evidence_note="Оба наблюдения поддержаны текущей выборкой.",
            ),
            InterpretationSection(
                kind="outcomes",
                title="Наблюдаемые последствия",
                synthesis="После реакций повторяется один из отмеченных вариантов завершения.",
                artifact_ids=("pattern:outcome_pattern",),
            ),
        ),
        next_question=InterpretationQuestion(
            text="Что появляется непосредственно перед расхождением вариантов?",
            artifact_ids=("question:fork", "exception:fork"),
        ),
        limitations=(
            InterpretationLimitation(
                text="Вывод ограничен текущей выборкой.",
                artifact_ids=("evidence:sample",),
            ),
        ),
    )


def _interpretation_input():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260430-3", behavior_type="approach")),
        ]
    )
    return build_report_interpretation_input(build_insight_payload(report))
