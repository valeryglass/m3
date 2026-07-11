from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.analytics_loader import annotation_coverage_for_episode_ids, selected_annotation_run
from app.graph_report import build_report, load_episodes
from app.insight_payload import build_insight_payload, require_payload_export_ready
from app.journal import DEFAULT_JOURNAL_LOG, JournalLog, journal_event, record_journal_event
from app.map_payload import build_map_payload
from app.report_interpretation import (
    build_report_interpretation_input,
    report_interpretation_is_eligible,
)
from app.profile_interpreter import profile_text_violations
from app.report_cards import build_report_cards
from app.report_entities import build_report_entities
from app.report_view_model import build_report_view_model, render_details_view
from app.user_report import render_details_from_payload, render_summary_from_payload

STATUS_PASSED = "passed"
STATUS_BLOCKED = "blocked"

@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "message": self.message}


def build_qa_status(
    episode_dir: Path,
    annotation_run_dir: Path | None,
    source: str,
    *,
    insight_payload_path: Path | None = None,
    map_payload_path: Path | None = None,
    journal_log: JournalLog | Path | None = None,
) -> dict[str, Any]:
    _record_qa_started(journal_log, episode_dir, annotation_run_dir, source)
    checks: list[CheckResult] = []

    if annotation_run_dir is None:
        checks.append(_fail("explicit_annotation_run", "annotation-run is required"))
        status = _blocked(source, annotation_run_dir, checks)
        _record_qa_journal(journal_log, status, episode_dir, annotation_run_dir)
        return status

    try:
        status = _build_qa_status(
            episode_dir,
            annotation_run_dir,
            source,
            insight_payload_path=insight_payload_path,
            map_payload_path=map_payload_path,
        )
    except Exception as exc:
        checks.append(_fail("qa_exception", str(exc)))
        status = _blocked(source, annotation_run_dir, checks)
        _record_qa_journal(journal_log, status, episode_dir, annotation_run_dir)
        return status
    _record_qa_journal(journal_log, status, episode_dir, annotation_run_dir)
    return status


