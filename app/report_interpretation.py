from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any

from app.insight_payload import InsightPayload
from app.report_cards import ReportCard, build_report_cards
from app.report_entities import ReportEntity, build_report_entities
from app.report_view_model import build_report_view_model
from app.report_text_layout import (
    append_report_block,
    report_content_length,
    report_header,
)


VERSION = "0.1"
SECTION_KINDS = (
    "main_pattern",
    "choice_or_exception",
    "outcomes",
    "change",
    "unexplained",
)
MAX_BRIEF_CHARS = 1400
MAX_EXPANDED_CHARS = 3600
_ANALYTICAL_KINDS = frozenset({"pattern", "exception", "change"})
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")

_ARTIFACT_SPECS = (
    ("pattern:dominant_motif", "dominant_motif", "main_pattern"),
    ("exception:fork", "fork", "choice_point"),
    ("exception:counterexample", "counterexample", "counterexample"),
    ("exception:contrast", "contrast", "contrast"),
    ("pattern:outcome_pattern", "outcome_pattern", "outcome_pattern"),
)
_QUESTION_ROLE_BY_CARD_KIND = {
    "main_pattern": "dominant_motif",
    "choice_point": "fork",
    "counterexample": "counterexample",
    "contrast": "contrast",
    "outcome_pattern": "outcome_pattern",
    "next_question": "next_observation",
}


@dataclass(frozen=True)
class InterpretationArtifact:
    artifact_id: str
    entity_kind: str
    role: str
    priority: int
    title: str
    claim: str
    evidence: tuple[str, ...] = ()
    support_count: int | None = None
    question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fact_text(self) -> str:
        return "\n".join(
            part
            for part in (
                self.claim,
                *self.evidence,
                str(self.support_count) if self.support_count is not None else "",
                self.question or "",
            )
            if part
        )


@dataclass(frozen=True)
class ReportInterpretationInput:
    kind: str
    version: str
    sample_line: str
    coverage_note: str
    artifacts: tuple[InterpretationArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version,
            "sample_line": self.sample_line,
            "coverage_note": self.coverage_note,
            "artifacts": tuple(item.to_dict() for item in self.artifacts),
        }

    def artifacts_by_id(self) -> dict[str, InterpretationArtifact]:
        return {item.artifact_id: item for item in self.artifacts}

    def analytical_artifacts(self) -> tuple[InterpretationArtifact, ...]:
        return tuple(
            item for item in self.artifacts if item.entity_kind in _ANALYTICAL_KINDS
        )


@dataclass(frozen=True)
class InterpretationBrief:
    synthesis: str
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class InterpretationSection:
    kind: str
    title: str
    synthesis: str
    artifact_ids: tuple[str, ...]
    evidence_note: str | None = None


@dataclass(frozen=True)
class InterpretationQuestion:
    text: str
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class InterpretationLimitation:
    text: str
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class NumericGroundingMismatch:
    field_path: str
    numbers: tuple[str, ...]
    artifact_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BriefReportInterpretation:
    brief: InterpretationBrief
    next_question: InterpretationQuestion | None


@dataclass(frozen=True)
class ExpandedReportInterpretation:
    sections: tuple[InterpretationSection, ...]
    next_question: InterpretationQuestion | None
    limitations: tuple[InterpretationLimitation, ...]


def build_report_interpretation_input(
    payload: InsightPayload,
) -> ReportInterpretationInput:
    entities = build_report_entities(payload).entities
    cards = build_report_cards(payload)
    view_model = build_report_view_model(payload)
    entities_by_role = {entity.role: entity for entity in entities}
    cards_by_kind = {card.kind: card for card in cards}
    artifacts: list[InterpretationArtifact] = []

    sample = entities_by_role["sample"]
    artifacts.append(
        InterpretationArtifact(
            artifact_id="evidence:sample",
            entity_kind="evidence",
            role="sample",
            priority=sample.priority,
            title="О данных",
            claim=view_model.sample_line,
            evidence=(view_model.coverage_note,) if view_model.coverage_note else (),
            support_count=sample.support_count,
        )
    )

    coverage_gap = entities_by_role.get("coverage_gap")
    if coverage_gap is not None:
        card = cards_by_kind.get("sample_status")
        artifacts.append(
            InterpretationArtifact(
                artifact_id="gap:coverage",
                entity_kind="gap",
                role="coverage_gap",
                priority=coverage_gap.priority,
                title=coverage_gap.title,
                claim=card.claim if card is not None else view_model.coverage_note,
                evidence=card.evidence if card is not None else (),
                support_count=coverage_gap.support_count,
            )
        )

    for artifact_id, role, card_kind in _ARTIFACT_SPECS:
        entity = entities_by_role.get(role)
        card = cards_by_kind.get(card_kind)
        if entity is None or card is None:
            continue
        artifacts.append(
            _artifact_from_entity_and_card(
                artifact_id,
                entity,
                card,
            )
        )

    for card in cards:
        if not card.question:
            continue
        role = _QUESTION_ROLE_BY_CARD_KIND.get(card.kind)
        if role is None:
            continue
        artifacts.append(
            InterpretationArtifact(
                artifact_id=f"question:{role}",
                entity_kind="question",
                role=role,
                priority=5,
                title=card.title,
                claim=card.question,
                question=card.question,
            )
        )

    return ReportInterpretationInput(
        kind="report_interpretation_input",
        version=VERSION,
        sample_line=view_model.sample_line,
        coverage_note=view_model.coverage_note,
        artifacts=tuple(
            sorted(
                artifacts,
                key=lambda item: (-item.priority, item.entity_kind, item.artifact_id),
            )
        ),
    )


