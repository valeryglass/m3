from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.spatial_payload import build_spatial_payload
from app.schemas.episode import Episode
from tests.test_insight_payload import _episode


def test_spatial_payload_projects_insight_payload_without_report_text():
    report = build_report(
        [
            _load(_episode("episode-20260430-1", behavior_type="avoid")),
            _load(_episode("episode-20260430-2", behavior_type="avoid")),
            _load(_episode("episode-20260430-3", behavior_type="avoid")),
            _load(_episode("episode-20260430-4", behavior_type="approach")),
        ]
    )

    spatial = build_spatial_payload(build_insight_payload(report))
    data = spatial.to_dict()

    assert data["kind"] == "spatial_payload"
    assert data["source_kind"] == "insight_payload"
    assert data["paths"][0]["role"] == "dominant_motif"
    assert data["paths"][0]["signature"] == {
        "trigger": "social",
        "emotion": "страх",
        "behavior": "avoid",
    }
    assert data["markers"][0]["role"] == "fork"
    assert data["markers"][1]["role"] == "counterexample"
    assert "Развилка реакций" not in str(data)


def _load(data):
    return Episode.model_validate(data)
