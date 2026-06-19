from __future__ import annotations

from dataclasses import dataclass

from app.graph_report import GraphReport
from app.insight_payload import (
    BackgroundPayload,
    ContrastPayload,
    CounterexamplePayload,
    ForkPayload,
    InsightPayload,
    MotifPayload,
    OutcomePatternPayload,
    build_insight_payload,
)


INTERNAL_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)

FRIENDLY_LABELS = {
    "social": "контакт с людьми",
    "external": "внешняя ситуация",
    "thought": "мысли",
    "memory": "воспоминание",
    "physical": "телесное состояние",
    "internal": "внутреннее состояние",
    "approach": "идти в действие",
    "avoid": "дистанцироваться",
    "freeze": "замирать",
    "distract": "отвлекаться",
    "attack": "атаковать",
    "compensate": "компенсировать",
    "submit": "уступать",
    "neutral_mixed": "смешанный итог",
    "нейтраль/мешанные": "нейтральные/смешанные",
    "relief": "облегчение",
    "unresolved": "без ясного завершения",
    "escalation": "усиление напряжения",
    "learning": "опыт/понимание",
    "control": "больше контроля",
    "connection": "контакт/связь",
    "avoidance_cost": "цена дистанции",
}

OUTCOME_HORIZON_LABELS = {
    "short_term": "сразу",
    "long_term": "позже",
}


@dataclass(frozen=True)
class UserReport:
    summary_text: str
    details_text: str


def build_user_report(report: GraphReport) -> UserReport:
    payload = build_insight_payload(report)
    return UserReport(
        summary_text=render_summary_from_payload(payload),
        details_text=render_details_from_payload(payload),
    )


def render_summary(report: GraphReport) -> str:
    return render_summary_from_payload(build_insight_payload(report))


def render_details(report: GraphReport) -> str:
    return render_details_from_payload(build_insight_payload(report))


def render_summary_from_payload(payload: InsightPayload) -> str:
    lines = [
        "Короткий отчет",
        "",
        f"В выборке: {_episode_count(payload.sample.total_episodes)}.",
    ]
    coverage_note = _coverage_note(payload)
    if coverage_note:
        lines.append(coverage_note)
    background = _sample_background(payload.background)
    if background:
        lines.append(background)
    if payload.dominant_motif:
        lines.append(
            "Повторяющийся сценарий: "
            f"{_format_motif(payload.dominant_motif)} "
            f"({_episode_count(payload.dominant_motif.support_count)})."
        )

    lines.extend(["", "Наблюдение:", _summary_observation(payload.dominant_motif)])
    return "\n".join(lines)


def render_details_from_payload(payload: InsightPayload) -> str:
    lines = ["Подробный отчет", ""]
    sections = [
        _current_picture(payload),
        _repeating_pattern(payload.dominant_motif),
        _main_fork(payload.main_fork),
        _counterexample_observation(payload.counterexample),
        _contrast_observation(payload.contrast),
        _outcome_observations(payload.outcome_patterns),
        _stable_scenarios(payload.stable_motifs),
        _what_to_notice(payload),
        _reflection_questions(payload),
        _conclusion(payload),
    ]
    for section in sections:
        if not section:
            continue
        if lines[-1] != "":
            lines.append("")
        lines.extend(section)
    return "\n".join(lines).rstrip()


def _current_picture(payload: InsightPayload) -> list[str]:
    background = payload.background
    items = []
    if background.trigger:
        items.append(f"контекст — {_friendly(background.trigger)}")
    if background.emotions:
        items.append(f"эмоция — {_friendly_join(background.emotions)}")
    if background.behaviors:
        items.append(f"реакция — {_friendly_join(background.behaviors)}")
    if not items:
        return []
    lines = ["Текущая картина", *[f"- {item}" for item in items]]
    coverage_note = _coverage_note(payload)
    if coverage_note:
        lines.append(f"- {coverage_note}")
    return lines


def _repeating_pattern(motif: MotifPayload | None) -> list[str]:
    if not motif:
        return []
    return [
        "Повторяющийся сценарий",
        f"- {_format_motif(motif)}",
        f"- поддержка: {_episode_count(motif.support_count)}",
    ]


def _main_fork(fork: ForkPayload | None) -> list[str]:
    if not fork:
        return []
    behavior_text = ", ".join(
        f"{_friendly(variant.behavior)} ({variant.support_count})"
        for variant in fork.variants
    )
    return [
        "Развилка реакций",
        f"- {_format_pair((fork.trigger, fork.emotion))}",
        f"- варианты: {behavior_text}",
    ]


def _counterexample_observation(
    candidate: CounterexamplePayload | None,
) -> list[str]:
    if not candidate:
        return []
    base = _format_pair((candidate.trigger, candidate.emotion))
    return [
        "Менее частый вариант",
        f"- в этой выборке чаще: {base} -> "
        f"{_friendly(candidate.dominant.behavior)} ({candidate.dominant.support_count})",
        f"- реже встречалось: {base} -> "
        f"{_friendly(candidate.alternative.behavior)} "
        f"({candidate.alternative.support_count})",
    ]


