from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.insight_payload import InsightPayload
from app.report_cards import ReportCard, build_report_cards
from app.report_text_layout import append_report_block, report_header


VERSION = "0.1"


@dataclass(frozen=True)
class ReportViewSection:
    kind: str
    title: str
    claim: str
    evidence: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()
    question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReportViewModel:
    kind: str
    version: str
    sample_line: str
    coverage_note: str
    summary_sections: tuple[ReportViewSection, ...]
    details_sections: tuple[ReportViewSection, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version,
            "sample_line": self.sample_line,
            "coverage_note": self.coverage_note,
            "summary_sections": tuple(
                section.to_dict() for section in self.summary_sections
            ),
            "details_sections": tuple(
                section.to_dict() for section in self.details_sections
            ),
        }


def build_report_view_model(payload: InsightPayload) -> ReportViewModel:
    cards = build_report_cards(payload)
    return ReportViewModel(
        kind="report_view_model",
        version=VERSION,
        sample_line=f"В выборке: {_episode_count(payload.sample.total_episodes)}.",
        coverage_note=_coverage_note(payload),
        summary_sections=tuple(_section(card) for card in _summary_cards(cards)),
        details_sections=tuple(_section(card) for card in cards),
    )


def render_summary_view(model: ReportViewModel) -> str:
    lines = report_header(
        "Короткий отчет",
        (model.sample_line, model.coverage_note),
    )

    for section in model.summary_sections:
        append_report_block(
            lines,
            _render_section_content(section, compact=True),
            title=section.title,
        )

    if not model.summary_sections:
        append_report_block(
            lines,
            ("Пока недостаточно обработанных эпизодов для аккуратного вывода.",),
        )
    return "\n".join(lines).rstrip()


def render_details_view(model: ReportViewModel) -> str:
    lines = report_header(
        "Подробный отчет",
        (model.sample_line, model.coverage_note),
    )
    for section in model.details_sections:
        append_report_block(
            lines,
            _render_section_content(section, compact=False),
            title=section.title,
        )
    if not model.details_sections:
        append_report_block(
            lines,
            ("Пока недостаточно обработанных эпизодов для аккуратного вывода.",),
        )
    return "\n".join(lines).rstrip()


def _section(card: ReportCard) -> ReportViewSection:
    return ReportViewSection(
        kind=card.kind,
        title=card.title,
        claim=card.claim,
        evidence=card.evidence,
        question=card.question,
    )


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


def _render_section_content(section: ReportViewSection, *, compact: bool) -> list[str]:
    lines = [section.claim]
    if section.evidence:
        lines.append("")
        lines.extend(f"- {line}" for line in section.evidence)
    if section.limits:
        lines.append("")
        lines.extend(f"- {line}" for line in section.limits)
    if section.question:
        if not compact or section.kind in {"main_pattern", "next_question"}:
            lines.append("")
            lines.append(f"Вопрос: {section.question}")
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