def _build_qa_status(
    episode_dir: Path,
    annotation_run_dir: Path,
    source: str,
    *,
    insight_payload_path: Path | None,
    map_payload_path: Path | None,
) -> dict[str, Any]:
    checks: list[CheckResult] = []
    all_episodes = load_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
    all_episode_ids = {episode.id for episode in all_episodes}
    selected_run = selected_annotation_run(
        episode_dir,
        annotation_run_dir=annotation_run_dir,
        episode_ids=all_episode_ids,
    )
    checks.append(_pass("explicit_annotation_run", "annotation-run loaded"))

    source_episodes = [episode for episode in all_episodes if episode.source == source]
    source_episode_ids = {episode.id for episode in source_episodes}
    if not source_episodes:
        checks.append(_fail("source_has_episodes", "source has no episodes"))
        return _blocked(source, annotation_run_dir, checks, selected_run=selected_run)
    checks.append(_pass("source_has_episodes", "source has episodes"))

    coverage = annotation_coverage_for_episode_ids(
        source_episode_ids,
        annotation_run_dir=annotation_run_dir,
        known_episode_ids=all_episode_ids,
    )
    report = build_report(source_episodes, coverage=coverage)
    insight_payload = build_insight_payload(report)
    report_entities = build_report_entities(insight_payload)
    report_cards = build_report_cards(insight_payload)
    report_view_model = build_report_view_model(insight_payload)
    interpretation_input = build_report_interpretation_input(insight_payload)
    short_report = render_summary_from_payload(insight_payload)
    long_report = render_details_from_payload(insight_payload)
    map_payload = build_map_payload(
        all_episodes,
        source=source,
        coverage=coverage,
        provenance={
            "episode_dir": episode_dir.as_posix(),
            "source_scope": source,
            "annotation_run_id": selected_run.manifest.annotation_run_id,
            "annotation_run_path": selected_run.path.as_posix(),
        },
    )

    checks.extend(
        _readiness_checks(
            report,
            insight_payload,
            map_payload,
            selected_run,
            report_entities,
        )
    )
    checks.extend(
        _export_checks(
            insight_payload.to_dict(),
            map_payload,
            insight_payload_path=insight_payload_path,
            map_payload_path=map_payload_path,
        )
    )
    checks.extend(_report_text_checks(short_report, long_report, report_cards))
    checks.extend(
        _interpretation_input_checks(
            interpretation_input,
            long_report=long_report,
            deterministic_details=render_details_view(report_view_model),
        )
    )

    status = STATUS_PASSED if all(check.passed for check in checks) else STATUS_BLOCKED
    return {
        "status": status,
        "source": source,
        "selected_annotation_run_id": selected_run.manifest.annotation_run_id,
        "selected_annotation_run_path": selected_run.path.as_posix(),
        "coverage": insight_payload.to_dict()["coverage"],
        "readiness": {
            "total_episodes": report.total_episodes,
            "graph_ready_count": len(report.graph_ready),
            "report_ready_count": sum(
                1 for item in report.readiness if item.report_ready
            ),
            "payload_eligible_count": sum(
                1 for item in report.readiness if item.payload_eligible
            ),
        },
        "report_card_kinds": [card.kind for card in report_cards],
        "report_entity_kinds": sorted(
            {entity.kind for entity in report_entities.entities}
        ),
        "interpretation_artifact_kinds": sorted(
            {item.entity_kind for item in interpretation_input.artifacts}
        ),
        "interpretation_artifact_count": len(interpretation_input.artifacts),
        "interpretation_eligible": report_interpretation_is_eligible(
            interpretation_input
        ),
        "map_primitive_kinds": sorted(
            {
                primitive["kind"]
                for primitive in map_payload["analytics"]["map_primitives"][
                    "primitives"
                ]
            }
        ),
        "short_report_chars": len(short_report),
        "long_report_chars": len(long_report),
        "checks": [check.as_dict() for check in checks],
        "blockers": [check.message for check in checks if not check.passed],
    }