def _contrast_observation(candidate: ContrastPayload | None) -> list[str]:
    if not candidate:
        return []
    trigger = _friendly(candidate.trigger)
    behavior = _friendly(candidate.behavior)
    return [
        "Контраст",
        "- в этой выборке одна реакция встречалась при разных эмоциях: "
        f"{trigger} -> {_friendly(candidate.left.emotion)} -> {behavior} "
        f"({candidate.left.support_count}) и "
        f"{trigger} -> {_friendly(candidate.right.emotion)} -> {behavior} "
        f"({candidate.right.support_count})",
    ]


def _outcome_observations(
    outcome_patterns: tuple[OutcomePatternPayload, ...],
) -> list[str]:
    if not outcome_patterns:
        return []
    lines = ["Наблюдаемые итоги"]
    lines.extend(
        f"- {OUTCOME_HORIZON_LABELS[pattern.horizon]}: "
        f"{_friendly(pattern.behavior)} -> {_friendly(pattern.outcome)}: "
        f"{pattern.support_count} из {_case_count(pattern.total_count)}"
        for pattern in outcome_patterns
    )
    return lines


def _stable_scenarios(motifs: tuple[MotifPayload, ...]) -> list[str]:
    if not motifs:
        return []
    lines = ["Устойчивые сценарии"]
    lines.extend(
        f"- {_format_motif(motif)}: {_episode_count(motif.support_count)}"
        for motif in motifs
    )
    return lines


def _what_to_notice(payload: InsightPayload) -> list[str]:
    if payload.sample.graph_ready_count <= 0:
        return []
    return [
        "Что заметить",
        "- полезнее смотреть на развилки и итоги, а не только на частые слова.",
        "- повторяющийся сценарий показывает форму, развилка — место выбора.",
    ]


def _reflection_questions(payload: InsightPayload) -> list[str]:
    if payload.sample.graph_ready_count <= 0:
        return []
    return [
        "Вопросы для наблюдения",
        "- в какой момент реакция начинает повторяться?",
        "- что обычно происходит сразу перед ней?",
        "- какие варианты действия уже появлялись в похожих ситуациях?",
    ]


def _conclusion(payload: InsightPayload) -> list[str]:
    if payload.sample.graph_ready_count <= 0:
        return [
            "Итог",
            "Пока недостаточно обработанных эпизодов для аккуратного вывода.",
        ]
    return [
        "Итог",
        "похоже, сейчас полезнее всего смотреть не на один эпизод, "
        "а на повторяющиеся связки ситуации, эмоции и реакции.",
    ]


def _sample_background(background: BackgroundPayload) -> str:
    parts = []
    if background.trigger:
        parts.append(_friendly(background.trigger))
    if background.emotions:
        parts.append(_friendly_join(background.emotions))
    if background.behaviors:
        parts.append(_friendly_join(background.behaviors))
    if not parts:
        return ""
    return "Фон выборки: " + "; ".join(parts) + "."


def _summary_observation(motif: MotifPayload | None) -> str:
    if not motif:
        return (
            "похоже, данных пока немного; может быть полезно понаблюдать, "
            "какие ситуации повторяются чаще всего."
        )
    return (
        "в этих данных видно повторяющуюся связку: "
        f"«{_format_motif(motif)}». "
        "Может быть полезно понаблюдать, в какой точке этой цепочки "
        "появляется выбор реакции."
    )


def _friendly(value: str) -> str:
    return FRIENDLY_LABELS.get(value, value)


def _friendly_join(values: tuple[str, ...]) -> str:
    return " + ".join(_friendly(value) for value in values) if values else "нет данных"


def _format_motif(motif: MotifPayload) -> str:
    return f"{_friendly(motif.trigger)} -> {_friendly(motif.emotion)} -> {_friendly(motif.behavior)}"


def _format_pair(pair: tuple[str, str]) -> str:
    first, second = pair
    return f"{_friendly(first)} -> {_friendly(second)}"


def _episode_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'эпизод', 'эпизода', 'эпизодов')}"


def _case_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'случая', 'случаев', 'случаев')}"


def _coverage_note(payload: InsightPayload) -> str:
    coverage = payload.coverage
    if coverage.state != "partial" or coverage.pending_count <= 0:
        return ""
    return (
        f"Учтено {coverage.annotated_count} из {coverage.observed_count} эпизодов; "
        f"{coverage.pending_count} ждут обработки."
    )


def _plural_ru(number: int, one: str, few: str, many: str) -> str:
    number = abs(number)
    if number % 100 in (11, 12, 13, 14):
        return many
    if number % 10 == 1:
        return one
    if number % 10 in (2, 3, 4):
        return few
    return many
