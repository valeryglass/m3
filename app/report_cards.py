from __future__ import annotations

from dataclasses import dataclass

from app.insight_payload import InsightPayload, MotifPayload
from app.report_entities import ReportEntity, build_report_entities


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
class ReportCard:
    kind: str
    priority: int
    title: str
    claim: str
    evidence: tuple[str, ...] = ()
    question: str | None = None


def build_report_cards(payload: InsightPayload) -> tuple[ReportCard, ...]:
    report_entities = build_report_entities(payload)
    entities_by_role = {entity.role: entity for entity in report_entities.entities}
    cards = [card for card in _candidate_cards(payload, entities_by_role) if card is not None]
    return tuple(sorted(cards, key=lambda item: (-item.priority, item.kind)))


def _candidate_cards(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> list[ReportCard | None]:
    return [
        _main_pattern_card(payload, entities_by_role),
        _choice_point_card(payload, entities_by_role),
        _counterexample_card(payload, entities_by_role),
        _contrast_card(payload, entities_by_role),
        _outcome_card(payload, entities_by_role),
        _sample_status_card(payload, entities_by_role),
        _next_question_card(payload, entities_by_role),
    ]


def _sample_status_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    coverage = payload.coverage
    entity = entities_by_role.get("coverage_gap")
    if entity is None:
        return None
    return ReportCard(
        kind="sample_status",
        priority=entity.priority,
        title="О данных",
        claim=(
            f"Учтено {coverage.annotated_count} из "
            f"{coverage.observed_count} эпизодов."
        ),
        evidence=(f"{coverage.pending_count} ждут обработки.",),
    )


def _main_pattern_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    motif = payload.dominant_motif
    entity = entities_by_role.get("dominant_motif")
    if not motif or entity is None:
        return None
    return ReportCard(
        kind="main_pattern",
        priority=entity.priority,
        title="Главный повторяющийся сценарий",
        claim=_format_motif(motif),
        evidence=(f"Поддержка: {_episode_count(motif.support_count)}.",),
        question="Где в этой цепочке появляется выбор реакции?",
    )


def _choice_point_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    fork = payload.main_fork
    entity = entities_by_role.get("fork")
    if not fork or entity is None:
        return None
    variants = ", ".join(
        f"{_friendly(variant.behavior)} ({variant.support_count})"
        for variant in fork.variants
    )
    return ReportCard(
        kind="choice_point",
        priority=entity.priority,
        title="Точка выбора",
        claim=(
            f"{_format_pair((fork.trigger, fork.emotion))} "
            "не всегда заканчивается одинаково."
        ),
        evidence=(f"Варианты: {variants}.",),
        question="Что отличает разные варианты реакции?",
    )


def _counterexample_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    candidate = payload.counterexample
    entity = entities_by_role.get("counterexample")
    if not candidate or entity is None:
        return None
    base = _format_pair((candidate.trigger, candidate.emotion))
    return ReportCard(
        kind="counterexample",
        priority=entity.priority,
        title="Менее частый вариант",
        claim="В этой выборке есть другой вариант реакции.",
        evidence=(
            f"Чаще: {base} -> {_friendly(candidate.dominant.behavior)} "
            f"({candidate.dominant.support_count}).",
            f"Реже: {base} -> {_friendly(candidate.alternative.behavior)} "
            f"({candidate.alternative.support_count}).",
        ),
        question="Что позволило появиться другому варианту?",
    )


def _contrast_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    contrast = payload.contrast
    entity = entities_by_role.get("contrast")
    if not contrast or entity is None:
        return None
    trigger = _friendly(contrast.trigger)
    behavior = _friendly(contrast.behavior)
    return ReportCard(
        kind="contrast",
        priority=entity.priority,
        title="Контраст",
        claim=f"Одна реакция — {behavior} — встречалась при разных эмоциях.",
        evidence=(
            f"{trigger} -> {_friendly(contrast.left.emotion)} -> {behavior} "
            f"({contrast.left.support_count}).",
            f"{trigger} -> {_friendly(contrast.right.emotion)} -> {behavior} "
            f"({contrast.right.support_count}).",
        ),
        question="Что общего у этих эпизодов, кроме реакции?",
    )


def _outcome_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    entity = entities_by_role.get("outcome_pattern")
    if not payload.outcome_patterns or entity is None:
        return None
    return ReportCard(
        kind="outcome_pattern",
        priority=entity.priority,
        title="Что обычно получается после реакции",
        claim="В этих данных видны повторяющиеся итоги действий.",
        evidence=tuple(
            f"{OUTCOME_HORIZON_LABELS[pattern.horizon]}: "
            f"{_friendly(pattern.behavior)} -> {_friendly(pattern.outcome)}: "
            f"{pattern.support_count} из {_case_count(pattern.total_count)}."
            for pattern in payload.outcome_patterns[:3]
        ),
        question="Этот итог помогает или просто завершает эпизод?",
    )


def _next_question_card(
    payload: InsightPayload,
    entities_by_role: dict[str, ReportEntity],
) -> ReportCard | None:
    entity = entities_by_role.get("next_observation")
    if entity is None:
        return None
    return ReportCard(
        kind="next_question",
        priority=entity.priority,
        title="Что понаблюдать дальше",
        claim="Сейчас полезнее смотреть на момент выбора реакции.",
        evidence=(
            "Повторяющийся сценарий показывает форму.",
            "Развилка показывает место выбора.",
        ),
        question="Что обычно происходит прямо перед повторяющейся реакцией?",
    )


def _friendly(value: str) -> str:
    return FRIENDLY_LABELS.get(value, value)


def _format_motif(motif: MotifPayload) -> str:
    return f"{_friendly(motif.trigger)} -> {_friendly(motif.emotion)} -> {_friendly(motif.behavior)}"


def _format_pair(pair: tuple[str, str]) -> str:
    first, second = pair
    return f"{_friendly(first)} -> {_friendly(second)}"


def _episode_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'эпизод', 'эпизода', 'эпизодов')}"


def _case_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'случая', 'случаев', 'случаев')}"


def _plural_ru(number: int, one: str, few: str, many: str) -> str:
    number = abs(number)
    if number % 100 in (11, 12, 13, 14):
        return many
    if number % 10 == 1:
        return one
    if number % 10 in (2, 3, 4):
        return few
    return many