def report_interpretation_is_eligible(
    interpretation_input: ReportInterpretationInput,
) -> bool:
    analytical = interpretation_input.analytical_artifacts()
    return len(analytical) >= 3 and any(
        item.entity_kind == "pattern" for item in analytical
    )


def render_interpretation_brief(
    interpretation_input: ReportInterpretationInput,
    interpretation: BriefReportInterpretation,
) -> str:
    lines = report_header(
        "Короткий отчет",
        (interpretation_input.sample_line, interpretation_input.coverage_note),
    )
    append_report_block(lines, (interpretation.brief.synthesis.strip(),))
    if interpretation.next_question is not None:
        append_report_block(
            lines,
            (f"Вопрос: {interpretation.next_question.text.strip()}",),
        )
    return "\n".join(lines).rstrip()


def render_interpretation_expanded(
    interpretation_input: ReportInterpretationInput,
    interpretation: ExpandedReportInterpretation,
) -> str:
    lines = report_header(
        "Подробный отчет",
        (interpretation_input.sample_line, interpretation_input.coverage_note),
    )

    for section in interpretation.sections:
        content = [section.synthesis.strip()]
        if section.evidence_note:
            content.extend(["", f"Основание: {section.evidence_note.strip()}"])
        append_report_block(lines, content, title=section.title.strip())

    if interpretation.limitations:
        append_report_block(
            lines,
            (f"- {item.text.strip()}" for item in interpretation.limitations),
            title="Ограничения",
        )

    if interpretation.next_question is not None:
        append_report_block(
            lines,
            (interpretation.next_question.text.strip(),),
            title="Что наблюдать дальше",
        )
    return "\n".join(lines).rstrip()


def brief_interpretation_violations(
    interpretation_input: ReportInterpretationInput,
    interpretation: BriefReportInterpretation,
) -> tuple[str, ...]:
    violations: list[str] = []
    artifacts_by_id = interpretation_input.artifacts_by_id()

    _validate_synthesis(
        interpretation.brief.synthesis,
        interpretation.brief.artifact_ids,
        artifacts_by_id,
        violations,
        minimum_sentences=2,
        maximum_sentences=5,
        maximum_length=1100,
    )
    if len(_analytical_ids(interpretation.brief.artifact_ids, artifacts_by_id)) < 2:
        violations.append("brief_does_not_synthesize")

    _validate_question(
        interpretation.next_question,
        artifacts_by_id,
        violations,
    )
    if report_content_length(
        render_interpretation_brief(interpretation_input, interpretation)
    ) > MAX_BRIEF_CHARS:
        violations.append("brief_too_long")
    return tuple(dict.fromkeys(violations))


