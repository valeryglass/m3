from app.analytics_loader import AnnotationCoverage
from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.report_cards import build_report_cards
from app.schemas.episode import Episode
from tests.test_insight_payload import _episode


def test_report_cards_are_built_from_insight_payload():
    payload = build_insight_payload(
        build_report(
            [
                _load(_episode("episode-20260430-1", behavior_type="avoid")),
                _load(_episode("episode-20260430-2", behavior_type="avoid")),
                _load(_episode("episode-20260430-3", behavior_type="avoid")),
                _load(_episode("episode-20260430-4", behavior_type="approach")),
            ]
        )
    )

    cards = build_report_cards(payload)

    assert [card.kind for card in cards[:4]] == [
        "main_pattern",
        "choice_point",
        "counterexample",
        "outcome_pattern",
    ]
    assert cards[0].title == "Главный повторяющийся сценарий"
    assert cards[0].claim == "контакт с людьми -> страх -> дистанцироваться"
    assert cards[1].title == "Точка выбора"
    assert cards[2].title == "Менее частый вариант"
    assert cards[-1].kind == "next_question"


def test_report_cards_surface_partial_coverage_as_low_priority_status():
    payload = build_insight_payload(
        build_report(
            [_load(_episode("episode-20260430-1"))],
            coverage=AnnotationCoverage(
                observed_count=2,
                annotation_row_count=1,
                annotated_count=1,
                pending_count=1,
                pending_episode_ids=("episode-20260430-2",),
                coverage="partial",
            ),
        )
    )

    cards = build_report_cards(payload)
    status = next(card for card in cards if card.kind == "sample_status")

    assert status.title == "О данных"
    assert status.claim == "Учтено 1 из 2 эпизодов."
    assert status.evidence == ("1 ждут обработки.",)


def _load(data):
    return Episode.model_validate(data)
