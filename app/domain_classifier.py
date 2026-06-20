from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.episode import DomainAnnotation, Episode, LifeDomain


CLASSIFIER_VERSION = "life-domain-rules-v1"
PRIMARY_CONFIDENCE = 0.85
SECONDARY_CONFIDENCE = 0.75
UNKNOWN_CONFIDENCE = 0.5

DOMAIN_KEYWORDS: dict[LifeDomain, tuple[str, ...]] = {
    "work_study": (
        "работ",
        "офис",
        "коллег",
        "началь",
        "клиент",
        "дедлайн",
        "задач",
        "учеб",
        "экзам",
        "универс",
        "курс",
        "work",
        "office",
        "colleague",
        "study",
        "exam",
    ),
    "close_relationships_family": (
        "партнер",
        "партнёр",
        "муж",
        "жен",
        "девуш",
        "парен",
        "семь",
        "мам",
        "пап",
        "родител",
        "ребен",
        "ребён",
        "отношен",
        "расстав",
        "partner",
        "family",
        "relationship",
    ),
    "health_body": (
        "здоров",
        "врач",
        "болез",
        "боль",
        "симптом",
        "лечен",
        "лекар",
        "сон",
        "тело",
        "устал",
        "health",
        "doctor",
        "pain",
        "sleep",
    ),
    "money_resources": (
        "деньг",
        "зарплат",
        "долг",
        "кредит",
        "бюджет",
        "оплат",
        "цен",
        "покуп",
        "финанс",
        "money",
        "salary",
        "debt",
        "budget",
    ),
    "home_daily_life": (
        "дом",
        "квартир",
        "уборк",
        "быт",
        "ремонт",
        "готов",
        "магазин",
        "продукт",
        "рутин",
        "house",
        "home",
        "clean",
        "chores",
    ),
    "projects_creativity": (
        "проект",
        "творч",
        "рисова",
        "музык",
        "писа",
        "иде",
        "прототип",
        "код",
        "приложен",
        "project",
        "creative",
        "music",
        "writing",
        "prototype",
    ),
    "social_public": (
        "друг",
        "компан",
        "вечерин",
        "групп",
        "чат",
        "публич",
        "соцсет",
        "незнаком",
        "встреч",
        "friend",
        "party",
        "group chat",
        "public",
        "social",
    ),
    "unknown": (),
}


@dataclass(frozen=True)
class DomainDecision:
    annotations: tuple[DomainAnnotation, ...]
    needs_review: bool
    candidate_domains: tuple[LifeDomain, ...]


def classify_episode_domains(episode: Episode) -> DomainDecision:
    fields = _evidence_fields(episode)
    scores: dict[LifeDomain, int] = {}
    situation_scores: dict[LifeDomain, int] = {}
    evidence: dict[LifeDomain, tuple[str, str]] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain == "unknown":
            continue
        score = 0
        best: tuple[int, str, str] | None = None
        for source_field, text, weight in fields:
            lowered = text.lower()
            hits = _keyword_hits(lowered, keywords)
            if not hits:
                continue
            weighted = hits * weight
            score += weighted
            if source_field == "observed.situation":
                situation_scores[domain] = situation_scores.get(domain, 0) + weighted
            candidate = (weighted, source_field, text)
            if best is None or candidate > best:
                best = candidate
        if score and situation_scores.get(domain, 0):
            scores[domain] = score
            assert best is not None
            evidence[domain] = (best[1], best[2])

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ordered:
        return DomainDecision(
            annotations=(_unknown_annotation(episode),),
            needs_review=True,
            candidate_domains=(),
        )
    primary_domain, primary_score = ordered[0]
    tied = len(ordered) > 1 and ordered[1][1] == primary_score
    if situation_scores.get(primary_domain, 0) < 3 or tied:
        return DomainDecision(
            annotations=(_unknown_annotation(episode),),
            needs_review=True,
            candidate_domains=tuple(domain for domain, _score in ordered[:3]),
        )

    annotations = [
        _annotation(
            1,
            primary_domain,
            "primary",
            "deterministic_rule",
            evidence[primary_domain],
            PRIMARY_CONFIDENCE,
        )
    ]
    if len(ordered) > 1:
        secondary_domain, secondary_score = ordered[1]
        if secondary_score >= 3 and primary_score - secondary_score >= 2:
            annotations.append(
                _annotation(
                    2,
                    secondary_domain,
                    "secondary",
                    "deterministic_rule",
                    evidence[secondary_domain],
                    SECONDARY_CONFIDENCE,
                )
            )
    return DomainDecision(
        annotations=tuple(annotations),
        needs_review=False,
        candidate_domains=tuple(domain for domain, _score in ordered[:3]),
    )


def reviewed_domain_annotations(
    episode: Episode,
    *,
    primary_domain: LifeDomain,
    primary_source_field: str,
    secondary_domain: LifeDomain | None = None,
    secondary_source_field: str | None = None,
) -> tuple[DomainAnnotation, ...]:
    annotations = [
        _annotation(
            1,
            primary_domain,
            "primary",
            "explicit_review",
            _review_evidence(episode, primary_source_field),
            0.9 if primary_domain != "unknown" else UNKNOWN_CONFIDENCE,
        )
    ]
    if secondary_domain is not None:
        if secondary_source_field is None:
            raise ValueError("secondary_source_field is required")
        annotations.append(
            _annotation(
                2,
                secondary_domain,
                "secondary",
                "explicit_review",
                _review_evidence(episode, secondary_source_field),
                0.8,
            )
        )
    return tuple(annotations)


def _evidence_fields(episode: Episode) -> tuple[tuple[str, str, int], ...]:
    observed = episode.observed
    fields = [("observed.situation", observed.situation.source_quote, 3)]
    for name in ("trigger", "actor", "quote"):
        value = getattr(observed, name)
        if value is not None and value.source_quote.strip():
            fields.append((f"observed.{name}", value.source_quote, 1))
    return tuple(fields)


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    tokens = re.findall(r"[\wё]+", text)
    return sum(
        1
        for keyword in keywords
        if (
            keyword in text
            if " " in keyword
            else any(token.startswith(keyword) for token in tokens)
        )
    )


def _review_evidence(episode: Episode, source_field: str) -> tuple[str, str]:
    allowed = {
        "observed.situation": episode.observed.situation,
        "observed.trigger": episode.observed.trigger,
        "observed.actor": episode.observed.actor,
        "observed.quote": episode.observed.quote,
    }
    if source_field not in allowed:
        raise ValueError(f"unsupported domain evidence field: {source_field}")
    value = allowed[source_field]
    if value is None or not value.source_quote.strip():
        raise ValueError(f"missing domain evidence: {source_field}")
    return source_field, value.source_quote


def _unknown_annotation(episode: Episode) -> DomainAnnotation:
    return _annotation(
        1,
        "unknown",
        "primary",
        "deterministic_rule",
        ("observed.situation", episode.observed.situation.source_quote),
        UNKNOWN_CONFIDENCE,
    )


def _annotation(
    index: int,
    domain: LifeDomain,
    role: str,
    method: str,
    evidence: tuple[str, str],
    confidence: float,
) -> DomainAnnotation:
    source_field, source_quote = evidence
    return DomainAnnotation(
        id=f"domain-annotation-{index}",
        domain=domain,
        role=role,
        method=method,
        source_field=source_field,
        source_quote=source_quote,
        confidence=confidence,
    )
