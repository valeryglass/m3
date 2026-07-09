from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.report_entities import REPORT_ENTITY_KINDS, build_report_entities
from app.schemas.episode import Episode
from tests.test_insight_payload import _episode


def test_report_entities_project_insight_payload_with_stable_kinds():
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

    report_entities = build_report_entities(payload)
    by_role = {entity.role: entity for entity in report_entities.entities}

    assert report_entities.kind == "report_entities"
    assert set(REPORT_ENTITY_KINDS) == {
        "evidence",
        "pattern",
        "exception",
        "change",
        "finding",
        "question",
        "gap",
    }
    assert by_role["dominant_motif"].kind == "pattern"
    assert by_role["dominant_motif"].support_count == 3
    assert by_role["dominant_motif"].episode_ids == (
        "episode-20260430-1",
        "episode-20260430-2",
        "episode-20260430-3",
    )
    assert by_role["fork"].kind == "exception"
    assert by_role["next_observation"].kind == "question"
    assert by_role["sample"].kind == "evidence"


def test_report_entities_do_not_contain_user_report_copy():
    payload = build_insight_payload(build_report([_load(_episode("episode-20260430-1"))]))

    rendered = str(build_report_entities(payload).to_dict()).lower()

    assert "короткий отчет" not in rendered
    assert "подробный отчет" not in rendered
    assert "диагноз" not in rendered


def _load(data):
    return Episode.model_validate(data)
