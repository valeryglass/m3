from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.report_view_model import (
    build_report_view_model,
    render_details_view,
    render_summary_view,
)
from tests.test_user_report import _episode, _load_episode


def test_report_view_model_builds_summary_and_details_sections():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260430-3", behavior_type="approach")),
        ]
    )
    model = build_report_view_model(build_insight_payload(report))

    assert model.kind == "report_view_model"
    assert model.sample_line == "В выборке: 3 эпизода."
    assert [section.kind for section in model.summary_sections] == [
        "main_pattern",
        "choice_point",
        "next_question",
    ]
    assert [section.kind for section in model.details_sections][:2] == [
        "main_pattern",
        "choice_point",
    ]


def test_report_view_model_preserves_evidence_support_and_questions():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
        ]
    )
    model = build_report_view_model(build_insight_payload(report))
    main = model.details_sections[0]

    assert main.title == "Главный повторяющийся сценарий"
    assert main.evidence == ("Поддержка: 2 эпизода.",)
    assert main.question == "Где в этой цепочке появляется выбор реакции?"


def test_report_view_model_rendering_hides_raw_internal_labels():
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
    model = build_report_view_model(build_insight_payload(report))
    text = render_summary_view(model) + "\n" + render_details_view(model)

    assert "компенсировать" in text
    assert "атаковать" in text
    assert "смешанный итог" in text
    assert "compensate" not in text
    assert "neutral_mixed" not in text
    assert "source_quote" not in text


def test_report_view_model_uses_plain_text_dividers_for_header_and_sections():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
        ]
    )
    model = build_report_view_model(build_insight_payload(report))

    summary = render_summary_view(model)
    details = render_details_view(model)

    assert summary.startswith("Короткий отчет\n────────────\nВ выборке: 2 эпизода.")
    assert details.startswith("Подробный отчет\n────────────\nВ выборке: 2 эпизода.")
    assert "────────────\nГлавный повторяющийся сценарий\n\n" in summary
    assert "────────────\nГлавный повторяющийся сценарий\n\n" in details
    assert "────────────\n\n────────────" not in summary
    assert "────────────\n\n────────────" not in details
