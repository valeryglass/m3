from collections import Counter

from app.analytics_loader import AnnotationCoverage
from app.graph_report import EpisodeSignature, GraphReport
from app.pattern_metrics import (
    behavior_fork_episode_ids,
    behavior_forks,
    contrast_candidates,
    counterexample_candidates,
    loop_counter,
    loop_episode_ids,
    outcome_episode_ids,
    outcome_pattern_counter,
    sorted_counter_items,
    top_loop,
    trigger_counter,
)


def test_pattern_counts_are_distinct_episode_counts_with_provenance():
    report = _report(
        _signature(
            "episode-20260601-1",
            triggers=("social", "social"),
            emotions=("fear",),
            behaviors=("avoid",),
            short_outcomes=("relief",),
        ),
        _signature(
            "episode-20260602-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid", "approach"),
            short_outcomes=("relief",),
        ),
    )

    assert trigger_counter(report) == Counter({"social": 2})
    assert loop_counter(report)[("social", "fear", "avoid")] == 2
    assert loop_episode_ids(report)[("social", "fear", "avoid")] == frozenset(
        {"episode-20260601-1", "episode-20260602-1"}
    )
    assert behavior_forks(report)[("social", "fear")] == Counter(
        {"avoid": 2, "approach": 1}
    )
    assert behavior_fork_episode_ids(report)[("social", "fear")]["approach"] == (
        frozenset({"episode-20260602-1"})
    )
    assert outcome_pattern_counter(report)[("avoid", "relief")] == 2
    assert outcome_episode_ids(report)[("avoid", "short_term", "relief")] == (
        frozenset({"episode-20260601-1", "episode-20260602-1"})
    )


def test_pattern_ranking_is_deterministic():
    report = _report(
        _signature(
            "episode-20260601-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid", "approach"),
        )
    )

    assert top_loop(report) == (("social", "fear", "approach"), 1)
    assert sorted_counter_items(Counter({"b": 1, "a": 1})) == [("a", 1), ("b", 1)]


def test_counterexample_requires_dominance_and_keeps_episode_provenance():
    report = _report(
        *[
            _signature(
                f"episode-2026060{index}-1",
                triggers=("social",),
                emotions=("fear",),
                behaviors=(behavior,),
            )
            for index, behavior in enumerate(
                ("avoid", "avoid", "avoid", "approach"), start=1
            )
        ]
    )

    candidate = counterexample_candidates(report)[0]

    assert candidate.base == ("social", "fear")
    assert candidate.dominant_behavior == "avoid"
    assert candidate.dominant_episode_ids == (
        "episode-20260601-1",
        "episode-20260602-1",
        "episode-20260603-1",
    )
    assert candidate.alternative_behavior == "approach"
    assert candidate.alternative_episode_ids == ("episode-20260604-1",)


def test_counterexample_rejects_weak_or_tied_dominance():
    weak = _report(
        _signature(
            "episode-20260601-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid",),
        ),
        _signature(
            "episode-20260602-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid",),
        ),
        _signature(
            "episode-20260603-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("approach",),
        ),
    )
    tied = _report(
        *[
            _signature(
                f"episode-2026060{index}-1",
                triggers=("social",),
                emotions=("fear",),
                behaviors=(behavior,),
            )
            for index, behavior in enumerate(
                ("avoid", "avoid", "avoid", "approach", "approach", "approach"),
                start=1,
            )
        ]
    )

    assert counterexample_candidates(weak) == ()
    assert counterexample_candidates(tied) == ()


def test_counterexample_selects_strongest_alternative_deterministically():
    report = _report(
        *[
            _signature(
                f"episode-202606{index:02d}-1",
                triggers=("social",),
                emotions=("fear",),
                behaviors=(behavior,),
            )
            for index, behavior in enumerate(
                ("avoid", "avoid", "avoid", "avoid", "freeze", "approach"),
                start=1,
            )
        ]
    )

    candidate = counterexample_candidates(report)[0]

    assert candidate.alternative_behavior == "approach"


def test_contrast_requires_two_episodes_per_side_and_keeps_provenance():
    report = _report(
        *[
            _signature(
                f"episode-2026060{index}-1",
                triggers=("social",),
                emotions=(emotion,),
                behaviors=("avoid",),
            )
            for index, emotion in enumerate(
                ("fear", "fear", "anger", "anger"), start=1
            )
        ]
    )

    candidate = contrast_candidates(report)[0]

    assert candidate.trigger == "social"
    assert candidate.behavior == "avoid"
    assert candidate.left_emotion == "anger"
    assert candidate.left_episode_ids == (
        "episode-20260603-1",
        "episode-20260604-1",
    )
    assert candidate.right_emotion == "fear"
    assert candidate.right_episode_ids == (
        "episode-20260601-1",
        "episode-20260602-1",
    )


def test_contrast_ignores_unsupported_side():
    report = _report(
        _signature(
            "episode-20260601-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid",),
        ),
        _signature(
            "episode-20260602-1",
            triggers=("social",),
            emotions=("fear",),
            behaviors=("avoid",),
        ),
        _signature(
            "episode-20260603-1",
            triggers=("social",),
            emotions=("anger",),
            behaviors=("avoid",),
        ),
    )

    assert contrast_candidates(report) == ()


def _report(*signatures: EpisodeSignature) -> GraphReport:
    return GraphReport(
        total_episodes=len(signatures),
        coverage=AnnotationCoverage(
            observed_count=len(signatures),
            annotation_row_count=len(signatures),
            annotated_count=len(signatures),
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
        graph_ready=signatures,
        readiness=(),
        emotion_signatures=Counter(),
        behavior_signatures=Counter(),
        cognition_signatures=Counter(),
        trigger_emotion_signatures=Counter(),
        cognition_behavior_signatures=Counter(),
        emotion_behavior_signatures=Counter(),
        relation_type_signatures=Counter(),
    )


def _signature(
    episode_id: str,
    *,
    triggers: tuple[str, ...],
    emotions: tuple[str, ...],
    behaviors: tuple[str, ...],
    short_outcomes: tuple[str, ...] = (),
    long_outcomes: tuple[str, ...] = (),
) -> EpisodeSignature:
    return EpisodeSignature(
        episode_id=episode_id,
        source="telegram-chat:test",
        triggers=triggers,
        cognitions=(),
        emotions=emotions,
        behaviors=behaviors,
        short_outcomes=short_outcomes,
        long_outcomes=long_outcomes,
        relation_types=(),
        short_term_consequence="",
        long_term_consequence="",
    )
