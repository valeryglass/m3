from __future__ import annotations

from dataclasses import dataclass

from app.graph_report import GraphReport
from app.insight_payload import InsightPayload, build_insight_payload
from app.report_cards import ReportCard, build_report_cards


INTERNAL_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)


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
    cards = build_report_cards(payload)
    lines = [
        "Короткий отчет",
        "",
        f"В выборке: {_episode_count(payload.sample.total_episodes)}.",
    ]
    coverage_note = _coverage_note(payload)
    if coverage_note:
        lines.append(coverage_note)

    for card in _summary_cards(cards):
        if lines[-1] != "":
            lines.append("")
        lines.extend(_render_card(card, compact=True))

    if len(lines) == 3:
        lines.extend(["", "Пока недостаточно обработанных эпизодов для аккуратного вывода."])
    return "\n".join(lines).rstrip()


def render_details_from_payload(payload: InsightPayload) -> str:
    cards = build_report_cards(payload)
    lines = ["Подробный отчет", ""]
    for card in cards:
        if lines[-1] != "":
            lines.append("")
        lines.extend(_render_card(card, compact=False))
    if len(lines) == 2:
        lines.append("Пока недостаточно обработанных эпизодов для аккуратного вывода.")
    return "\n".join(lines).rstrip()


def _summary_cards(cards: tuple[ReportCard, ...]) -> tuple[ReportCard, ...]:
    selected: list[ReportCard] = []
    main = _first_card(cards, "main_pattern")
    if main:
        selected.append(main)

    for kind in ("choice_point", "counterexample", "contrast", "outcome_pattern"):
        card = _first_card(cards, kind)
        if card:
            selected.append(card)
            break

    question = _first_card(cards, "next_question")
    if question:
        selected.append(question)
    return tuple(selected)


def _first_card(cards: tuple[ReportCard, ...], kind: str) -> ReportCard | None:
    for card in cards:
        if card.kind == kind:
            return card
    return None


def _render_card(card: ReportCard, *, compact: bool) -> list[str]:
    lines = [card.title, "", card.claim]
    if card.evidence:
        lines.append("")
        lines.extend(f"- {line}" for line in card.evidence)
    if card.question:
        if not compact or card.kind in {"main_pattern", "next_question"}:
            lines.append("")
            lines.append(f"Вопрос: {card.question}")
    return lines


def _coverage_note(payload: InsightPayload) -> str:
    coverage = payload.coverage
    if coverage.state != "partial" or coverage.pending_count <= 0:
        return ""
    return (
        f"Учтено {coverage.annotated_count} из {coverage.observed_count} эпизодов; "
        f"{coverage.pending_count} ждут обработки."
    )


def _episode_count(count: int) -> str:
    return f"{count} {_plural_ru(count, 'эпизод', 'эпизода', 'эпизодов')}"


def _plural_ru(number: int, one: str, few: str, many: str) -> str:
    number = abs(number)
    if number % 100 in (11, 12, 13, 14):
        return many
    if number % 10 == 1:
        return one
    if number % 10 in (2, 3, 4):
        return few
    return many