def expanded_interpretation_violations(
    interpretation_input: ReportInterpretationInput,
    interpretation: ExpandedReportInterpretation,
) -> tuple[str, ...]:
    violations: list[str] = []
    artifacts_by_id = interpretation_input.artifacts_by_id()

    if not 2 <= len(interpretation.sections) <= 5:
        violations.append("section_count")
    section_kinds = [section.kind for section in interpretation.sections]
    if any(kind not in SECTION_KINDS for kind in section_kinds):
        violations.append("section_kind")
    if len(set(section_kinds)) != len(section_kinds):
        violations.append("duplicate_section_kind")
    if not section_kinds or section_kinds[0] != "main_pattern":
        violations.append("main_pattern_not_first")

    combined_section = False
    seen_analytical: set[str] = set()
    seen_syntheses: set[str] = set()
    for index, section in enumerate(interpretation.sections):
        _validate_grounded_text(
            section.title,
            section.artifact_ids,
            artifacts_by_id,
            violations,
            maximum_length=80,
        )
        _validate_synthesis(
            section.synthesis,
            section.artifact_ids,
            artifacts_by_id,
            violations,
            minimum_sentences=1,
            maximum_sentences=4,
            maximum_length=700,
        )
        analytical_ids = _analytical_ids(section.artifact_ids, artifacts_by_id)
        if not analytical_ids:
            violations.append("section_without_analytics")
        if len(analytical_ids) >= 2:
            combined_section = True
        if index > 0 and not (analytical_ids - seen_analytical):
            violations.append("section_repeats_artifacts")
        seen_analytical.update(analytical_ids)

        normalized = " ".join(section.synthesis.lower().split())
        if normalized in seen_syntheses:
            violations.append("repetitive_output")
        seen_syntheses.add(normalized)
        if section.evidence_note:
            _validate_grounded_text(
                section.evidence_note,
                section.artifact_ids,
                artifacts_by_id,
                violations,
                maximum_length=240,
            )
    if not combined_section:
        violations.append("sections_do_not_synthesize")

    _validate_question(
        interpretation.next_question,
        artifacts_by_id,
        violations,
    )

    if len(interpretation.limitations) > 3:
        violations.append("limitation_count")
    for limitation in interpretation.limitations:
        _validate_grounded_text(
            limitation.text,
            limitation.artifact_ids,
            artifacts_by_id,
            violations,
            maximum_length=280,
        )

    expanded_text = render_interpretation_expanded(
        interpretation_input,
        interpretation,
    )
    if report_content_length(expanded_text) > MAX_EXPANDED_CHARS:
        violations.append("expanded_too_long")
    return tuple(dict.fromkeys(violations))


def report_interpretation_numeric_mismatches(
    interpretation_input: ReportInterpretationInput,
    interpretation: BriefReportInterpretation | ExpandedReportInterpretation,
) -> tuple[NumericGroundingMismatch, ...]:
    artifacts_by_id = interpretation_input.artifacts_by_id()
    candidates: list[tuple[str, str, tuple[str, ...]]] = []
    if isinstance(interpretation, BriefReportInterpretation):
        candidates.append(
            (
                "brief.synthesis",
                interpretation.brief.synthesis,
                interpretation.brief.artifact_ids,
            )
        )
    else:
        for index, section in enumerate(interpretation.sections):
            candidates.extend(
                (
                    (f"sections[{index}].title", section.title, section.artifact_ids),
                    (
                        f"sections[{index}].synthesis",
                        section.synthesis,
                        section.artifact_ids,
                    ),
                )
            )
            if section.evidence_note:
                candidates.append(
                    (
                        f"sections[{index}].evidence_note",
                        section.evidence_note,
                        section.artifact_ids,
                    )
                )
    if interpretation.next_question is not None:
        candidates.append(
            (
                "next_question.text",
                interpretation.next_question.text,
                interpretation.next_question.artifact_ids,
            )
        )
    if isinstance(interpretation, ExpandedReportInterpretation):
        candidates.extend(
            (f"limitations[{index}].text", item.text, item.artifact_ids)
            for index, item in enumerate(interpretation.limitations)
        )

    mismatches: list[NumericGroundingMismatch] = []
    for field_path, text, artifact_ids in candidates:
        if not artifact_ids or any(
            artifact_id not in artifacts_by_id for artifact_id in artifact_ids
        ):
            continue
        allowed_numbers = {
            number
            for artifact_id in artifact_ids
            for number in _NUMBER_RE.findall(artifacts_by_id[artifact_id].fact_text())
        }
        unsupported_numbers = tuple(
            dict.fromkeys(
                number
                for number in _NUMBER_RE.findall(text)
                if number not in allowed_numbers
            )
        )
        if unsupported_numbers:
            mismatches.append(
                NumericGroundingMismatch(
                    field_path=field_path,
                    numbers=unsupported_numbers,
                    artifact_ids=artifact_ids,
                )
            )
    return tuple(mismatches)