def _readiness_checks(
    report,
    insight_payload,
    map_payload,
    selected_run,
    report_entities,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    try:
        require_payload_export_ready(report)
        checks.append(_pass("payload_export_ready", "source is payload export ready"))
    except ValueError as exc:
        checks.append(_fail("payload_export_ready", str(exc)))

    insight_dict = insight_payload.to_dict()
    if insight_dict["coverage"]["state"] == "full":
        checks.append(_pass("full_coverage", "source coverage is full"))
    else:
        checks.append(_fail("full_coverage", "source coverage is partial"))

    if map_payload["analytics"]["insight_payload"] == insight_dict:
        checks.append(_pass("map_embeds_insight_payload", "map embeds matching insight"))
    else:
        checks.append(_fail("map_embeds_insight_payload", "map insight payload differs"))

    report_entity_kinds = {entity.kind for entity in report_entities.entities}
    if {"evidence", "pattern", "finding", "question"}.issubset(report_entity_kinds):
        checks.append(_pass("report_entities_available", "report entities are available"))
    else:
        checks.append(_fail("report_entities_available", "report entities are incomplete"))

    primitives = map_payload["analytics"].get("map_primitives", {}).get("primitives", ())
    primitive_kinds = {primitive.get("kind") for primitive in primitives}
    if {"Region", "Path", "Boundary", "Field", "Label"}.issubset(primitive_kinds):
        checks.append(_pass("map_primitives_available", "map primitives are available"))
    else:
        checks.append(_fail("map_primitives_available", "map primitives are incomplete"))

    dominant = insight_dict.get("dominant_motif")
    if dominant is None:
        checks.append(_pass("report_map_support_agreement", "no dominant motif to compare"))
    else:
        motif_ids = set(dominant.get("episode_ids", ()))
        report_ids = {
            episode_id
            for entity in report_entities.entities
            if entity.role == "dominant_motif"
            for episode_id in entity.episode_ids
        }
        region_ids = {
            episode_id
            for primitive in primitives
            if primitive.get("kind") == "Region"
            for episode_id in primitive.get("episode_ids", ())
        }
        if motif_ids and motif_ids.issubset(report_ids) and motif_ids.issubset(region_ids):
            checks.append(
                _pass(
                    "report_map_support_agreement",
                    "report entities and map primitives share motif support",
                )
            )
        else:
            checks.append(
                _fail(
                    "report_map_support_agreement",
                    "report/map support differs for dominant motif",
                )
            )

    provenance = map_payload.get("provenance", {})
    if (
        provenance.get("annotation_run_id") == selected_run.manifest.annotation_run_id
        and provenance.get("annotation_run_path") == selected_run.path.as_posix()
    ):
        checks.append(_pass("map_provenance_selected_run", "map names selected run"))
    else:
        checks.append(_fail("map_provenance_selected_run", "map provenance run mismatch"))
    return checks


def _export_checks(
    insight_payload: dict[str, Any],
    map_payload: dict[str, Any],
    *,
    insight_payload_path: Path | None,
    map_payload_path: Path | None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if insight_payload_path is not None:
        exported = _read_json(insight_payload_path)
        if _normalize_json_payload(exported) == _normalize_json_payload(insight_payload):
            checks.append(_pass("insight_export_matches", "insight export matches"))
        else:
            checks.append(_fail("insight_export_matches", "insight export differs"))
    if map_payload_path is not None:
        exported = _read_json(map_payload_path)
        if _normalize_map_payload(exported) == _normalize_map_payload(map_payload):
            checks.append(_pass("map_export_matches", "map export matches"))
        else:
            checks.append(_fail("map_export_matches", "map export differs"))
    return checks


def _report_text_checks(
    short_report: str,
    long_report: str,
    report_cards,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    forbidden = profile_text_violations(short_report, long_report)
    if forbidden:
        checks.append(
            _fail("report_text_guard", f"forbidden report wording: {', '.join(forbidden)}")
        )
    else:
        checks.append(_pass("report_text_guard", "report wording guard passed"))

    if report_cards and short_report and long_report:
        checks.append(_pass("report_renders_from_cards", "short and long reports render"))
    else:
        checks.append(_fail("report_renders_from_cards", "report cards or report text missing"))
    return checks


def _interpretation_input_checks(
    interpretation_input,
    *,
    long_report: str,
    deterministic_details: str,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    serialized = json.dumps(interpretation_input.to_dict(), ensure_ascii=False)
    artifact_ids = [item.artifact_id for item in interpretation_input.artifacts]
    entity_kinds = {item.entity_kind for item in interpretation_input.artifacts}
    safe_shape = (
        entity_kinds.issubset(
            {"evidence", "pattern", "exception", "change", "question", "gap"}
        )
        and len(artifact_ids) == len(set(artifact_ids))
        and not any(
            forbidden in serialized
            for forbidden in (
                "source_quote",
                "transcript",
                "episode_id",
                "episode_ids",
            )
        )
    )
    if safe_shape:
        checks.append(
            _pass(
                "interpretation_input_safe",
                "structured interpretation input is safe",
            )
        )
    else:
        checks.append(
            _fail(
                "interpretation_input_safe",
                "structured interpretation input is unsafe",
            )
        )

    if long_report == deterministic_details:
        checks.append(
            _pass(
                "deterministic_fallback_available",
                "deterministic expanded fallback is available",
            )
        )
    else:
        checks.append(
            _fail(
                "deterministic_fallback_available",
                "deterministic expanded fallback differs",
            )
        )
    return checks


def _blocked(
    source: str,
    annotation_run_dir: Path | None,
    checks: list[CheckResult],
    *,
    selected_run=None,
) -> dict[str, Any]:
    return {
        "status": STATUS_BLOCKED,
        "source": source,
        "selected_annotation_run_id": (
            selected_run.manifest.annotation_run_id if selected_run is not None else None
        ),
        "selected_annotation_run_path": (
            selected_run.path.as_posix()
            if selected_run is not None
            else annotation_run_dir.as_posix()
            if annotation_run_dir is not None
            else None
        ),
        "coverage": {},
        "readiness": {},
        "report_card_kinds": [],
        "report_entity_kinds": [],
        "interpretation_artifact_kinds": [],
        "interpretation_artifact_count": 0,
        "interpretation_eligible": False,
        "map_primitive_kinds": [],
        "short_report_chars": 0,
        "long_report_chars": 0,
        "checks": [check.as_dict() for check in checks],
        "blockers": [check.message for check in checks if not check.passed],
    }


def _normalize_map_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_json_payload(payload)
    normalized.get("provenance", {}).pop("generated_at", None)
    return normalized


def _normalize_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _record_qa_journal(
    journal_log: JournalLog | Path | None,
    status: dict[str, Any],
    episode_dir: Path,
    annotation_run_dir: Path | None,
) -> None:
    blocked = status["status"] == STATUS_BLOCKED
    readiness = status.get("readiness") or {}
    checks = status.get("checks") or []
    record_journal_event(
        journal_log,
        journal_event(
            component="report_payload_qa",
            event_type=(
                "report_payload_qa.blocked"
                if blocked
                else "report_payload_qa.passed"
            ),
            stage="blocked" if blocked else "succeeded",
            level="error" if blocked else "info",
            reason="; ".join(status.get("blockers", [])) or None,
            refs={
                "episode_dir": episode_dir.as_posix(),
                "annotation_run_dir": (
                    annotation_run_dir.as_posix()
                    if annotation_run_dir is not None
                    else None
                ),
                "selected_annotation_run_path": status.get(
                    "selected_annotation_run_path"
                ),
            },
            counts={
                "check_count": len(checks),
                "blocker_count": len(status.get("blockers", [])),
                "graph_ready_count": readiness.get("graph_ready_count", 0),
                "report_ready_count": readiness.get("report_ready_count", 0),
                "payload_eligible_count": readiness.get(
                    "payload_eligible_count", 0
                ),
            },
            details={
                "source": status.get("source"),
                "selected_annotation_run_id": status.get(
                    "selected_annotation_run_id"
                ),
                "coverage_state": (status.get("coverage") or {}).get("state"),
            },
        ),
    )


def _record_qa_started(
    journal_log: JournalLog | Path | None,
    episode_dir: Path,
    annotation_run_dir: Path | None,
    source: str,
) -> None:
    record_journal_event(
        journal_log,
        journal_event(
            component="report_payload_qa",
            event_type="report_payload_qa.started",
            stage="started",
            refs={
                "episode_dir": episode_dir.as_posix(),
                "annotation_run_dir": (
                    annotation_run_dir.as_posix()
                    if annotation_run_dir is not None
                    else None
                ),
            },
            details={"source": source},
        ),
    )


def _pass(name: str, message: str) -> CheckResult:
    return CheckResult(name=name, passed=True, message=message)


def _fail(name: str, message: str) -> CheckResult:
    return CheckResult(name=name, passed=False, message=message)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="QA graph, payload, map, and profile report consistency."
    )
    parser.add_argument("--episode-dir", type=Path, default=Path("data/episodes"))
    parser.add_argument("--annotation-run-dir", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--insight-payload-path", type=Path)
    parser.add_argument("--map-payload-path", type=Path)
    parser.add_argument("--journal-log", type=Path, default=DEFAULT_JOURNAL_LOG)
    args = parser.parse_args(argv)

    status = build_qa_status(
        args.episode_dir,
        args.annotation_run_dir,
        args.source,
        insight_payload_path=args.insight_payload_path,
        map_payload_path=args.map_payload_path,
        journal_log=args.journal_log,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status["status"] == STATUS_BLOCKED:
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
