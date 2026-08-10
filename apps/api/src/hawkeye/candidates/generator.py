"""Evidence-backed, local-only candidate generation for Engine V0.2."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from hawkeye.extraction.links import normalize_exact_asset_url
from hawkeye.models import (
    CandidateCorpusExclusion,
    CandidateCorpusSnapshot,
    CandidateDocument,
    CandidateEvidenceReference,
    CandidateObservation,
    CandidateReason,
    CandidateRecord,
    CaseRecord,
    CrawlFrontierRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    RedirectRecord,
)

from .normalization import (
    CandidateTarget,
    candidate_target_from_url,
    hostname_from_observed_url,
    is_common_asset_provider,
    is_common_external_reference,
    is_generic_referral_signal,
)

ReasonType = Literal[
    "external_link",
    "external_redirect",
    "external_discovery",
    "shared_telegram",
    "shared_whatsapp_or_phone",
    "shared_referral",
    "shared_exact_asset_url",
]
SignalQuality = Literal["observed", "strong", "medium", "weak"]
Direction = Literal["source_to_candidate", "undirected"]
DiscoveryMethod = Literal[
    "html_anchor",
    "network_redirect",
    "public_source",
    "local_corpus_match",
]

MAX_SHARED_SIGNAL_DOMAINS = 3
_SHARED_SIGNAL_TYPES = frozenset(
    {"telegram", "whatsapp_or_phone", "referral", "external_asset_url"}
)
_REASON_BY_SIGNAL: dict[str, ReasonType] = {
    "telegram": "shared_telegram",
    "whatsapp_or_phone": "shared_whatsapp_or_phone",
    "referral": "shared_referral",
    "external_asset_url": "shared_exact_asset_url",
}
_BASE_WEIGHT_BY_REASON: dict[ReasonType, int] = {
    "external_redirect": 30,
    "external_link": 10,
    "external_discovery": 5,
    "shared_telegram": 35,
    "shared_whatsapp_or_phone": 30,
    "shared_referral": 15,
    "shared_exact_asset_url": 20,
}


@dataclass(frozen=True)
class CandidateGeneration:
    """The two persisted V0.2 candidate artifacts for one completed or failed case."""

    document: CandidateDocument
    observations: list[CandidateObservation]


@dataclass(frozen=True)
class _CorpusEntity:
    """One usable historical entity that can corroborate a current signal."""

    case_id: str
    candidate: CandidateTarget
    observed_hosts: tuple[str, ...]
    source_page_id: str | None
    entity: ExtractedEntity


@dataclass(frozen=True)
class _CorpusLoad:
    """Accepted corpus facts plus a stable snapshot manifest for reproducible candidate output."""

    entities: list[_CorpusEntity]
    case_ids: list[str]
    manifest_sha256: str
    exclusions: list[CandidateCorpusExclusion]


@dataclass
class _ReasonBuilder:
    """Mutable aggregation that becomes one portable, immutable candidate reason."""

    reason_type: ReasonType
    signal_value: str | None
    weight: int
    signal_quality: SignalQuality
    corpus_frequency: int
    corpus_case_count: int
    corpus_domain_count: int
    direction: Direction
    discovery_method: DiscoveryMethod
    source_case_ids: set[str] = field(default_factory=set)
    source_urls: set[str] = field(default_factory=set)
    supporting_evidence_ids: set[str] = field(default_factory=set)
    supporting_evidence_refs: dict[tuple[str, str, str], CandidateEvidenceReference] = field(
        default_factory=dict
    )
    source_observation_ids: set[str] = field(default_factory=set)

    def include(self, observation: CandidateObservation) -> None:
        self.source_case_ids.add(observation.source_case_id)
        self.source_urls.add(observation.source_url)
        if observation.source_evidence_id is not None:
            self.supporting_evidence_ids.add(observation.source_evidence_id)
            reference = CandidateEvidenceReference(
                case_id=observation.source_case_id,
                evidence_id=observation.source_evidence_id,
                observation_id=observation.id,
            )
            self.supporting_evidence_refs[
                (reference.case_id, reference.evidence_id, reference.observation_id)
            ] = reference
        self.source_observation_ids.add(observation.id)

    def build(self) -> CandidateReason:
        return CandidateReason(
            reason_type=self.reason_type,
            signal_value=self.signal_value,
            weight=self.weight,
            signal_quality=self.signal_quality,
            corpus_frequency=self.corpus_frequency,
            corpus_case_count=self.corpus_case_count,
            corpus_domain_count=self.corpus_domain_count,
            source_case_ids=sorted(self.source_case_ids),
            source_urls=sorted(self.source_urls),
            supporting_evidence_ids=sorted(self.supporting_evidence_ids),
            supporting_evidence_refs=sorted(
                self.supporting_evidence_refs.values(),
                key=lambda reference: (
                    reference.case_id,
                    reference.evidence_id,
                    reference.observation_id,
                ),
            ),
            source_observation_ids=sorted(self.source_observation_ids),
            direction=self.direction,
            discovery_method=self.discovery_method,
        )


@dataclass
class _CandidateBuilder:
    """Aggregate observations for one exact candidate hostname."""

    target: CandidateTarget
    scope_relation: Literal["different_registrable_domain", "same_registrable_domain_external_host"]
    observed_hosts: set[str] = field(default_factory=set)
    reasons: dict[tuple[ReasonType, str | None], _ReasonBuilder] = field(default_factory=dict)

    def include_host(self, hostname: str) -> None:
        self.observed_hosts.add(hostname)

    def include_reason(
        self,
        *,
        reason_type: ReasonType,
        signal_value: str | None,
        weight: int,
        signal_quality: SignalQuality,
        corpus_frequency: int,
        corpus_case_count: int,
        corpus_domain_count: int,
        direction: Direction,
        discovery_method: DiscoveryMethod,
        observations: Iterable[CandidateObservation],
    ) -> None:
        key = (reason_type, signal_value)
        reason = self.reasons.get(key)
        if reason is None:
            reason = _ReasonBuilder(
                reason_type=reason_type,
                signal_value=signal_value,
                weight=weight,
                signal_quality=signal_quality,
                corpus_frequency=corpus_frequency,
                corpus_case_count=corpus_case_count,
                corpus_domain_count=corpus_domain_count,
                direction=direction,
                discovery_method=discovery_method,
            )
            self.reasons[key] = reason
        for observation in observations:
            reason.include(observation)

    def build(self) -> CandidateRecord:
        reasons = sorted(
            (reason.build() for reason in self.reasons.values()),
            key=lambda reason: (reason.reason_type, reason.signal_value or ""),
        )
        # Repeated pages, repeated anchors, and even multiple different values of the same signal
        # type must not inflate this discovery-priority score. Reasons retain every observation.
        score_by_type: dict[str, int] = {}
        for reason in reasons:
            score_by_type[reason.reason_type] = max(
                score_by_type.get(reason.reason_type, 0), reason.weight
            )
        return CandidateRecord(
            candidate_id=f"candidate-host:{self.target.hostname}",
            hostname=self.target.hostname,
            registrable_domain=self.target.registrable_domain,
            suffix_type=self.target.suffix_type,
            scope_relation=self.scope_relation,
            observed_hosts=sorted(self.observed_hosts),
            discovery_priority_score=min(100, sum(score_by_type.values())),
            reasons=reasons,
        )


def generate_candidates(
    *,
    case: CaseRecord,
    pages: list[CrawlPageRecord],
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
    frontier: list[CrawlFrontierRecord],
    corpus_root: Path | str | None,
    current_case_directory: Path,
) -> CandidateGeneration:
    """Generate pending domains from saved observations and an optional local case corpus.

    The function is deliberately pure with respect to the network and does not enqueue, validate,
    or browse any candidate. Corpus facts are accepted only from completed cases whose originating
    HTML evidence belongs to a usable page.
    """

    source_case_target, _ = _case_target(case)
    source_hosts = _source_hosts(case=case, pages=pages)
    usable_entities = _usable_entities(pages=pages, evidence=evidence, entities=entities)
    evidence_by_id = {record.id: record for record in evidence}
    page_by_id = {page.id: page for page in pages}
    observations: dict[str, CandidateObservation] = {}
    candidates: dict[str, _CandidateBuilder] = {}

    def record(observation: CandidateObservation) -> CandidateObservation:
        observations.setdefault(observation.id, observation)
        return observations[observation.id]

    def candidate_for(target: CandidateTarget) -> _CandidateBuilder:
        builder = candidates.get(target.hostname)
        if builder is None:
            builder = _CandidateBuilder(
                target=target,
                scope_relation=_scope_relation(target, source_case_target),
                observed_hosts={target.hostname},
            )
            candidates[target.hostname] = builder
        else:
            builder.include_host(target.hostname)
        return builder

    for entity in usable_entities:
        if entity.type != "external_link":
            continue
        target, rejection = candidate_target_from_url(entity.normalized_value)
        decision, exclusion = _candidate_decision(target, rejection, source_hosts)
        if target is not None and is_common_external_reference(target.hostname):
            decision, exclusion = "excluded", "common_external_reference"
        observation = record(
            _observation(
                observation_type="external_link",
                source_case_id=case.case_id,
                source_page_id=_page_id_for_evidence(evidence_by_id, entity.source_evidence_id),
                source_evidence_id=entity.source_evidence_id,
                source_url=entity.source_url,
                target_url=entity.normalized_value,
                target_host=(
                    target.hostname
                    if target is not None
                    else hostname_from_observed_url(entity.value)
                ),
                direction="source_to_candidate",
                discovery_method="html_anchor",
                candidate_decision=decision,
                exclusion_reason=exclusion,
                details=_external_link_context(entity),
            )
        )
        if target is None or decision != "accepted":
            continue
        candidate_for(target).include_reason(
            reason_type="external_link",
            signal_value=None,
            weight=_BASE_WEIGHT_BY_REASON["external_link"],
            signal_quality="observed",
            corpus_frequency=0,
            corpus_case_count=0,
            corpus_domain_count=0,
            direction="source_to_candidate",
            discovery_method="html_anchor",
            observations=[observation],
        )

    observed_network_redirects: set[tuple[str, str]] = set()
    for source_page in sorted(pages, key=lambda page: page.id):
        redirect_evidence_id = source_page.redirect_evidence_id
        evidence_record = evidence_by_id.get(redirect_evidence_id or "")
        if evidence_record is None or evidence_record.type != "network_event":
            continue
        for redirect in source_page.redirects:
            observed_network_redirects.add((redirect_evidence_id or "", redirect.destination_url))
            target, rejection = candidate_target_from_url(redirect.destination_url)
            decision, exclusion = _candidate_decision(target, rejection, source_hosts)
            if redirect.resource_type != "document" or not redirect.is_top_level_navigation:
                decision, exclusion = "excluded", "non_top_level_or_non_document_redirect"
            observation = record(
                _observation(
                    observation_type="external_redirect",
                    source_case_id=case.case_id,
                    source_page_id=source_page.id,
                    source_evidence_id=redirect_evidence_id,
                    source_url=redirect.source_url,
                    target_url=redirect.destination_url,
                    target_host=(
                        target.hostname
                        if target is not None
                        else hostname_from_observed_url(redirect.destination_url)
                    ),
                    direction="source_to_candidate",
                    discovery_method="network_redirect",
                    candidate_decision=decision,
                    exclusion_reason=exclusion,
                    details=_redirect_details(redirect),
                )
            )
            if target is None or decision != "accepted":
                continue
            candidate_for(target).include_reason(
                reason_type="external_redirect",
                signal_value=None,
                weight=_BASE_WEIGHT_BY_REASON["external_redirect"],
                signal_quality="observed",
                corpus_frequency=0,
                corpus_case_count=0,
                corpus_domain_count=0,
                direction="source_to_candidate",
                discovery_method="network_redirect",
                observations=[observation],
            )

    for record_frontier in sorted(frontier, key=lambda item: item.id):
        if record_frontier.discovery_method != "redirect" or not record_frontier.normalized_url:
            continue
        if (
            record_frontier.source_evidence_id or "",
            record_frontier.normalized_url,
        ) in observed_network_redirects:
            continue
        evidence_record = evidence_by_id.get(record_frontier.source_evidence_id or "")
        if evidence_record is None or evidence_record.type != "network_event":
            continue
        target, _ = candidate_target_from_url(record_frontier.normalized_url)
        frontier_source_page = page_by_id.get(record_frontier.source_page_id or "")
        source_url = (
            frontier_source_page.final_url or frontier_source_page.normalized_url
            if frontier_source_page is not None
            else evidence_record.source_url
        )
        observation = record(
            _observation(
                observation_type="external_redirect",
                source_case_id=case.case_id,
                source_page_id=record_frontier.source_page_id,
                source_evidence_id=record_frontier.source_evidence_id,
                source_url=source_url,
                target_url=record_frontier.normalized_url,
                target_host=(
                    target.hostname
                    if target is not None
                    else hostname_from_observed_url(record_frontier.normalized_url)
                ),
                direction="source_to_candidate",
                discovery_method="network_redirect",
                candidate_decision="excluded",
                exclusion_reason="insufficient_redirect_context",
                details={
                    "status_code": (
                        str(record_frontier.redirect_status_code)
                        if record_frontier.redirect_status_code is not None
                        else ""
                    ),
                    "resolved_target_url": record_frontier.normalized_url,
                },
            )
        )

    current_shared = [entity for entity in usable_entities if entity.type in _SHARED_SIGNAL_TYPES]
    eligible_current_shared: list[ExtractedEntity] = []
    for entity in current_shared:
        exclusion = _shared_signal_exclusion(entity)
        if exclusion is None:
            eligible_current_shared.append(entity)
            continue
        record(
            _observation(
                observation_type="signal",
                source_case_id=case.case_id,
                source_page_id=_page_id_for_evidence(evidence_by_id, entity.source_evidence_id),
                source_evidence_id=entity.source_evidence_id,
                source_url=entity.source_url,
                target_url=entity.normalized_value if entity.type == "external_asset_url" else None,
                target_host=(
                    hostname_from_observed_url(entity.normalized_value)
                    if entity.type == "external_asset_url"
                    else None
                ),
                signal_type=entity.type,
                signal_value=entity.normalized_value,
                direction="undirected",
                discovery_method="local_corpus_match",
                candidate_decision="excluded",
                exclusion_reason=exclusion,
            )
        )

    corpus = _load_corpus(
        corpus_root=Path(corpus_root) if corpus_root is not None else None,
        current_case_id=case.case_id,
        current_case_directory=current_case_directory,
    )
    corpus_by_signal: dict[tuple[str, str], list[_CorpusEntity]] = defaultdict(list)
    for historical in corpus.entities:
        if _shared_signal_exclusion(historical.entity) is None:
            corpus_by_signal[
                (historical.entity.type, _shared_signal_value(historical.entity))
            ].append(historical)

    for current in sorted(
        eligible_current_shared,
        key=lambda entity: (entity.type, _shared_signal_value(entity), entity.id),
    ):
        signal_value = _shared_signal_value(current)
        key = (current.type, signal_value)
        matches = sorted(
            corpus_by_signal.get(key, []),
            key=lambda item: (item.candidate.hostname, item.case_id, item.entity.id),
        )
        if not matches:
            continue
        frequency, case_count, domain_count = _corpus_metrics(matches)
        if domain_count > MAX_SHARED_SIGNAL_DOMAINS:
            record(
                _observation(
                    observation_type="signal",
                    source_case_id=case.case_id,
                    source_page_id=_page_id_for_evidence(
                        evidence_by_id, current.source_evidence_id
                    ),
                    source_evidence_id=current.source_evidence_id,
                    source_url=current.source_url,
                    signal_type=current.type,
                    signal_value=signal_value,
                    direction="undirected",
                    discovery_method="local_corpus_match",
                    candidate_decision="excluded",
                    exclusion_reason=(f"common_signal_across_{domain_count}_corpus_domains"),
                )
            )
            continue

        reason_type = _REASON_BY_SIGNAL[current.type]
        quality = _shared_signal_quality(current.type, frequency, case_count, domain_count)
        weight = _quality_adjusted_weight(_BASE_WEIGHT_BY_REASON[reason_type], quality)
        by_candidate: dict[str, list[_CorpusEntity]] = defaultdict(list)
        for historical in matches:
            by_candidate[historical.candidate.hostname].append(historical)

        for domain in sorted(by_candidate):
            historical_matches = by_candidate[domain]
            target = historical_matches[0].candidate
            decision, exclusion = _candidate_decision(target, None, source_hosts)
            current_observation = record(
                _observation(
                    observation_type="signal",
                    source_case_id=case.case_id,
                    source_page_id=_page_id_for_evidence(
                        evidence_by_id, current.source_evidence_id
                    ),
                    source_evidence_id=current.source_evidence_id,
                    source_url=current.source_url,
                    target_url=_candidate_target_url(historical_matches[0]),
                    target_host=target.hostname,
                    signal_type=current.type,
                    signal_value=signal_value,
                    direction="undirected",
                    discovery_method="local_corpus_match",
                    candidate_decision=decision,
                    exclusion_reason=exclusion,
                )
            )
            historical_observations = [
                record(
                    _observation(
                        observation_type="signal",
                        source_case_id=historical.case_id,
                        source_page_id=historical.source_page_id,
                        source_evidence_id=historical.entity.source_evidence_id,
                        source_url=historical.entity.source_url,
                        target_url=_candidate_target_url(historical),
                        target_host=target.hostname,
                        signal_type=historical.entity.type,
                        signal_value=_shared_signal_value(historical.entity),
                        direction="undirected",
                        discovery_method="local_corpus_match",
                        candidate_decision=decision,
                        exclusion_reason=exclusion,
                    )
                )
                for historical in historical_matches
            ]
            if decision != "accepted":
                continue
            builder = candidate_for(target)
            for historical in historical_matches:
                for hostname in historical.observed_hosts:
                    builder.include_host(hostname)
            builder.include_reason(
                reason_type=reason_type,
                signal_value=signal_value,
                weight=weight,
                signal_quality=quality,
                corpus_frequency=frequency,
                corpus_case_count=case_count,
                corpus_domain_count=domain_count,
                direction="undirected",
                discovery_method="local_corpus_match",
                observations=[current_observation, *historical_observations],
            )

    candidate_records = sorted(
        (builder.build() for builder in candidates.values()),
        key=lambda candidate: (-candidate.discovery_priority_score, candidate.hostname),
    )
    observation_records = sorted(observations.values(), key=lambda observation: observation.id)
    document = CandidateDocument(
        source_case_id=case.case_id,
        candidates=candidate_records,
        excluded_observation_count=sum(
            observation.candidate_decision == "excluded" for observation in observation_records
        ),
        corpus=CandidateCorpusSnapshot(
            case_ids=corpus.case_ids,
            case_count=len(corpus.case_ids),
            manifest_sha256=corpus.manifest_sha256,
            generated_at=datetime.now(UTC),
            excluded_cases=corpus.exclusions,
        ),
    )
    return CandidateGeneration(document=document, observations=observation_records)


def generate_external_discovery_candidates(
    *,
    case: CaseRecord,
    source_hosts: set[str],
    observations: list[CandidateObservation],
) -> CandidateGeneration:
    """Apply the V0.2 candidate identity, suppression, deduplication, and scoring rules.

    V0.4 source adapters supply raw, evidence-linked observations only. This function deliberately
    reuses V0.2's exact-host candidate shape and a low, standalone priority reason instead of
    creating a second candidate schema or asserting any relationship.
    """

    source_case_target, _ = _case_target(case)
    candidates: dict[str, _CandidateBuilder] = {}
    normalized_observations: list[CandidateObservation] = []

    def candidate_for(target: CandidateTarget) -> _CandidateBuilder:
        builder = candidates.get(target.hostname)
        if builder is None:
            builder = _CandidateBuilder(
                target=target,
                scope_relation=_scope_relation(target, source_case_target),
                observed_hosts={target.hostname},
            )
            candidates[target.hostname] = builder
        else:
            builder.include_host(target.hostname)
        return builder

    for observation in sorted(observations, key=lambda item: item.id):
        if (
            observation.observation_type != "external_discovery"
            or observation.discovery_method != "public_source"
        ):
            raise ValueError(
                "External discovery candidate input must use public_source observations"
            )
        target, rejection = candidate_target_from_url(observation.target_url or "")
        decision, exclusion = _candidate_decision(target, rejection, source_hosts)
        normalized = observation.model_copy(
            update={
                "target_host": (
                    target.hostname
                    if target is not None
                    else hostname_from_observed_url(observation.target_url or "")
                ),
                "candidate_decision": decision,
                "exclusion_reason": exclusion,
            }
        )
        normalized_observations.append(normalized)
        if target is None or decision != "accepted":
            continue
        candidate_for(target).include_reason(
            reason_type="external_discovery",
            signal_value=None,
            weight=_BASE_WEIGHT_BY_REASON["external_discovery"],
            signal_quality="observed",
            corpus_frequency=0,
            corpus_case_count=0,
            corpus_domain_count=0,
            direction="source_to_candidate",
            discovery_method="public_source",
            observations=[normalized],
        )

    candidate_records = sorted(
        (builder.build() for builder in candidates.values()),
        key=lambda candidate: (-candidate.discovery_priority_score, candidate.hostname),
    )
    observation_records = sorted(normalized_observations, key=lambda observation: observation.id)
    return CandidateGeneration(
        document=CandidateDocument(
            source_case_id=case.case_id,
            candidates=candidate_records,
            excluded_observation_count=sum(
                observation.candidate_decision == "excluded" for observation in observation_records
            ),
            corpus=CandidateCorpusSnapshot(
                case_ids=[],
                case_count=0,
                manifest_sha256=hashlib.sha256(b"").hexdigest(),
                generated_at=datetime.now(UTC),
                excluded_cases=[],
            ),
        ),
        observations=observation_records,
    )


def _candidate_decision(
    target: CandidateTarget | None,
    rejection: str | None,
    source_hosts: set[str],
) -> tuple[Literal["accepted", "excluded"], str | None]:
    if target is None:
        return "excluded", rejection or "invalid_candidate_target"
    if target.hostname in source_hosts:
        return "excluded", "same_observed_host_as_source"
    return "accepted", None


def _observation(
    *,
    observation_type: Literal[
        "external_link",
        "external_redirect",
        "external_discovery",
        "signal",
    ],
    source_case_id: str,
    source_page_id: str | None,
    source_evidence_id: str | None,
    source_url: str,
    target_url: str | None = None,
    target_host: str | None = None,
    signal_type: str | None = None,
    signal_value: str | None = None,
    direction: Direction,
    discovery_method: DiscoveryMethod,
    candidate_decision: Literal["accepted", "excluded"],
    exclusion_reason: str | None,
    details: dict[str, str] | None = None,
) -> CandidateObservation:
    """Create a content-addressed observation ID so ordering cannot alter its identity."""

    normalized_details = dict(sorted((details or {}).items()))
    material = "\x1f".join(
        (
            observation_type,
            source_case_id,
            source_page_id or "",
            source_evidence_id or "",
            source_url,
            target_url or "",
            target_host or "",
            signal_type or "",
            signal_value or "",
            direction,
            discovery_method,
            candidate_decision,
            exclusion_reason or "",
            json.dumps(
                normalized_details, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ),
        )
    )
    return CandidateObservation(
        id=f"candidate-observation-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}",
        observation_type=observation_type,
        source_case_id=source_case_id,
        source_page_id=source_page_id,
        source_evidence_id=source_evidence_id,
        source_url=source_url,
        target_url=target_url,
        target_host=target_host,
        signal_type=signal_type,
        signal_value=signal_value,
        direction=direction,
        discovery_method=discovery_method,
        candidate_decision=candidate_decision,
        exclusion_reason=exclusion_reason,
        details=normalized_details,
    )


def _usable_entities(
    *,
    pages: list[CrawlPageRecord],
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    evidence_by_id = {record.id: record for record in evidence}
    usable_evidence_ids = {
        page.html_evidence_id
        for page in pages
        if page.state == "completed" and page.content_usable is True and page.html_evidence_id
    }
    return sorted(
        (
            entity
            for entity in entities
            if entity.source_evidence_id in usable_evidence_ids
            and evidence_by_id.get(entity.source_evidence_id) is not None
            and evidence_by_id[entity.source_evidence_id].type == "html_page"
        ),
        key=lambda entity: (entity.type, entity.normalized_value, entity.id),
    )


def _page_id_for_evidence(
    evidence_by_id: dict[str, EvidenceRecord], evidence_id: str
) -> str | None:
    record = evidence_by_id.get(evidence_id)
    return record.page_id if record is not None else None


def _shared_signal_exclusion(entity: ExtractedEntity) -> str | None:
    if entity.type == "external_asset_url" and is_common_asset_provider(
        hostname_from_observed_url(_shared_signal_value(entity))
    ):
        return "common_asset_provider"
    if entity.type == "referral" and is_generic_referral_signal(entity.normalized_value):
        return "generic_referral_signal"
    return None


def _shared_signal_value(entity: ExtractedEntity) -> str:
    """Canonicalize exact assets at comparison time, including older local-corpus artifacts."""

    if entity.type != "external_asset_url":
        return entity.normalized_value
    normalized = normalize_exact_asset_url(entity.value, entity.source_url)
    if normalized is None:
        return entity.normalized_value
    return normalized[1]


def _external_link_context(entity: ExtractedEntity) -> dict[str, str]:
    """Retain passive anchor context so a human can distinguish a footer reference from a lead."""

    return {
        key: entity.details[key]
        for key in ("anchor_text", "rel", "source_region")
        if entity.details.get(key)
    }


def _redirect_details(redirect: RedirectRecord) -> dict[str, str]:
    """Retain the redirect protocol facts needed to review a score-30 observation."""

    return {
        "resource_type": redirect.resource_type,
        "is_top_level_navigation": str(redirect.is_top_level_navigation).lower(),
        "status_code": str(redirect.status_code) if redirect.status_code is not None else "",
        "raw_location": redirect.raw_location or "",
        "resolved_target_url": redirect.destination_url,
    }


def _corpus_metrics(matches: list[_CorpusEntity]) -> tuple[int, int, int]:
    return (
        len(matches),
        len({match.case_id for match in matches}),
        len({match.candidate.registrable_domain for match in matches}),
    )


def _shared_signal_quality(
    signal_type: str, frequency: int, case_count: int, domain_count: int
) -> SignalQuality:
    if signal_type in {"telegram", "whatsapp_or_phone"}:
        return "strong" if frequency == case_count == domain_count == 1 else "medium"
    if signal_type == "external_asset_url":
        return "strong" if frequency == case_count == domain_count == 1 else "medium"
    return "medium" if frequency == case_count == domain_count == 1 else "weak"


def _quality_adjusted_weight(base_weight: int, quality: SignalQuality) -> int:
    if quality in {"observed", "strong"}:
        return base_weight
    if quality == "medium":
        return max(1, round(base_weight * 0.65))
    return max(1, round(base_weight * 0.35))


def _candidate_target_url(historical: _CorpusEntity) -> str:
    """Use the historical evidence page URL as the actionable, auditable target observation."""

    return historical.entity.source_url


def _case_target(case: CaseRecord) -> tuple[CandidateTarget | None, str | None]:
    url = case.final_url or case.seed_url
    return candidate_target_from_url(url)


def _source_hosts(*, case: CaseRecord, pages: list[CrawlPageRecord]) -> set[str]:
    """Return every exact host already observed as part of the source investigation."""

    hosts = {
        hostname
        for hostname in (
            hostname_from_observed_url(case.seed_url),
            hostname_from_observed_url(case.final_url or ""),
        )
        if hostname is not None
    }
    for page in pages:
        hostname = hostname_from_observed_url(page.final_url or page.normalized_url)
        if hostname is not None:
            hosts.add(hostname)
    return hosts


def _scope_relation(
    target: CandidateTarget, source_case_target: CandidateTarget | None
) -> Literal["different_registrable_domain", "same_registrable_domain_external_host"]:
    if (
        source_case_target is not None
        and target.registrable_domain == source_case_target.registrable_domain
    ):
        return "same_registrable_domain_external_host"
    return "different_registrable_domain"


def _load_corpus(
    *,
    corpus_root: Path | None,
    current_case_id: str,
    current_case_directory: Path,
) -> _CorpusLoad:
    """Load only completed, evidence-valid sibling cases from a local corpus root."""

    if corpus_root is None or not corpus_root.exists() or not corpus_root.is_dir():
        return _CorpusLoad(
            entities=[],
            case_ids=[],
            manifest_sha256=hashlib.sha256(b"").hexdigest(),
            exclusions=[],
        )
    try:
        normalized_current = current_case_directory.resolve()
    except OSError:
        normalized_current = current_case_directory
    directories = (
        [corpus_root]
        if (corpus_root / "case.json").is_file()
        else sorted(
            (entry for entry in corpus_root.iterdir() if entry.is_dir()),
            key=lambda entry: entry.name.casefold(),
        )
    )
    loaded: list[_CorpusEntity] = []
    manifest_entries: list[tuple[str, str]] = []
    exclusions: list[CandidateCorpusExclusion] = []
    seen_case_ids: set[str] = set()
    for directory in directories:
        try:
            if directory.resolve() == normalized_current:
                continue
        except OSError:
            continue
        records = _load_one_case(directory)
        if records is None:
            exclusions.append(
                CandidateCorpusExclusion(
                    directory_name=directory.name,
                    reason="malformed_or_incompatible_case_artifacts",
                )
            )
            continue
        historical_case, historical_pages, historical_evidence, historical_entities = records
        if historical_case.case_id == current_case_id or historical_case.case_id in seen_case_ids:
            if historical_case.case_id != current_case_id:
                exclusions.append(
                    CandidateCorpusExclusion(
                        directory_name=directory.name,
                        case_id=historical_case.case_id,
                        reason="duplicate_case_id",
                    )
                )
            continue
        seen_case_ids.add(historical_case.case_id)
        if historical_case.status != "completed":
            exclusions.append(
                CandidateCorpusExclusion(
                    directory_name=directory.name,
                    case_id=historical_case.case_id,
                    reason="case_not_completed",
                )
            )
            continue
        target, _ = _case_target(historical_case)
        if target is None:
            exclusions.append(
                CandidateCorpusExclusion(
                    directory_name=directory.name,
                    case_id=historical_case.case_id,
                    reason="case_target_not_registrable",
                )
            )
            continue
        usable = _usable_entities(
            pages=historical_pages,
            evidence=historical_evidence,
            entities=historical_entities,
        )
        if not usable:
            exclusions.append(
                CandidateCorpusExclusion(
                    directory_name=directory.name,
                    case_id=historical_case.case_id,
                    reason="no_usable_html_evidence",
                )
            )
            continue
        if not _has_intact_source_artifacts(directory, historical_evidence, usable):
            exclusions.append(
                CandidateCorpusExclusion(
                    directory_name=directory.name,
                    case_id=historical_case.case_id,
                    reason="missing_or_modified_source_artifact",
                )
            )
            continue
        manifest_entries.append(
            (
                historical_case.case_id,
                _corpus_case_fingerprint(
                    case=historical_case,
                    pages=historical_pages,
                    evidence=historical_evidence,
                    entities=historical_entities,
                ),
            )
        )
        observed_hosts = {target.hostname}
        for entity in usable:
            hostname = hostname_from_observed_url(entity.source_url)
            if hostname is not None:
                observed_hosts.add(hostname)
        evidence_by_id = {record.id: record for record in historical_evidence}
        normalized_observed_hosts = tuple(sorted(observed_hosts))
        for entity in usable:
            if entity.type in _SHARED_SIGNAL_TYPES:
                loaded.append(
                    _CorpusEntity(
                        case_id=historical_case.case_id,
                        candidate=target,
                        observed_hosts=normalized_observed_hosts,
                        source_page_id=_page_id_for_evidence(
                            evidence_by_id, entity.source_evidence_id
                        ),
                        entity=entity,
                    )
                )
    manifest_material = "\n".join(
        f"{case_id}\x1f{fingerprint}" for case_id, fingerprint in sorted(manifest_entries)
    )
    return _CorpusLoad(
        entities=loaded,
        case_ids=sorted(case_id for case_id, _ in manifest_entries),
        manifest_sha256=hashlib.sha256(manifest_material.encode("utf-8")).hexdigest(),
        exclusions=sorted(
            exclusions,
            key=lambda exclusion: (
                exclusion.case_id or "",
                exclusion.directory_name,
                exclusion.reason,
            ),
        ),
    )


def _corpus_case_fingerprint(
    *,
    case: CaseRecord,
    pages: list[CrawlPageRecord],
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
) -> str:
    """Hash original persisted facts, never prior candidate or comparison-derived outputs."""

    payload = {
        "case": case.model_dump(mode="json"),
        "pages": [page.model_dump(mode="json") for page in pages],
        "evidence": [record.model_dump(mode="json") for record in evidence],
        "entities": [entity.model_dump(mode="json") for entity in entities],
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _has_intact_source_artifacts(
    directory: Path, evidence: list[EvidenceRecord], entities: list[ExtractedEntity]
) -> bool:
    """Require every historical source entity to resolve to its recorded, hashed HTML artifact."""

    evidence_by_id = {record.id: record for record in evidence}
    required_ids = {entity.source_evidence_id for entity in entities}
    try:
        resolved_root = directory.resolve()
    except OSError:
        return False
    for evidence_id in required_ids:
        record = evidence_by_id.get(evidence_id)
        if record is None or record.type != "html_page":
            return False
        try:
            artifact = (directory / record.path).resolve()
        except OSError:
            return False
        if (
            artifact == resolved_root
            or resolved_root not in artifact.parents
            or not artifact.is_file()
        ):
            return False
        try:
            if _sha256_file(artifact) != record.sha256:
                return False
        except OSError:
            return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_one_case(
    directory: Path,
) -> tuple[CaseRecord, list[CrawlPageRecord], list[EvidenceRecord], list[ExtractedEntity]] | None:
    """Parse a single local case defensively; malformed/untrusted corpus entries are ignored."""

    try:
        case = CaseRecord.model_validate(_read_json(directory / "case.json"))
        pages = _models_from_json(directory / "pages.json", CrawlPageRecord)
        evidence = _models_from_json(directory / "evidence.json", EvidenceRecord)
        entities = _models_from_json(directory / "entities.json", ExtractedEntity)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return case, pages, evidence, entities


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _models_from_json[T](path: Path, model_type: type[T]) -> list[T]:
    """Validate a JSON array of Pydantic models without trusting arbitrary corpus files."""

    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list in {path}")
    return [model_type.model_validate(item) for item in payload]  # type: ignore[attr-defined]