def attach_global_sample_evidence(
    interpretation_input: ReportInterpretationInput,
    interpretation: BriefReportInterpretation | ExpandedReportInterpretation,
) -> BriefReportInterpretation | ExpandedReportInterpretation:
    sample = interpretation_input.artifacts_by_id().get("evidence:sample")
    if sample is None:
        return interpretation
    sample_numbers = frozenset(_NUMBER_RE.findall(sample.fact_text()))
    if not sample_numbers:
        return interpretation

    def refs_for(text: str, artifact_ids: tuple[str, ...]) -> tuple[str, ...]:
        if "evidence:sample" in artifact_ids:
            return artifact_ids
        if not sample_numbers.intersection(_NUMBER_RE.findall(text)):
            return artifact_ids
        return (*artifact_ids, "evidence:sample")

    next_question = interpretation.next_question
    if next_question is not None:
        next_question = replace(
            next_question,
            artifact_ids=refs_for(next_question.text, next_question.artifact_ids),
        )
    if isinstance(interpretation, BriefReportInterpretation):
        return replace(
            interpretation,
            brief=replace(
                interpretation.brief,
                artifact_ids=refs_for(
                    interpretation.brief.synthesis,
                    interpretation.brief.artifact_ids,
                ),
            ),
            next_question=next_question,
        )

    sections = tuple(
        replace(
            section,
            artifact_ids=refs_for(
                "\n".join(
                    part
                    for part in (
                        section.title,
                        section.synthesis,
                        section.evidence_note or "",
                    )
                    if part
                ),
                section.artifact_ids,
            ),
        )
        for section in interpretation.sections
    )
    limitations = tuple(
        replace(item, artifact_ids=refs_for(item.text, item.artifact_ids))
        for item in interpretation.limitations
    )
    return replace(
        interpretation,
        sections=sections,
        next_question=next_question,
        limitations=limitations,
    )


def _artifact_from_entity_and_card(
    artifact_id: str,
    entity: ReportEntity,
    card: ReportCard,
) -> InterpretationArtifact:
    return InterpretationArtifact(
        artifact_id=artifact_id,
        entity_kind=entity.kind,
        role=entity.role,
        priority=entity.priority,
        title=card.title,
        claim=card.claim,
        evidence=card.evidence,
        support_count=entity.support_count,
    )


def _validate_question(
    question: InterpretationQuestion | None,
    artifacts_by_id: dict[str, InterpretationArtifact],
    violations: list[str],
) -> None:
    if question is None:
        return
    _validate_grounded_text(
        question.text,
        question.artifact_ids,
        artifacts_by_id,
        violations,
        maximum_length=240,
    )
    if not question.text.strip().endswith("?"):
        violations.append("question_punctuation")
    question_ids = {
        artifact_id
        for artifact_id in question.artifact_ids
        if artifacts_by_id.get(artifact_id) is not None
        and artifacts_by_id[artifact_id].entity_kind == "question"
    }
    analytical_ids = _analytical_ids(question.artifact_ids, artifacts_by_id)
    if not question_ids or not analytical_ids:
        violations.append("question_not_grounded")


def _validate_synthesis(
    text: str,
    artifact_ids: tuple[str, ...],
    artifacts_by_id: dict[str, InterpretationArtifact],
    violations: list[str],
    *,
    minimum_sentences: int,
    maximum_sentences: int,
    maximum_length: int,
) -> None:
    _validate_grounded_text(
        text,
        artifact_ids,
        artifacts_by_id,
        violations,
        maximum_length=maximum_length,
    )
    sentence_count = len(_SENTENCE_END_RE.findall(text.strip()))
    if not minimum_sentences <= sentence_count <= maximum_sentences:
        violations.append("sentence_count")


def _validate_grounded_text(
    text: str,
    artifact_ids: tuple[str, ...],
    artifacts_by_id: dict[str, InterpretationArtifact],
    violations: list[str],
    *,
    maximum_length: int,
) -> None:
    stripped = text.strip()
    if not stripped or len(stripped) > maximum_length:
        violations.append("text_length")
    if not _CYRILLIC_RE.search(stripped):
        violations.append("non_russian_text")
    referenced = _referenced_artifacts(artifact_ids, artifacts_by_id, violations)
    if not referenced:
        return
    allowed_numbers = {
        number
        for artifact in referenced
        for number in _NUMBER_RE.findall(artifact.fact_text())
    }
    if any(number not in allowed_numbers for number in _NUMBER_RE.findall(stripped)):
        violations.append("unsupported_number")


def _referenced_artifacts(
    artifact_ids: tuple[str, ...],
    artifacts_by_id: dict[str, InterpretationArtifact],
    violations: list[str],
) -> tuple[InterpretationArtifact, ...]:
    if not artifact_ids or len(set(artifact_ids)) != len(artifact_ids):
        violations.append("artifact_ref_mismatch")
        return ()
    if any(artifact_id not in artifacts_by_id for artifact_id in artifact_ids):
        violations.append("artifact_ref_mismatch")
        return ()
    return tuple(artifacts_by_id[artifact_id] for artifact_id in artifact_ids)


def _analytical_ids(
    artifact_ids: tuple[str, ...],
    artifacts_by_id: dict[str, InterpretationArtifact],
) -> set[str]:
    return {
        artifact_id
        for artifact_id in artifact_ids
        if artifacts_by_id.get(artifact_id) is not None
        and artifacts_by_id[artifact_id].entity_kind in _ANALYTICAL_KINDS
    }
