from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.analytics_loader import annotation_coverage_for_episode_ids, selected_annotation_run
from app.graph_report import GraphReport, build_report, load_episodes
from app.insight_payload import build_insight_payload, require_payload_export_ready
from app.pattern_metrics import (
    WEEK_QUANT,
    loops_for_signature,
    novelty_counter,
    rarity_counter,
    safe_filename,
    stability_counter,
    surprise_counter,
    week_key,
)
from app.schemas.episode import Episode
from app.spatial_payload import build_spatial_payload


VERSION = "0.1"
SIMILARITY_VERSION = "symbolic_v1"
SIMILARITY_WEIGHTS = {
    "trigger": 0.40,
    "emotion": 0.35,
    "behavior": 0.25,
}
NEIGHBOR_THRESHOLD = 0.30
NEIGHBOR_LIMIT_PER_DISTRICT = 5
CLUSTER_THRESHOLD = 0.55
ENTITY_TYPES = (
    "district",
    "gate",
    "climate",
    "architecture",
    "road",
    "crossroads",
    "landmark",
    "destination",
)
LINK_TYPES = (
    "gate_to_district",
    "climate_to_district",
    "architecture_to_district",
    "district_to_road",
    "road_to_destination",
    "crossroads_to_district",
    "landmark_to_district",
)
DEFAULT_LIMITS = {
    "district": 12,
    "gate": 12,
    "climate": 12,
    "architecture": 12,
    "road": 12,
    "crossroads": 12,
    "landmark": 16,
    "destination": 12,
}


@dataclass
class EntitySeed:
    type: str
    key: tuple[str, ...]
    label: str
    signature: dict[str, Any]
    episode_ids: set[str]
    semantic_similarity_keys: list[str]
    suggested_map_role: str
    parent_key: tuple[str, tuple[str, ...]] | None = None
    novelty_flag: bool = False
    rarity_flag: bool = False
    surprise_flag: bool = False


@dataclass
class LinkSeed:
    type: str
    from_key: tuple[str, tuple[str, ...]]
    to_key: tuple[str, tuple[str, ...]]
    episode_ids: set[str]


def build_map_payload(
    episodes: list[Episode],
    *,
    source: str,
    limits: dict[str, int] | None = None,
    provenance: dict[str, Any] | None = None,
    coverage=None,
) -> dict[str, Any]:
    source_episodes = [episode for episode in episodes if episode.source == source]
    report = build_report(source_episodes, coverage=coverage)
    active_limits = {**DEFAULT_LIMITS, **(limits or {})}
    insight_payload = build_insight_payload(report)
    spatial_payload = build_spatial_payload(insight_payload)
    seeds = _entity_seeds(report)
    entities, key_to_id = _finalize_entities(seeds, report, active_limits)
    links = _finalize_links(_link_seeds(report), key_to_id)
    clusters, neighbors = _district_topology(entities, report)

    base_provenance = {
        "generated_from": "graph_signatures",
        "graph_ready_episode_ids": [sig.episode_id for sig in report.graph_ready],
        "skipped_episode_ids": list(report.skipped),
        "coverage": {
            "observed_count": report.coverage.observed_count,
            "annotation_row_count": report.coverage.annotation_row_count,
            "annotated_count": report.coverage.annotated_count,
            "pending_count": report.coverage.pending_count,
            "pending_episode_ids": list(report.coverage.pending_episode_ids),
            "state": report.coverage.coverage,
        },
    }
    if provenance:
        base_provenance.update(provenance)

    return {
        "kind": "map_payload",
        "version": VERSION,
        "source": source,
        "episodes": len(source_episodes),
        "timespan_quant": WEEK_QUANT,
        "similarity": {"version": SIMILARITY_VERSION},
        "analytics": {
            "source": "insight_payload",
            "insight_payload": insight_payload.to_dict(),
            "spatial_payload": spatial_payload.to_dict(),
        },
        "entities": entities,
        "links": links,
        "clusters": clusters,
        "neighbors": neighbors,
        "provenance": base_provenance,
    }


