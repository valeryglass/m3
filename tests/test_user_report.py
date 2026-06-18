from app.analytics_loader import AnnotationCoverage
from app.graph_report import build_report
from app.schemas.episode import Episode
from app.user_report import build_user_report, render_details, render_summary


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
)


def test_summary_renders_from_minimal_valid_report():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260508-1", behavior_type="approach")),
        ]
    )

    text = render_summary(report)

    assert text.startswith("Короткий отчет")
    assert "В выборке: 3 эпизода." in text
    assert "контакт с людьми" in text
    assert "страх" in text
    assert "дистанцироваться" in text
    assert "контакт с людьми -> страх -> дистанцироваться" in text
    assert "в этих данных видно" in text
    assert "Может быть полезно понаблюдать" in text
    assert 350 <= len(text) <= 800


def test_details_render_and_skip_missing_sections():
    report = build_report(
        [_load_episode(_episode("episode-20260430-1", outcome_annotations=False))]
    )

    text = render_details(report)

    assert text.startswith("Подробный отчет")
    assert "Текущая картина" in text
    assert "Наблюдаемые итоги" not in text
    assert "Устойчивые сценарии" not in text


def test_build_user_report_matches_direct_helpers():
    report = build_report([_load_episode(_episode("episode-20260430-1"))])

    user_report = build_user_report(report)

    assert user_report.summary_text == render_summary(report)
    assert user_report.details_text == render_details(report)


def test_rendered_text_hides_internal_terms_and_diagnostic_wording():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
        ]
    )
    text = render_summary(report) + "\n" + render_details(report)
    lowered = text.lower()

    for term in INTERNAL_TERMS:
        assert term not in lowered
    for wording in FORBIDDEN_WORDING:
        assert wording not in lowered


def test_details_show_repeated_scenario_with_friendly_mappings():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260430-3", behavior_type="freeze")),
        ]
    )

    text = render_details(report)

    assert "контакт с людьми -> страх -> дистанцироваться" in text
    assert "- контакт с людьми -> страх" in text
    assert "- варианты: дистанцироваться (2), замирать (1)" in text


def test_common_raw_labels_are_rendered_as_friendly_text():
    report = build_report(
        [
            _load_episode(
                _episode(
                    "episode-20260430-1",
                    behavior_type="compensate",
                    outcome_type="neutral_mixed",
                )
            ),
            _load_episode(
                _episode(
                    "episode-20260430-2",
                    behavior_type="attack",
                    outcome_type="learning",
                )
            ),
        ]
    )

    text = render_summary(report) + "\n" + render_details(report)

    assert "компенсировать" in text
    assert "атаковать" in text
    assert "смешанный итог" in text
    assert "опыт/понимание" in text
    assert "compensate" not in text
    assert "neutral_mixed" not in text
    assert "learning" not in text


def test_partial_coverage_renders_subtle_user_note():
    report = build_report(
        [_load_episode(_episode("episode-20260430-1"))],
        coverage=AnnotationCoverage(
            observed_count=2,
            annotation_row_count=1,
            annotated_count=1,
            pending_count=1,
            pending_episode_ids=("episode-20260430-2",),
            coverage="partial",
        ),
    )

    text = render_summary(report) + "\n" + render_details(report)

    assert "Учтено 1 из 2 эпизодов; 1 ждут обработки." in text
    assert "episode-20260430-2" not in text


def test_details_surface_supported_counterexample_cautiously():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1", behavior_type="avoid")),
            _load_episode(_episode("episode-20260430-2", behavior_type="avoid")),
            _load_episode(_episode("episode-20260430-3", behavior_type="avoid")),
            _load_episode(_episode("episode-20260430-4", behavior_type="approach")),
        ]
    )

    text = render_details(report)

    assert "Менее частый вариант" in text
    assert (
        "в этой выборке чаще: контакт с людьми -> страх -> "
        "дистанцироваться (3)"
    ) in text
    assert (
        "реже встречалось: контакт с людьми -> страх -> идти в действие (1)"
    ) in text


def _load_episode(data):
    return Episode.model_validate(data)


def _episode(
    episode_id,
    *,
    behavior_type="avoid",
    outcome_annotations=True,
    outcome_type="relief",
):
    nodes = [
        {
            "id": "node-1",
            "node_origin": "observed",
            "kind": "cognition",
            "text": "They will judge me.",
            "source_field": "observed.automatic_thought",
            "source_quote": "they will judge me",
            "confidence": 0.9,
        }
    ]
    outcomes = []
    if outcome_annotations:
        nodes.append(
            {
                "id": "node-2",
                "node_origin": "observed",
                "kind": "short_outcome",
                "text": "Relief.",
                "source_field": "observed.short_term_consequence",
                "source_quote": "Relief.",
                "confidence": 0.85,
            }
        )
        outcomes = [
            {
                "id": "outcome-annotation-1",
                "node_id": "node-2",
                "horizon": "short_term",
                "type": outcome_type,
                "source_field": "observed.short_term_consequence",
                "source_quote": "Relief.",
                "confidence": 0.85,
            }
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
            "outcome_annotations": outcomes,
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
