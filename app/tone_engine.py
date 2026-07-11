from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from app.draft_review import render_draft_review_overview
from app.messages import (
    BOT_PROFILE,
    COMMAND_DESCRIPTIONS,
    FIELD_GUIDES,
    SESSION_MESSAGES,
    TARGETS,
    TARGET_PROMPTS,
)

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard
    yaml = None


DEFAULT_TONE_CONFIG: dict[str, Any] = {
    "tone": {
        "name": "pragmatic_cbt_guide",
        "language": {
            "default": "ru",
            "style": "concise",
            "slang_allowed": True,
        },
        "voice": {
            "warm": 2,
            "direct": 5,
            "clinical": 2,
            "playful": 1,
            "supportive": 3,
        },
        "behavior": {
            "one_question_at_time": True,
            "avoid_long_explanations": True,
            "avoid_advice": True,
            "avoid_diagnosis": True,
            "keep_user_words": True,
        },
        "question_style": {
            "max_length": 140,
            "examples_allowed": True,
            "prefer_concrete_episode": True,
        },
        "forbidden": [
            "moralizing",
            "diagnosis",
            "personality_typing",
            "motivation_monologue",
            "overexplaining",
        ],
    }
}


@dataclass(frozen=True)
class ToneEngine:
    config: dict[str, Any]
    prompts: dict[str, str]

    @classmethod
    def default(cls) -> "ToneEngine":
        return cls(config=deepcopy(DEFAULT_TONE_CONFIG), prompts=dict(TARGET_PROMPTS))

    @property
    def max_question_length(self) -> int:
        return int(
            self.config["tone"].get("question_style", {}).get("max_length", 140)
        )

    @property
    def forbidden(self) -> tuple[str, ...]:
        return tuple(self.config["tone"].get("forbidden", ()))

    def target_prompt(self, target: str) -> str:
        if target == "complete":
            return self.complete()
        return self.prompts[target]

    def field_guide(self, target: str) -> dict[str, Any]:
        return FIELD_GUIDES[target]

    def bot_short_description(self) -> str:
        return BOT_PROFILE["short_description"]

    def bot_description(self) -> str:
        return BOT_PROFILE["description"]

    def start_session(self, prompt: str, total_count: int | None = None) -> str:
        total_count = total_count or len(TARGETS)
        return SESSION_MESSAGES["start_session"].format(
            progress_bar=self.progress_bar(0, total_count),
            completed_count=0,
            total_count=total_count,
            prompt=prompt,
        )

    def next_prompt_bridge(
        self, completed_count: int, total_count: int, prompt: str
    ) -> str:
        return SESSION_MESSAGES["next_prompt_bridge"].format(
            progress_bar=self.progress_bar(completed_count, total_count),
            completed_count=completed_count,
            total_count=total_count,
            prompt=prompt,
        )

    def review_screen(
        self,
        observed: dict[str, dict[str, str]],
        targets: tuple[str, ...] = TARGETS,
    ) -> str:
        total_count = len(targets)
        return SESSION_MESSAGES["review_screen"].format(
            progress_bar=self.progress_bar(total_count, total_count),
            completed_count=total_count,
            total_count=total_count,
            overview=render_draft_review_overview(observed, targets),
        )

    def progress_bar(self, completed_count: int, total_count: int) -> str:
        completed = max(0, min(completed_count, total_count))
        remaining = max(0, total_count - completed)
        return f"{'■' * completed}{'□' * remaining}"

    def empty_answer(self, target: str) -> str:
        return f"{SESSION_MESSAGES['empty_answer']}\n\n{self.target_prompt(target)}"

    def complete(self) -> str:
        return SESSION_MESSAGES["complete"]

    def already_complete(self) -> str:
        return SESSION_MESSAGES["already_complete"]

    def status(self, target: str, completed_count: int, total_count: int) -> str:
        return SESSION_MESSAGES["status"].format(
            target=target,
            completed_count=completed_count,
            total_count=total_count,
        )

    def help(self) -> str:
        return SESSION_MESSAGES["help"]

    def command_description(self, command: str) -> str:
        return COMMAND_DESCRIPTIONS[command]

    def no_active_loop(self) -> str:
        return SESSION_MESSAGES["no_active_loop"]

    def no_active_loop_start(self) -> str:
        return SESSION_MESSAGES["no_active_loop_start"]

    def cancel(self) -> str:
        return SESSION_MESSAGES["cancel"]

    def unknown_command(self) -> str:
        return SESSION_MESSAGES["unknown_command"]

    def unauthorized(self) -> str:
        return SESSION_MESSAGES["unauthorized"]

    def waitlisted(self) -> str:
        return SESSION_MESSAGES["waitlisted"]

    def private_chat_required(self) -> str:
        return SESSION_MESSAGES["private_chat_required"]

    def consent_notice(self, notice_version: str) -> str:
        return SESSION_MESSAGES["consent_notice"].format(
            notice_version=escape(notice_version)
        )

    def consent_accepted(self) -> str:
        return SESSION_MESSAGES["consent_accepted"]

    def consent_declined(self) -> str:
        return SESSION_MESSAGES["consent_declined"]

    def consent_stale(self) -> str:
        return SESSION_MESSAGES["consent_stale"]

    def admin_waitlist_notice(
        self, chat_id: int, user_id: str, profile: dict[str, Any] | None = None
    ) -> str:
        profile_text = _format_admin_profile(profile or {})
        return SESSION_MESSAGES["admin_waitlist_notice"].format(
            chat_id=chat_id,
            user_id=escape(user_id),
            profile=profile_text,
        )

    def admin_approved(self, chat_id: int) -> str:
        return SESSION_MESSAGES["admin_approved"].format(chat_id=chat_id)

    def approval_granted(self) -> str:
        return SESSION_MESSAGES["approval_granted"]

    def admin_paused(self, chat_id: int) -> str:
        return SESSION_MESSAGES["admin_paused"].format(chat_id=chat_id)

    def admin_bad_command(self, command: str) -> str:
        return SESSION_MESSAGES["admin_bad_command"].format(command=command)

    def profile_missing(self) -> str:
        return SESSION_MESSAGES["profile_missing"]

    def report_failed(self, error: Exception | str) -> str:
        return SESSION_MESSAGES["report_failed"].format(error=escape(str(error)))

    def graph_reports_ready(
        self,
        *,
        episodes: int,
        observed_count: int,
        annotated_count: int,
        pending_count: int,
        coverage: str,
        invalid: int,
        empty_derived: int,
        annotation_ready: int,
        graph_ready: int,
        report_ready: int,
        payload_eligible: int,
    ) -> str:
        return SESSION_MESSAGES["graph_reports_ready"].format(
            episodes=episodes,
            observed_count=observed_count,
            annotated_count=annotated_count,
            pending_count=pending_count,
            coverage=escape(coverage),
            invalid=invalid,
            empty_derived=empty_derived,
            annotation_ready=annotation_ready,
            graph_ready=graph_ready,
            report_ready=report_ready,
            payload_eligible=payload_eligible,
        )

    def expired_initial_session(self) -> str:
        return SESSION_MESSAGES["expired_initial_session"]

    def saved_episode(self, reply: str, episode_count: int) -> str:
        return SESSION_MESSAGES["saved_episode"].format(
            reply=reply,
            episode_count=episode_count,
        )


def load_tone_engine(path: Path | str) -> ToneEngine:
    path = Path(path)
    if yaml is None or not path.exists():
        return ToneEngine.default()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ToneEngine.default()
    if not isinstance(data, dict):
        return ToneEngine.default()
    return ToneEngine(
        config=_deep_merge(DEFAULT_TONE_CONFIG, data),
        prompts=dict(TARGET_PROMPTS),
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _format_admin_profile(profile: dict[str, Any]) -> str:
    lines = []
    for field in ("username", "first_name", "last_name", "language_code", "is_bot"):
        value = profile.get(field)
        if value is not None and value != "":
            lines.append(f"{field}: {escape(str(value))}")
    if not lines:
        return ""
    return "\n" + "\n".join(lines)
