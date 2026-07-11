from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.runtime_storage import ProcessLock, atomic_write_text, locked_path
from app.userlist import JsonUserList

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency guard
    load_dotenv = None


DELETE_CONFIRM_PREFIX = "DELETE-"


@dataclass(frozen=True)
class UserDataPaths:
    episode_dir: Path = Path("data/episodes")
    runtime_session_dir: Path = Path("data/runtime-sessions")
    runtime_flow_dir: Path = Path("data/runtime-flows")
    userlist_path: Path = Path("data/userlist/users.json")
    ux_event_log: Path = Path("data/ux-events/events.jsonl")
    journal_log: Path = Path("data/journal/events.jsonl")
    annotation_run_root: Path = Path("data/annotation-runs")
    intake_transcript_dir: Path = Path("data/intake-transcripts")
    capture_artifact_dir: Path = Path("data/capture-artifacts")
    capture_extraction_dir: Path = Path("data/capture-extractions")
    capture_debug_dir: Path = Path("data/capture-debug")
    reports_dir: Path = Path("data/reports")
    exports_dir: Path = Path("data/exports")
    backups_dir: Path = Path("data/backups")


@dataclass(frozen=True)
class UserDataInventory:
    user_id: str
    chat_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]
    files_by_category: dict[str, tuple[Path, ...]]
    userlist_records: int
    ux_event_rows: int
    journal_rows: int
    affected_annotation_runs: tuple[Path, ...]
    shared_files_to_clear: tuple[Path, ...]

    @property
    def personal_file_count(self) -> int:
        return sum(len(paths) for paths in self.files_by_category.values())

    @property
    def has_data(self) -> bool:
        return any(
            (
                self.personal_file_count,
                self.userlist_records,
                self.ux_event_rows,
                self.journal_rows,
                len(self.affected_annotation_runs),
                len(self.shared_files_to_clear),
            )
        )

    def safe_summary(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "chat_ids": list(self.chat_ids),
            "episode_count": len(self.episode_ids),
            "files_by_category": {
                category: [path.as_posix() for path in paths]
                for category, paths in sorted(self.files_by_category.items())
            },
            "personal_file_count": self.personal_file_count,
            "userlist_records": self.userlist_records,
            "ux_event_rows": self.ux_event_rows,
            "journal_rows": self.journal_rows,
            "affected_annotation_runs": [
                path.as_posix() for path in self.affected_annotation_runs
            ],
            "shared_files_to_clear": [
                path.as_posix() for path in self.shared_files_to_clear
            ],
            "has_data": self.has_data,
            "delete_confirmation": f"{DELETE_CONFIRM_PREFIX}{self.user_id}",
        }


