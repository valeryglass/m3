from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.runtime_storage import append_jsonl

SCHEMA_VERSION = "m3.journal_event.v1"
DEFAULT_JOURNAL_LOG = Path("data/journal/events.jsonl")
LEVELS = frozenset({"info", "warning", "error", "critical"})
STAGES = frozenset({"started", "succeeded", "failed", "blocked", "checked"})
UNSAFE_KEYS = frozenset(
    {
        "api_key",
        "automatic_thought",
        "llm_output",
        "message_text",
        "observed",
        "prompt",
        "quote",
        "raw_output",
        "raw_provider_output",
        "raw_text",
        "report_text",
        "source_quote",
        "telegram_text",
        "text",
        "transcript",
        "value",
        "provider_output",
    }
)


@dataclass(frozen=True)
class JournalLog:
    path: Path

    def append(self, event: Mapping[str, Any]) -> None:
        normalized = _sanitize_mapping(dict(event))
        append_jsonl(self.path, normalized)


def journal_event(
    *,
    component: str,
    event_type: str,
    stage: str,
    level: str = "info",
    created_at: datetime | None = None,
    run_id: str | None = None,
    process_id: str | None = None,
    refs: Mapping[str, Any] | None = None,
    counts: Mapping[str, Any] | None = None,
    reason: str | None = None,
    failure_code: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if level not in LEVELS:
        raise ValueError(f"journal level must be one of: {', '.join(sorted(LEVELS))}")
    if stage not in STAGES:
        raise ValueError(f"journal stage must be one of: {', '.join(sorted(STAGES))}")
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
        "level": level,
        "component": component,
        "event_type": event_type,
        "stage": stage,
    }
    if run_id:
        event["run_id"] = run_id
    if process_id:
        event["process_id"] = process_id
    if refs:
        event["refs"] = _sanitize_mapping(refs)
    if counts:
        event["counts"] = _sanitize_mapping(counts)
    if reason:
        event["reason"] = reason
    if failure_code:
        event["failure_code"] = failure_code
    if details:
        event["details"] = _sanitize_mapping(details)
    return _sanitize_mapping(event)


def record_journal_event(log: JournalLog | Path | None, event: Mapping[str, Any]) -> None:
    if log is None:
        return
    try:
        journal = log if isinstance(log, JournalLog) else JournalLog(Path(log))
        journal.append(event)
    except Exception:
        return


def _sanitize_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        normalized_key = str(key)
        if normalized_key.lower() in UNSAFE_KEYS:
            sanitized[normalized_key] = "[redacted]"
        else:
            sanitized[normalized_key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
