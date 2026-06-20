from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.map_payload import build_map_payload
from app.schemas.episode import Episode
from app.user_report import render_details, render_summary
from tests.test_insight_payload import _episode


def test_insight_payload_partitions_compact_analytics_by_primary_domain():
    episodes = [
        _load(_with_domains(_episode("episode-20260430-1"), "work_study")),
        _load(_with_domains(_episode("episode-20260430-2"), "work_study")),
        _load(
            _with_domains(
                _episode("episode-20260430-3", behavior_type="approach"),
                "work_study",
                "social_public",
            )
        ),
        _load(
            _with_domains(
                _episode("episode-20260430-4"),
                "close_relationships_family",
            )
        ),
    ]

    payload = build_insight_payload(build_report(episodes))

    assert payload.version == "0.2"
    assert [
        (item.role, item.domain, item.support_count)
        for item in payload.domain_distribution
    ] == [
        ("primary", "work_study", 3),
        ("primary", "close_relationships_family", 1),
        ("secondary", "social_public", 1),
    ]
    work = next(
        item for item in payload.domain_summaries if item.domain == "work_study"
    )
    relationship = next(
        item
        for item in payload.domain_summaries
        if item.domain == "close_relationships_family"
    )
    assert work.support_count == 3
    assert work.dominant_motif is not None
    assert work.dominant_motif.support_count == 2
    assert work.main_fork is not None
    assert work.main_fork.support_count == 3
    assert work.outcome_patterns
    assert relationship.support_count == 1
    assert set(work.episode_ids).isdisjoint(relationship.episode_ids)


def test_map_payload_embeds_domain_analytics_without_report_changes():
    episode = _load(
        _with_domains(
            _episode("episode-20260430-1"),
            "projects_creativity",
        )
    )

    payload = build_map_payload([episode], source="telegram-chat:123")

    assert payload["version"] == "0.2"
    assert payload["analytics"]["insight_payload"]["version"] == "0.2"
    assert payload["analytics"]["insight_payload"]["domain_distribution"] == (
        {
            "domain": "projects_creativity",
            "role": "primary",
            "support_count": 1,
            "episode_ids": ("episode-20260430-1",),
        },
    )


def test_domain_annotations_do_not_change_profile_report_text():
    plain = _load(_episode("episode-20260430-1"))
    enriched = _load(
        _with_domains(
            _episode("episode-20260430-1"),
            "social_public",
        )
    )

    assert render_summary(build_report([enriched])) == render_summary(
        build_report([plain])
    )
    assert render_details(build_report([enriched])) == render_details(
        build_report([plain])
    )


def _with_domains(data, primary, secondary=None):
    data["derived"]["domain_annotations"] = [
        {
            "id": "domain-annotation-1",
            "domain": primary,
            "role": "primary",
            "method": "explicit_review",
            "source_field": "observed.situation",
            "source_quote": data["observed"]["situation"]["source_quote"],
            "confidence": 0.9,
        }
    ]
    if secondary is not None:
        data["derived"]["domain_annotations"].append(
            {
                "id": "domain-annotation-2",
                "domain": secondary,
                "role": "secondary",
                "method": "explicit_review",
                "source_field": "observed.situation",
                "source_quote": data["observed"]["situation"]["source_quote"],
                "confidence": 0.8,
            }
        )
    return data


def _load(data):
    return Episode.model_validate(data)