class UserDataManager:
    def __init__(self, paths: UserDataPaths) -> None:
        self.paths = paths
        self.userlist = JsonUserList(paths.userlist_path)

    def inventory(self, user_id: str) -> UserDataInventory:
        normalized_user_id = _telegram_id(user_id, allow_negative=False)
        records = self.userlist.records_for_identity(normalized_user_id)
        raw_chat_ids = {
            normalized_user_id,
            *records.keys(),
            *(str(record.get("chat_id")) for record in records.values()),
        }
        raw_chat_ids.discard("None")
        chat_ids = {
            _telegram_id(chat_id, allow_negative=True) for chat_id in raw_chat_ids
        }

        episode_paths, episode_ids = self._episode_files(chat_ids)
        files_by_category = {
            "episodes": tuple(episode_paths),
            "runtime_sessions": self._named_files(
                self.paths.runtime_session_dir,
                chat_ids,
                templates=("chat-{chat_id}.json", "review/chat-{chat_id}.json"),
            ),
            "runtime_flows": self._named_files(
                self.paths.runtime_flow_dir,
                chat_ids,
                templates=("capture/chat-{chat_id}.json",),
            ),
            "intake_transcripts": self._chat_tree_files(
                self.paths.intake_transcript_dir, chat_ids
            ),
            "capture_artifacts": self._chat_tree_files(
                self.paths.capture_artifact_dir, chat_ids
            ),
            "capture_extractions": self._chat_tree_files(
                self.paths.capture_extraction_dir, chat_ids
            ),
            "capture_debug": self._chat_tree_files(
                self.paths.capture_debug_dir, chat_ids
            ),
        }
        files_by_category = {
            category: paths for category, paths in files_by_category.items() if paths
        }
        ux_rows = _matching_rows(
            self.paths.ux_event_log,
            normalized_user_id,
            chat_ids,
            episode_ids,
        )
        journal_rows = _matching_rows(
            self.paths.journal_log,
            normalized_user_id,
            chat_ids,
            episode_ids,
        )
        annotation_runs = self._affected_annotation_runs(episode_ids)
        has_personal_data = bool(
            records
            or files_by_category
            or ux_rows
            or journal_rows
            or annotation_runs
        )
        shared_files = (
            tuple(
                sorted(
                    {
                        *self._runtime_files(self.paths.reports_dir),
                        *self._runtime_files(self.paths.exports_dir),
                        *self._runtime_files(self.paths.backups_dir),
                    }
                )
            )
            if has_personal_data
            else ()
        )
        return UserDataInventory(
            user_id=normalized_user_id,
            chat_ids=tuple(sorted(chat_ids)),
            episode_ids=tuple(sorted(episode_ids)),
            files_by_category=files_by_category,
            userlist_records=len(records),
            ux_event_rows=len(ux_rows),
            journal_rows=len(journal_rows),
            affected_annotation_runs=annotation_runs,
            shared_files_to_clear=shared_files,
        )

    def export(self, user_id: str, output_path: Path) -> dict[str, Any]:
        with ProcessLock(self.paths.runtime_flow_dir / ".bot-writer.lock"):
            inventory = self.inventory(user_id)
            return self._export_locked(inventory, output_path)

    def _export_locked(
        self,
        inventory: UserDataInventory,
        output_path: Path,
    ) -> dict[str, Any]:
        output_path = Path(output_path)
        if output_path.exists():
            raise FileExistsError(f"export already exists: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            with zipfile.ZipFile(
                temporary_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                self._write_export(archive, inventory)
            os.replace(temporary_path, output_path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        return {
            "status": "exported",
            "user_id": inventory.user_id,
            "output_path": output_path.as_posix(),
            "personal_file_count": inventory.personal_file_count,
            "episode_count": len(inventory.episode_ids),
            "ux_event_rows": inventory.ux_event_rows,
            "journal_rows": inventory.journal_rows,
        }

    def delete(self, user_id: str, *, confirmation: str) -> dict[str, Any]:
        inventory = self.inventory(user_id)
        expected = f"{DELETE_CONFIRM_PREFIX}{inventory.user_id}"
        if confirmation != expected:
            raise ValueError(f"deletion requires exact confirmation: {expected}")

        with ProcessLock(self.paths.runtime_flow_dir / ".bot-writer.lock"):
            return self._delete_locked(inventory)

    def _delete_locked(self, inventory: UserDataInventory) -> dict[str, Any]:

        deleted_files = 0
        for paths in inventory.files_by_category.values():
            for path in paths:
                if path.exists():
                    path.unlink()
                    deleted_files += 1
        for path in inventory.shared_files_to_clear:
            if path.exists():
                path.unlink()
                deleted_files += 1
        for run_dir in inventory.affected_annotation_runs:
            if run_dir.exists():
                shutil.rmtree(run_dir)
        removed_ux = _remove_matching_rows(
            self.paths.ux_event_log,
            inventory.user_id,
            set(inventory.chat_ids),
            set(inventory.episode_ids),
        )
        removed_journal = _remove_matching_rows(
            self.paths.journal_log,
            inventory.user_id,
            set(inventory.chat_ids),
            set(inventory.episode_ids),
        )
        removed_users = self.userlist.delete_identity(inventory.user_id)
        _remove_empty_private_dirs(self.paths)

        verification = self.verify(inventory.user_id)
        planned_paths = {
            *(
                path
                for paths in inventory.files_by_category.values()
                for path in paths
            ),
            *inventory.shared_files_to_clear,
            *inventory.affected_annotation_runs,
        }
        undeleted_paths = sorted(
            path.as_posix() for path in planned_paths if path.exists()
        )
        verified = verification["verified"] and not undeleted_paths
        return {
            "status": "deleted" if verified else "blocked",
            "user_id": inventory.user_id,
            "deleted_files": deleted_files,
            "removed_annotation_runs": len(inventory.affected_annotation_runs),
            "removed_ux_rows": removed_ux,
            "removed_journal_rows": removed_journal,
            "removed_userlist_records": removed_users,
            "verified": verified,
            "remaining": verification["remaining"],
            "undeleted_paths": undeleted_paths,
        }

    def verify(self, user_id: str) -> dict[str, Any]:
        inventory = self.inventory(user_id)
        remaining = inventory.safe_summary()
        return {
            "status": "verified" if not inventory.has_data else "blocked",
            "user_id": inventory.user_id,
            "verified": not inventory.has_data,
            "remaining": remaining,
        }

    def _episode_files(self, chat_ids: set[str]) -> tuple[list[Path], set[str]]:
        paths: list[Path] = []
        episode_ids: set[str] = set()
        if not self.paths.episode_dir.exists():
            return paths, episode_ids
        sources = {f"telegram-chat:{chat_id}" for chat_id in chat_ids}
        for path in sorted(self.paths.episode_dir.glob("episode-*.json")):
            payload = _read_json(path)
            if payload.get("source") in sources:
                paths.append(path)
                episode_ids.add(str(payload.get("id") or path.stem))
        return paths, episode_ids

    def _affected_annotation_runs(self, episode_ids: set[str]) -> tuple[Path, ...]:
        if not episode_ids or not self.paths.annotation_run_root.exists():
            return ()
        affected = []
        for run_dir in sorted(self.paths.annotation_run_root.glob("run-*")):
            annotations = run_dir / "annotations.jsonl"
            if any(
                str(row.get("episode_id")) in episode_ids
                for row in _read_jsonl(annotations)
            ):
                affected.append(run_dir)
        return tuple(affected)

    def _write_export(
        self,
        archive: zipfile.ZipFile,
        inventory: UserDataInventory,
    ) -> None:
        for category, paths in sorted(inventory.files_by_category.items()):
            for path in paths:
                archive.write(
                    path,
                    arcname=self._export_arcname(category, path),
                )
        records = self.userlist.records_for_identity(inventory.user_id)
        _zip_json(archive, "access/userlist-records.json", {"users": records})
        _zip_jsonl(
            archive,
            "events/ux-events.jsonl",
            _matching_rows(
                self.paths.ux_event_log,
                inventory.user_id,
                set(inventory.chat_ids),
                set(inventory.episode_ids),
            ),
        )
        _zip_jsonl(
            archive,
            "events/journal-events.jsonl",
            _matching_rows(
                self.paths.journal_log,
                inventory.user_id,
                set(inventory.chat_ids),
                set(inventory.episode_ids),
            ),
        )
        for run_dir in inventory.affected_annotation_runs:
            rows = [
                row
                for row in _read_jsonl(run_dir / "annotations.jsonl")
                if str(row.get("episode_id")) in inventory.episode_ids
            ]
            _zip_jsonl(
                archive,
                f"derived/{run_dir.name}/annotations.jsonl",
                rows,
            )
        _zip_json(
            archive,
            "manifest.json",
            _export_manifest(inventory),
        )
    def _export_arcname(self, category: str, path: Path) -> str:
        roots = {
            "episodes": self.paths.episode_dir,
            "runtime_sessions": self.paths.runtime_session_dir,
            "runtime_flows": self.paths.runtime_flow_dir,
            "intake_transcripts": self.paths.intake_transcript_dir,
            "capture_artifacts": self.paths.capture_artifact_dir,
            "capture_extractions": self.paths.capture_extraction_dir,
            "capture_debug": self.paths.capture_debug_dir,
        }
        relative = path.relative_to(roots[category])
        return f"artifacts/{category}/{relative.as_posix()}"

    @staticmethod
    def _named_files(
        root: Path,
        chat_ids: set[str],
        *,
        templates: tuple[str, ...],
    ) -> tuple[Path, ...]:
        return tuple(
            sorted(
                path
                for chat_id in chat_ids
                for template in templates
                if (path := root / template.format(chat_id=chat_id)).is_file()
            )
        )

    @staticmethod
    def _chat_tree_files(root: Path, chat_ids: set[str]) -> tuple[Path, ...]:
        return tuple(
            sorted(
                path
                for chat_id in chat_ids
                for path in (root / f"telegram-chat-{chat_id}").rglob("*")
                if _is_runtime_file(path)
            )
        )

    @staticmethod
    def _runtime_files(root: Path) -> tuple[Path, ...]:
        if not root.exists():
            return ()
        return tuple(sorted(path for path in root.rglob("*") if _is_runtime_file(path)))


def _export_manifest(inventory: UserDataInventory) -> dict[str, Any]:
    summary = inventory.safe_summary()
    files_by_category = summary.pop("files_by_category")
    annotation_runs = summary.pop("affected_annotation_runs")
    shared_file_count = len(summary.pop("shared_files_to_clear"))
    summary.pop("delete_confirmation", None)
    return {
        "schema_version": "m3.user_data_export.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **summary,
        "file_counts_by_category": {
            category: len(paths) for category, paths in files_by_category.items()
        },
        "annotation_run_count": len(annotation_runs),
        "shared_reports_exports_and_backups_included": False,
        "shared_file_count_excluded": shared_file_count,
    }


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
    parser = argparse.ArgumentParser(
        description="Inventory, export, or delete one user's private data."
    )
    parser.add_argument(
        "action",
        choices=("inventory", "export", "delete-preview", "delete", "verify"),
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--output")
    parser.add_argument("--confirm")
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()

    root = Path(args.data_root)
    manager = UserDataManager(_paths_for_root(root))
    if args.action in {"inventory", "delete-preview"}:
        result = manager.inventory(args.user_id).safe_summary()
        result["status"] = "preview" if args.action == "delete-preview" else "inventory"
    elif args.action == "export":
        if not args.output:
            parser.error("export requires --output")
        result = manager.export(args.user_id, Path(args.output))
    elif args.action == "delete":
        if not args.confirm:
            parser.error("delete requires --confirm")
        result = manager.delete(args.user_id, confirmation=args.confirm)
    else:
        result = manager.verify(args.user_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _paths_for_root(root: Path) -> UserDataPaths:
    return UserDataPaths(
        episode_dir=_env_path("M3_EPISODE_DIR", root / "episodes"),
        runtime_session_dir=_env_path(
            "M3_RUNTIME_SESSION_DIR", root / "runtime-sessions"
        ),
        runtime_flow_dir=_env_path("M3_RUNTIME_FLOW_DIR", root / "runtime-flows"),
        userlist_path=_env_path(
            "M3_USERLIST_PATH", root / "userlist" / "users.json"
        ),
        ux_event_log=_env_path(
            "M3_UX_EVENT_LOG", root / "ux-events" / "events.jsonl"
        ),
        journal_log=_env_path(
            "M3_JOURNAL_LOG", root / "journal" / "events.jsonl"
        ),
        annotation_run_root=_env_path(
            "M3_ANNOTATION_RUN_ROOT", root / "annotation-runs"
        ),
        intake_transcript_dir=_env_path(
            "M3_INTAKE_TRANSCRIPT_DIR", root / "intake-transcripts"
        ),
        capture_artifact_dir=_env_path(
            "M3_CAPTURE_ARTIFACT_DIR", root / "capture-artifacts"
        ),
        capture_extraction_dir=_env_path(
            "M3_CAPTURE_EXTRACTION_DIR", root / "capture-extractions"
        ),
        capture_debug_dir=_env_path(
            "M3_CAPTURE_DEBUG_DIR", root / "capture-debug"
        ),
        reports_dir=root / "reports",
        exports_dir=root / "exports",
        backups_dir=root / "backups",
    )


def _env_path(key: str, default: Path) -> Path:
    value = os.environ.get(key, "").strip()
    return Path(value) if value else default


def _telegram_id(value: Any, *, allow_negative: bool) -> str:
    rendered = str(value).strip()
    pattern = r"-?[0-9]{1,20}" if allow_negative else r"[0-9]{1,20}"
    if not re.fullmatch(pattern, rendered):
        raise ValueError("Telegram user/chat ids must be numeric")
    return rendered


def _matching_rows(
    path: Path,
    user_id: str,
    chat_ids: set[str],
    episode_ids: set[str],
) -> list[dict[str, Any]]:
    return [
        row
        for row in _read_jsonl(path)
        if _row_matches_identity(row, user_id, chat_ids, episode_ids)
    ]


def _remove_matching_rows(
    path: Path,
    user_id: str,
    chat_ids: set[str],
    episode_ids: set[str],
) -> int:
    if not path.exists():
        return 0
    with locked_path(path):
        rows = _read_jsonl(path)
        retained = [
            row
            for row in rows
            if not _row_matches_identity(row, user_id, chat_ids, episode_ids)
        ]
        atomic_write_text(
            path,
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in retained
            ),
            lock=False,
        )
    return len(rows) - len(retained)


def _row_matches_identity(
    value: Any,
    user_id: str,
    chat_ids: set[str],
    episode_ids: set[str],
    *,
    key: str | None = None,
) -> bool:
    if isinstance(value, dict):
        return any(
            _row_matches_identity(
                nested,
                user_id,
                chat_ids,
                episode_ids,
                key=str(nested_key),
            )
            for nested_key, nested in value.items()
        )
    if isinstance(value, list):
        return any(
            _row_matches_identity(item, user_id, chat_ids, episode_ids, key=key)
            for item in value
        )
    rendered = str(value)
    if key in {"user_id", "chat_id"}:
        return rendered == user_id or rendered in chat_ids
    if key == "episode_id":
        return rendered in episode_ids
    if key in {"source", "capture_id", "extraction_id", "path", "debug_path"}:
        return any(
            marker in rendered
            for chat_id in chat_ids
            for marker in (
                f"telegram-chat:{chat_id}",
                f"telegram-chat-{chat_id}",
                f"-{chat_id}-",
            )
        ) or any(episode_id in rendered for episode_id in episode_ids)
    return False


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def _zip_json(archive: zipfile.ZipFile, name: str, payload: Any) -> None:
    archive.writestr(
        name,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _zip_jsonl(
    archive: zipfile.ZipFile,
    name: str,
    rows: Iterable[dict[str, Any]],
) -> None:
    archive.writestr(
        name,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
    )


def _is_runtime_file(path: Path) -> bool:
    return path.is_file() and path.name != ".gitkeep" and not path.name.endswith(
        (".lock", ".tmp")
    )


def _remove_empty_private_dirs(paths: UserDataPaths) -> None:
    roots = (
        paths.runtime_session_dir,
        paths.runtime_flow_dir,
        paths.intake_transcript_dir,
        paths.capture_artifact_dir,
        paths.capture_extraction_dir,
        paths.capture_debug_dir,
    )
    for root in roots:
        if not root.exists():
            continue
        for directory in sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                continue


if __name__ == "__main__":
    main()
