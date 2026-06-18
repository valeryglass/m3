from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.graph_report import GraphReport
from app.pattern_metrics import (
    behavior_forks as _metric_behavior_forks,
    loop_counter as _metric_loop_counter,
    outcome_support_counter as _metric_outcome_support_counter,
    outcome_totals_by_behavior_horizon as _metric_outcome_totals,
    sorted_counter_items as _metric_sorted_counter_items,
    top_contrast as _metric_top_contrast,
    top_counterexample as _metric_top_counterexample,
    top_loop as _metric_top_loop,
    trigger_counter as _metric_trigger_counter,
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
    return UserReport(
        summary_text=render_summary(report),
        details_text=render_details(report),
    )


def render_summary(report: GraphReport) -> str:
    trigger = _top_value(_trigger_counter(report))
    emotion = _top_signature(report.emotion_signatures)
    behavior = _top_signature(report.behavior_signatures)
    loop, loop_count = _top_loop(report)

    lines = [
        "Короткий отчет",
        "",
        f"В выборке: {_episode_count(report.total_episodes)}.",
    ]
    coverage_note = _coverage_note(report)
    if coverage_note:
        lines.append(coverage_note)
    background = _sample_background(trigger, emotion, behavior)
    if background:
        lines.append(background)
    if loop:
        lines.append(
            "Повторяющийся сценарий: "
            f"{_format_loop(loop)} ({_episode_count(loop_count)})."
        )

    lines.extend(["", "Наблюдение:", _summary_observation(loop)])
    return "\n".join(lines)


def render_details(report: GraphReport) -> str:
    lines = ["Подробный отчет", ""]
    sections = [
        _current_picture(report),
        _repeating_pattern(report),
        _main_fork(report),
        _counterexample_observation(report),
        _contrast_observation(report),
        _outcome_observations(report),
        _stable_scenarios(report),
        _what_to_notice(report),
        _reflection_questions(report),
        _conclusion(report),
    ]
    for section in sections:
        if not section:
            continue
        if lines[-1] != "":
            lines.append("")
        lines.extend(section)
    return "\n".join(lines).rstrip()


def _current_picture(report: GraphReport) -> list[str]:
    trigger = _top_value(_trigger_counter(report))
    emotion = _top_signature(report.emotion_signatures)
    behavior = _top_signature(report.behavior_signatures)
    items = []
    if trigger:
        items.append(f"контекст — {_friendly(trigger)}")
    if emotion:
        items.append(f"эмоция — {_friendly_join(emotion)}")
    if behavior:
        items.append(f"реакция — {_friendly_join(behavior)}")
    if not items:
        return []
    lines = [
        "Текущая картина",
        *[f"- {item}" for item in items],
    ]
    coverage_note = _coverage_note(report)
    if coverage_note:
        lines.append(f"- {coverage_note}")
    return lines


def _repeating_pattern(report: GraphReport) -> list[str]:
    loop, count = _top_loop(report)
    if not loop:
        return []
    return [
        "Повторяющийся сценарий",
        f"- {_format_loop(loop)}",
        f"- поддержка: {_episode_count(count)}",
    ]


def _main_fork(report: GraphReport) -> list[str]:
    forks = _behavior_forks(report)
    candidates = [
        (context, behaviors)
        for context, behaviors in forks.items()
        if len(behaviors) > 1
    ]
    if not candidates:
        return []
    context, behaviors = sorted(
        candidates,
        key=lambda item: (-sum(item[1].values()), _format_pair(item[0])),
    )[0]
    behavior_text = ", ".join(
        f"{_friendly(behavior)} ({count})"
        for behavior, count in _sorted_counter_items(behaviors)
    )
    return [
        "Развилка реакций",
        f"- {_format_pair(context)}",
        f"- варианты: {behavior_text}",
    ]


def _stable_scenarios(report: GraphReport) -> list[str]:
    loops = _loop_counter(report)
    repeated = [
        (loop, count)
        for loop, count in _sorted_counter_items(loops)
        if count >= 2
    ][:3]
    if not repeated:
        return []
    lines = ["Устойчивые сценарии"]
    lines.extend(
        f"- {_format_loop(loop)}: {_episode_count(count)}"
        for loop, count in repeated
    )
    return lines


def _counterexample_observation(report: GraphReport) -> list[str]:
    candidate = _metric_top_counterexample(report)
    if not candidate:
        return []
    base = _format_pair(candidate.base)
    return [
        "Менее частый вариант",
        f"- в этой выборке чаще: {base} -> "
        f"{_friendly(candidate.dominant_behavior)} ({candidate.dominant_count})",
        f"- реже встречалось: {base} -> "
        f"{_friendly(candidate.alternative_behavior)} ({candidate.alternative_count})",
    ]


def _outcome_observations(report: GraphReport) -> list[str]:
    counter = _metric_outcome_support_counter(report)
    totals = _metric_outcome_totals(report)
    items = _sorted_counter_items(counter)[:3]
    if not items:
        return []
    lines = ["Наблюдаемые итоги"]
    lines.extend(
        f"- {OUTCOME_HORIZON_LABELS[horizon]}: "
        f"{_friendly(behavior)} -> {_friendly(outcome)}: "
        f"{count} из {_case_count(totals[(behavior, horizon)])}"
        for (behavior, horizon, outcome), count in items
    )
    return lines


def _contrast_observation(report: GraphReport) -> list[str]:
    candidate = _metric_top_contrast(report)
    if not candidate:
        return []
    trigger = _friendly(candidate.trigger)
    behavior = _friendly(candidate.behavior)
    return [
        "Контраст",
        "- в этой выборке одна реакция встречалась при разных эмоциях: "
        f"{trigger} -> {_friendly(candidate.left_emotion)} -> {behavior} "
        f"({candidate.left_count}) и "
        f"{trigger} -> {_friendly(candidate.right_emotion)} -> {behavior} "
        f"({candidate.right_count})",
    ]


def _what_to_notice(report: GraphReport) -> list[str]:
    if not report.graph_ready:
        return []
    return [
        "Что заметить",
        "- полезнее смотреть на развилки и итоги, а не только на частые слова.",
        "- повторяющийся сценарий показывает форму, развилка — место выбора.",
    ]


def _reflection_questions(report: GraphReport) -> list[str]:
    if not report.graph_ready:
        return []
    return [
        "Вопросы для наблюдения",
        "- в какой момент реакция начинает повторяться?",
        "- что обычно происходит сразу перед ней?",
        "- какие варианты действия уже появлялись в похожих ситуациях?",
    ]


def _conclusion(report: GraphReport) -> list[str]:
    if not report.graph_ready:
        return [
            "Итог",
            "Пока недостаточно обработанных эпизодов для аккуратного вывода.",
        ]
    return [
        "Итог",
        "похоже, сейчас полезнее всего смотреть не на один эпизод, "
        "а на повторяющиеся связки ситуации, эмоции и реакции.",
    ]


def _sample_background(
    trigger: str | None,
    emotion: tuple[str, ...] | None,
    behavior: tuple[str, ...] | None,
) -> str:
    parts = []
    if trigger:
        parts.append(_friendly(trigger))
    if emotion:
        parts.append(_friendly_join(emotion))
    if behavior:
        parts.append(_friendly_join(behavior))
    if not parts:
        return ""
    return "Фон выборки: " + "; ".join(parts) + "."


def _summary_observation(
    loop: tuple[str, str, str] | None,
) -> str:
    if not loop:
        return (
            "похоже, данных пока немного; может быть полезно понаблюдать, "
            "какие ситуации повторяются чаще всего."
        )
    return (
        "в этих данных видно повторяющуюся связку: "
        f"«{_format_loop(loop)}». "
        "Может быть полезно понаблюдать, в какой точке этой цепочки "
        "появляется выбор реакции."
    )


def _trigger_counter(report: GraphReport) -> Counter[str]:
    return _metric_trigger_counter(report)


def _loop_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    return _metric_loop_counter(report)


def _behavior_forks(report: GraphReport) -> dict[tuple[str, str], Counter[str]]:
    return _metric_behavior_forks(report)


def _top_loop(report: GraphReport) -> tuple[tuple[str, str, str] | None, int]:
    return _metric_top_loop(report)


def _top_value(counter: Counter[str]) -> str | None:
    items = _sorted_counter_items(counter)
    return items[0][0] if items else None


def _top_signature(counter: Counter[tuple[str, ...]]) -> tuple[str, ...] | None:
    items = _sorted_counter_items(counter)
    return items[0][0] if items else None


def _sorted_counter_items(counter) -> list[tuple]:
    return _metric_sorted_counter_items(counter)


def _friendly(value: str) -> str:
    return FRIENDLY_LABELS.get(value, value)


def _friendly_join(values: tuple[str, ...]) -> str:
    return " + ".join(_friendly(value) for value in values) if values else "нет данных"


def _format_loop(loop: tuple[str, str, str]) -> str:
    trigger, emotion, behavior = loop
    return f"{_friendly(trigger)} -> {_friendly(emotion)} -> {_friendly(behavior)}"


def _format_pair(pair: tuple[str, str]) -> str:
    first, second = pair
    return f"{_friendly(first)} -> {_friendly(second)}"


def _episode_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'эпизод', 'эпизода', 'эпизодов')}"


def _case_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'случая', 'случаев', 'случаев')}"


def _coverage_note(report: GraphReport) -> str:
    coverage = report.coverage
    if coverage.coverage != "partial" or coverage.pending_count <= 0:
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
