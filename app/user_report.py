from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from app.graph_report import GraphReport


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
    if trigger:
        lines.append(f"Основной контекст: {_friendly(trigger)}.")
    if emotion:
        lines.append(f"Частая эмоция: {_friendly_join(emotion)}.")
    if behavior:
        lines.append(f"Частая реакция: {_friendly_join(behavior)}.")
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
        _stable_scenarios(report),
        _outcome_observations(report),
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


def _outcome_observations(report: GraphReport) -> list[str]:
    counter: Counter[tuple[str, str]] = Counter()
    for sig in report.graph_ready:
        for behavior in sig.behaviors:
            for outcome in sig.short_outcomes + sig.long_outcomes:
                counter[(behavior, outcome)] += 1
    items = _sorted_counter_items(counter)[:3]
    if not items:
        return []
    lines = ["Наблюдаемые итоги"]
    lines.extend(
        f"- {_friendly(behavior)} -> {_friendly(outcome)}: {_episode_count(count)}"
        for (behavior, outcome), count in items
    )
    return lines


def _what_to_notice(report: GraphReport) -> list[str]:
    trigger = _top_value(_trigger_counter(report))
    emotion = _top_signature(report.emotion_signatures)
    behavior = _top_signature(report.behavior_signatures)
    if not (trigger and emotion and behavior):
        return []
    return [
        "Что заметить",
        "- чаще всего отдельно встречаются: "
        f"{_friendly(trigger)}, {_friendly_join(emotion)}, {_friendly_join(behavior)}",
        "- может быть полезно понаблюдать, совпадает ли это с главным "
        "повторяющимся сценарием.",
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
    counter: Counter[str] = Counter()
    for sig in report.graph_ready:
        counter.update(sig.triggers)
    return counter


def _loop_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    counter[(trigger, emotion, behavior)] += 1
    return counter


def _behavior_forks(report: GraphReport) -> dict[tuple[str, str], Counter[str]]:
    forks: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    forks[(trigger, emotion)][behavior] += 1
    return dict(forks)


def _top_loop(report: GraphReport) -> tuple[tuple[str, str, str] | None, int]:
    items = _sorted_counter_items(_loop_counter(report))
    return items[0] if items else (None, 0)


def _top_value(counter: Counter[str]) -> str | None:
    items = _sorted_counter_items(counter)
    return items[0][0] if items else None


def _top_signature(counter: Counter[tuple[str, ...]]) -> tuple[str, ...] | None:
    items = _sorted_counter_items(counter)
    return items[0][0] if items else None


def _sorted_counter_items(counter) -> list[tuple]:
    return sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))


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