def write_map_payload(
    episodes: list[Episode],
    output_path: Path,
    *,
    source: str,
    limits: dict[str, int] | None = None,
    provenance: dict[str, Any] | None = None,
    coverage=None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_map_payload(
        episodes,
        source=source,
        limits=limits,
        provenance=provenance,
        coverage=coverage,
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write renderer-neutral map payload JSON.")
    parser.add_argument("--episode-dir", default="data/episodes")
    parser.add_argument("--annotation-run-dir", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    output = (
        Path(args.output)
        if args.output
        else Path("data/exports/map-payload") / f"{safe_filename(args.source)}.json"
    )
    episode_dir = Path(args.episode_dir)
    annotation_run_dir = Path(args.annotation_run_dir)
    episodes = load_episodes(
        episode_dir,
        annotation_run_dir=annotation_run_dir,
    )
    all_episode_ids = _episode_ids(episode_dir)
    coverage = annotation_coverage_for_episode_ids(
        {episode.id for episode in episodes if episode.source == args.source},
        annotation_run_dir=annotation_run_dir,
        known_episode_ids=all_episode_ids,
    )
    source_episodes = [episode for episode in episodes if episode.source == args.source]
    require_payload_export_ready(build_report(source_episodes, coverage=coverage))
    path = write_map_payload(
        episodes,
        output,
        source=args.source,
        coverage=coverage,
        provenance=_cli_provenance(
            episode_dir=episode_dir,
            annotation_run_dir=annotation_run_dir,
            episode_ids=all_episode_ids,
            source=args.source,
        ),
    )
    print(path.as_posix())


def _cli_provenance(
    *,
    episode_dir: Path,
    annotation_run_dir: Path,
    episode_ids: set[str],
    source: str,
) -> dict[str, Any]:
    annotation_run = selected_annotation_run(
        episode_dir,
        annotation_run_dir=annotation_run_dir,
        episode_ids=episode_ids,
    )
    provenance: dict[str, Any] = {
        "episode_dir": episode_dir.as_posix(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_scope": source,
    }
    if annotation_run is not None:
        provenance.update(
            {
                "annotation_run_id": annotation_run.manifest.annotation_run_id,
                "annotation_run_path": annotation_run.path.as_posix(),
            }
        )
    return provenance


def _episode_ids(episode_dir: Path) -> set[str]:
    episode_ids: set[str] = set()
    for path in sorted(episode_dir.glob("episode-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        episode_id = data.get("id", data.get("episode_id"))
        if isinstance(episode_id, str):
            episode_ids.add(episode_id)
    return episode_ids


def _entity_seeds(report: GraphReport) -> dict[tuple[str, tuple[str, ...]], EntitySeed]:
    seeds: dict[tuple[str, tuple[str, ...]], EntitySeed] = {}
    novelty = set(novelty_counter(report))
    rarity = set(rarity_counter(report))
    surprise = set(surprise_counter(report))

    for sig in report.graph_ready:
        for loop in loops_for_signature(sig):
            trigger, emotion, behavior = loop
            _upsert(
                seeds,
                "district",
                loop,
                f"{trigger} + {emotion} + {behavior}",
                {"trigger": trigger, "emotion": emotion, "behavior": behavior},
                sig.episode_id,
                [trigger, emotion, behavior],
                "district",
                novelty_flag=loop in novelty,
                rarity_flag=loop in rarity,
                surprise_flag=loop in surprise,
            )
            _upsert(
                seeds,
                "landmark",
                loop,
                f"{trigger} -> {emotion} -> {behavior}",
                {"trigger": trigger, "emotion": emotion, "behavior": behavior},
                sig.episode_id,
                [trigger, emotion, behavior],
                "landmark",
                parent_key=("district", loop),
                novelty_flag=loop in novelty,
                rarity_flag=loop in rarity,
                surprise_flag=loop in surprise,
            )
        for trigger in sig.triggers:
            _upsert(
                seeds,
                "gate",
                (trigger,),
                trigger,
                {"trigger": trigger},
                sig.episode_id,
                [trigger],
                "gate",
            )
        for emotion in sig.emotions:
            _upsert(
                seeds,
                "climate",
                (emotion,),
                emotion,
                {"emotion": emotion},
                sig.episode_id,
                [emotion],
                "climate",
            )
        for cognition in sig.cognitions:
            _upsert(
                seeds,
                "architecture",
                (cognition,),
                cognition,
                {"cognition": cognition},
                sig.episode_id,
                [cognition],
                "architecture",
            )
        for behavior in sig.behaviors:
            _upsert(
                seeds,
                "road",
                (behavior,),
                behavior,
                {"behavior": behavior},
                sig.episode_id,
                [behavior],
                "road",
            )
        for horizon, outcomes in (
            ("short_term", sig.short_outcomes),
            ("long_term", sig.long_outcomes),
        ):
            for outcome in outcomes:
                _upsert(
                    seeds,
                    "destination",
                    (horizon, outcome),
                    f"{horizon}: {outcome}",
                    {"horizon": horizon, "outcome": outcome},
                    sig.episode_id,
                    [outcome, horizon],
                    "destination",
                )

    for (trigger, emotion), behaviors in _behavior_forks(report).items():
        if len(behaviors) < 2:
            continue
        episode_ids = set().union(*behaviors.values())
        _upsert_many(
            seeds,
            "crossroads",
            (trigger, emotion),
            f"{trigger} -> {emotion}",
            {"trigger": trigger, "emotion": emotion},
            episode_ids,
            [trigger, emotion],
            "crossroads",
        )

    return seeds


def _link_seeds(report: GraphReport) -> list[LinkSeed]:
    link_sets: dict[tuple[str, tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]], set[str]] = defaultdict(set)
    forks = _behavior_forks(report)
    novelty = set(novelty_counter(report))
    rarity = set(rarity_counter(report))
    surprise = set(surprise_counter(report))

    for sig in report.graph_ready:
        for trigger, emotion, behavior in loops_for_signature(sig):
            district = ("district", (trigger, emotion, behavior))
            _add_link(link_sets, "gate_to_district", ("gate", (trigger,)), district, sig.episode_id)
            _add_link(link_sets, "climate_to_district", ("climate", (emotion,)), district, sig.episode_id)
            _add_link(link_sets, "district_to_road", district, ("road", (behavior,)), sig.episode_id)
            if len(forks.get((trigger, emotion), {})) > 1:
                _add_link(
                    link_sets,
                    "crossroads_to_district",
                    ("crossroads", (trigger, emotion)),
                    district,
                    sig.episode_id,
                )
            if (trigger, emotion, behavior) in novelty | rarity | surprise:
                _add_link(
                    link_sets,
                    "landmark_to_district",
                    ("landmark", (trigger, emotion, behavior)),
                    district,
                    sig.episode_id,
                )
            for cognition in sig.cognitions:
                _add_link(
                    link_sets,
                    "architecture_to_district",
                    ("architecture", (cognition,)),
                    district,
                    sig.episode_id,
                )
            for horizon, outcomes in (
                ("short_term", sig.short_outcomes),
                ("long_term", sig.long_outcomes),
            ):
                for outcome in outcomes:
                    _add_link(
                        link_sets,
                        "road_to_destination",
                        ("road", (behavior,)),
                        ("destination", (horizon, outcome)),
                        sig.episode_id,
                    )

    return [
        LinkSeed(type=kind, from_key=from_key, to_key=to_key, episode_ids=episode_ids)
        for (kind, from_key, to_key), episode_ids in link_sets.items()
    ]


def _finalize_entities(
    seeds: dict[tuple[str, tuple[str, ...]], EntitySeed],
    report: GraphReport,
    limits: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[tuple[str, tuple[str, ...]], str]]:
    recurrence = stability_counter(report)
    entities: list[dict[str, Any]] = []
    key_to_id: dict[tuple[str, tuple[str, ...]], str] = {}

    for entity_type in ENTITY_TYPES:
        typed = [seed for seed in seeds.values() if seed.type == entity_type]
        if entity_type == "district":
            typed = [seed for seed in typed if len(seed.episode_ids) >= 2]
        elif entity_type == "landmark":
            typed = [
                seed
                for seed in typed
                if seed.novelty_flag or seed.rarity_flag or seed.surprise_flag
            ]
        typed.sort(key=lambda seed: (-len(seed.episode_ids), seed.label, seed.type))
        typed = typed[: limits.get(entity_type, len(typed))]
        max_count = max((len(seed.episode_ids) for seed in typed), default=0)

        for index, seed in enumerate(typed, start=1):
            entity_id = f"{entity_type}-{index}"
            key_to_id[(seed.type, seed.key)] = entity_id
            metrics = _metrics(seed, report, max_count, recurrence)
            entities.append(
                {
                    "id": entity_id,
                    "type": seed.type,
                    "label": seed.label,
                    "parent_id": None,
                    "signature": seed.signature,
                    "metrics": metrics,
                    "compiler_hints": _compiler_hints(seed, metrics),
                    "cluster_membership": {"cluster_id": None},
                    "provenance": {"episode_ids": sorted(seed.episode_ids)},
                }
            )

    for entity in entities:
        seed_key = _entity_key(entity)
        seed = seeds.get(seed_key)
        if seed and seed.parent_key:
            entity["parent_id"] = key_to_id.get(seed.parent_key)

    return entities, key_to_id


def _finalize_links(
    seeds: list[LinkSeed],
    key_to_id: dict[tuple[str, tuple[str, ...]], str],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for link_type in LINK_TYPES:
        typed = [
            seed
            for seed in seeds
            if seed.type == link_type and seed.from_key in key_to_id and seed.to_key in key_to_id
        ]
        typed.sort(
            key=lambda seed: (
                -len(seed.episode_ids),
                key_to_id[seed.from_key],
                key_to_id[seed.to_key],
            )
        )
        max_count = max((len(seed.episode_ids) for seed in typed), default=0)
        for index, seed in enumerate(typed, start=1):
            links.append(
                {
                    "id": f"{link_type}-{index}",
                    "type": link_type,
                    "from": key_to_id[seed.from_key],
                    "to": key_to_id[seed.to_key],
                    "weight": _normalized(len(seed.episode_ids), max_count),
                    "provenance": {"episode_ids": sorted(seed.episode_ids)},
                }
            )
    return links


def _district_topology(
    entities: list[dict[str, Any]],
    report: GraphReport,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    districts = [entity for entity in entities if entity["type"] == "district"]
    vectors = {district["id"]: _district_vector(district) for district in districts}
    candidates = []
    for left_index, left in enumerate(districts):
        for right in districts[left_index + 1:]:
            score, shared_keys, differing_keys = _similarity(
                vectors[left["id"]],
                vectors[right["id"]],
            )
            if score < NEIGHBOR_THRESHOLD:
                continue
            episode_ids = set(left["provenance"]["episode_ids"]) | set(right["provenance"]["episode_ids"])
            candidates.append(
                {
                    "from": left["id"],
                    "to": right["id"],
                    "score": score,
                    "shared_keys": shared_keys,
                    "differing_keys": differing_keys,
                    "episode_ids": episode_ids,
                    "shared_episode_ids": set(left["provenance"]["episode_ids"]) & set(right["provenance"]["episode_ids"]),
                }
            )
    candidates.sort(
        key=lambda item: (
            -item["score"],
            -len(item["shared_keys"]),
            item["from"],
            item["to"],
        )
    )
    selected = []
    per_district: Counter[str] = Counter()
    for candidate in candidates:
        if (
            per_district[candidate["from"]] >= NEIGHBOR_LIMIT_PER_DISTRICT
            or per_district[candidate["to"]] >= NEIGHBOR_LIMIT_PER_DISTRICT
        ):
            continue
        per_district[candidate["from"]] += 1
        per_district[candidate["to"]] += 1
        selected.append(candidate)

    clusters = _clusters_from_candidates(
        districts,
        [candidate for candidate in candidates if candidate["score"] >= CLUSTER_THRESHOLD],
        report,
    )
    cluster_by_member = {
        member_id: cluster["id"]
        for cluster in clusters
        for member_id in cluster["member_entity_ids"]
    }
    for district in districts:
        district["cluster_membership"] = {
            "cluster_id": cluster_by_member.get(district["id"])
        }

    neighbors = [
        {
            "id": f"district_similarity-{index}",
            "type": "district_similarity",
            "from": candidate["from"],
            "to": candidate["to"],
            "score": candidate["score"],
            "shared_keys": candidate["shared_keys"],
            "differing_keys": candidate["differing_keys"],
            "provenance": {
                "episode_ids": sorted(candidate["episode_ids"]),
                "shared_episode_ids": sorted(candidate["shared_episode_ids"]),
            },
        }
        for index, candidate in enumerate(selected, start=1)
    ]
    return clusters, neighbors


def _district_vector(district: dict[str, Any]) -> dict[str, float]:
    signature = district["signature"]
    return {
        f"trigger:{signature.get('trigger', '')}": SIMILARITY_WEIGHTS["trigger"],
        f"emotion:{signature.get('emotion', '')}": SIMILARITY_WEIGHTS["emotion"],
        f"behavior:{signature.get('behavior', '')}": SIMILARITY_WEIGHTS["behavior"],
    }


def _similarity(
    left: dict[str, float],
    right: dict[str, float],
) -> tuple[float, list[str], list[str]]:
    keys = set(left) | set(right)
    shared_keys = sorted(set(left) & set(right))
    differing_keys = sorted(keys - set(shared_keys))
    numerator = sum(min(left.get(key, 0), right.get(key, 0)) for key in keys)
    denominator = sum(max(left.get(key, 0), right.get(key, 0)) for key in keys)
    return round(numerator / denominator, 4) if denominator else 0, shared_keys, differing_keys


def _clusters_from_candidates(
    districts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    report: GraphReport,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    district_by_id = {district["id"]: district for district in districts}
    adjacency: dict[str, set[str]] = defaultdict(set)
    scores: dict[frozenset[str], float] = {}
    for candidate in candidates:
        adjacency[candidate["from"]].add(candidate["to"])
        adjacency[candidate["to"]].add(candidate["from"])
        scores[frozenset((candidate["from"], candidate["to"]))] = candidate["score"]

    components = []
    seen = set()
    for district_id in sorted(adjacency):
        if district_id in seen:
            continue
        stack = [district_id]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(sorted(adjacency[current] - component))
        seen.update(component)
        if len(component) >= 2:
            components.append(sorted(component))

    clusters = []
    for component in components:
        members = [district_by_id[district_id] for district_id in component]
        label = _cluster_label(members)
        episode_ids = sorted(
            {
                episode_id
                for member in members
                for episode_id in member["provenance"]["episode_ids"]
            }
        )
        member_scores = [
            score
            for pair, score in scores.items()
            if pair.issubset(component)
        ]
        weeks = sorted({week_key(episode_id, report) for episode_id in episode_ids})
        possible_edges = len(component) * (len(component) - 1) / 2
        clusters.append(
            {
                "id": "",
                "type": "district_similarity_cluster",
                "label": label,
                "member_entity_ids": component,
                "centroid_signature": _centroid_signature(members),
                "metrics": {
                    "member_count": len(component),
                    "episode_count": len(episode_ids),
                    "weight": 0,
                    "recurrence_weeks": len(weeks),
                    "first_week": weeks[0] if weeks else None,
                    "last_week": weeks[-1] if weeks else None,
                    "cohesion": round(sum(member_scores) / len(member_scores), 4) if member_scores else 0,
                    "density": round(len(member_scores) / possible_edges, 4) if possible_edges else 0,
                },
                "compiler_hints": {
                    "layout_priority": 0,
                    "centrality": 0,
                    "density": round(len(member_scores) / possible_edges, 4) if possible_edges else 0,
                    "suggested_map_role": "district_cluster",
                    "semantic_similarity_keys": _cluster_similarity_keys(members),
                },
                "provenance": {"episode_ids": episode_ids},
            }
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster["metrics"]["member_count"],
            -cluster["metrics"]["episode_count"],
            cluster["label"],
        )
    )
    max_episode_count = max((cluster["metrics"]["episode_count"] for cluster in clusters), default=0)
    for index, cluster in enumerate(clusters, start=1):
        cluster["id"] = f"district-cluster-{index}"
        weight = _normalized(cluster["metrics"]["episode_count"], max_episode_count)
        cluster["metrics"]["weight"] = weight
        cluster["compiler_hints"]["layout_priority"] = weight
        cluster["compiler_hints"]["centrality"] = weight
        if cluster["label"] == "":
            cluster["label"] = cluster["id"]
    return clusters


def _cluster_label(members: list[dict[str, Any]]) -> str:
    trigger = _dominant_signature_value(members, "trigger")
    emotion = _dominant_signature_value(members, "emotion")
    if not trigger or not emotion:
        return ""
    return f"{_title_value(trigger)}-{_title_value(emotion)} Cluster"


def _centroid_signature(members: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trigger": _dominant_signature_value(members, "trigger"),
        "emotion": _dominant_signature_value(members, "emotion"),
        "behavior": _dominant_signature_value(members, "behavior"),
    }


def _cluster_similarity_keys(members: list[dict[str, Any]]) -> list[str]:
    centroid = _centroid_signature(members)
    return [
        f"{key}:{value}"
        for key, value in centroid.items()
        if value is not None
    ]


def _dominant_signature_value(members: list[dict[str, Any]], key: str) -> str | None:
    counter: Counter[str] = Counter()
    for member in members:
        value = member["signature"].get(key)
        if value:
            counter[value] += int(member["metrics"].get("count", 0))
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _title_value(value: str) -> str:
    return value[:1].upper() + value[1:]


def _upsert(
    seeds: dict[tuple[str, tuple[str, ...]], EntitySeed],
    entity_type: str,
    key: tuple[str, ...],
    label: str,
    signature: dict[str, Any],
    episode_id: str,
    semantic_similarity_keys: list[str],
    suggested_map_role: str,
    *,
    parent_key: tuple[str, tuple[str, ...]] | None = None,
    novelty_flag: bool = False,
    rarity_flag: bool = False,
    surprise_flag: bool = False,
) -> None:
    _upsert_many(
        seeds,
        entity_type,
        key,
        label,
        signature,
        {episode_id},
        semantic_similarity_keys,
        suggested_map_role,
        parent_key=parent_key,
        novelty_flag=novelty_flag,
        rarity_flag=rarity_flag,
        surprise_flag=surprise_flag,
    )


def _upsert_many(
    seeds: dict[tuple[str, tuple[str, ...]], EntitySeed],
    entity_type: str,
    key: tuple[str, ...],
    label: str,
    signature: dict[str, Any],
    episode_ids: set[str],
    semantic_similarity_keys: list[str],
    suggested_map_role: str,
    *,
    parent_key: tuple[str, tuple[str, ...]] | None = None,
    novelty_flag: bool = False,
    rarity_flag: bool = False,
    surprise_flag: bool = False,
) -> None:
    seed_key = (entity_type, key)
    if seed_key not in seeds:
        seeds[seed_key] = EntitySeed(
            type=entity_type,
            key=key,
            label=label,
            signature=signature,
            episode_ids=set(),
            semantic_similarity_keys=semantic_similarity_keys,
            suggested_map_role=suggested_map_role,
            parent_key=parent_key,
        )
    seed = seeds[seed_key]
    seed.episode_ids.update(episode_ids)
    seed.novelty_flag = seed.novelty_flag or novelty_flag
    seed.rarity_flag = seed.rarity_flag or rarity_flag
    seed.surprise_flag = seed.surprise_flag or surprise_flag


def _add_link(
    link_sets: dict[tuple[str, tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]], set[str]],
    link_type: str,
    from_key: tuple[str, tuple[str, ...]],
    to_key: tuple[str, tuple[str, ...]],
    episode_id: str,
) -> None:
    link_sets[(link_type, from_key, to_key)].add(episode_id)


def _metrics(
    seed: EntitySeed,
    report: GraphReport,
    max_count: int,
    recurrence: Counter[tuple[str, ...]],
) -> dict[str, Any]:
    weeks = sorted({week_key(episode_id, report) for episode_id in seed.episode_ids})
    count = len(seed.episode_ids)
    recurrence_weeks = len(weeks)
    stability_flag = (
        seed.key in recurrence
        if seed.type in {"district", "landmark"}
        else recurrence_weeks > 1
    )
    return {
        "count": count,
        "weight": _normalized(count, max_count),
        "recurrence_weeks": recurrence_weeks,
        "first_week": weeks[0] if weeks else None,
        "last_week": weeks[-1] if weeks else None,
        "novelty_flag": seed.novelty_flag,
        "stability_flag": stability_flag,
        "rarity_flag": seed.rarity_flag or count == 1,
        "surprise_flag": seed.surprise_flag,
    }


def _compiler_hints(seed: EntitySeed, metrics: dict[str, Any]) -> dict[str, Any]:
    weight = float(metrics["weight"])
    centrality = weight if seed.type in {"district", "crossroads", "road"} else weight * 0.65
    density = min(1.0, (metrics["count"] + metrics["recurrence_weeks"]) / 8)
    return {
        "layout_priority": weight,
        "semantic_similarity_keys": list(seed.semantic_similarity_keys),
        "centrality": round(centrality, 4),
        "density": round(density, 4),
        "suggested_map_role": seed.suggested_map_role,
    }


def _behavior_forks(report: GraphReport) -> dict[tuple[str, str], dict[str, set[str]]]:
    forks: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    forks[(trigger, emotion)][behavior].add(sig.episode_id)
    return forks


def _entity_key(entity: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    signature = entity["signature"]
    if entity["type"] == "district" or entity["type"] == "landmark":
        return (
            entity["type"],
            (signature["trigger"], signature["emotion"], signature["behavior"]),
        )
    if entity["type"] == "destination":
        return (entity["type"], (signature["horizon"], signature["outcome"]))
    value = signature.get(entity["type"])
    if entity["type"] == "gate":
        value = signature.get("trigger")
    elif entity["type"] == "climate":
        value = signature.get("emotion")
    elif entity["type"] == "architecture":
        value = signature.get("cognition")
    elif entity["type"] == "road":
        value = signature.get("behavior")
    elif entity["type"] == "crossroads":
        return (entity["type"], (signature["trigger"], signature["emotion"]))
    return (entity["type"], (value,))


def _normalized(value: int, max_value: int) -> float:
    if not value or not max_value:
        return 0
    return round(value / max_value, 4)


if __name__ == "__main__":
    main()
