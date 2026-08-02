"""Append-only SQLite event, candidate-lead, assertion, and human-review index."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import CandidateAssertion, CandidateLead, EventKind, InvestigationEvent, ReviewEvent

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    sequence INTEGER NOT NULL,
    case_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    causation_event_id TEXT,
    correlation_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);
CREATE TABLE IF NOT EXISTS candidate_leads (
    lead_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    url TEXT NOT NULL,
    discovery_method TEXT NOT NULL,
    source_observation_ids_json TEXT NOT NULL,
    collection_mode TEXT NOT NULL,
    initial_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assertions (
    assertion_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    assertion_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    object TEXT NOT NULL,
    supporting_observation_ids_json TEXT NOT NULL,
    source_artifact_ids_json TEXT NOT NULL,
    initial_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    limitations_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    assertion_id TEXT NOT NULL REFERENCES assertions(assertion_id),
    outcome TEXT NOT NULL,
    reviewer_label TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    previous_version INTEGER NOT NULL,
    new_version INTEGER NOT NULL,
    UNIQUE(assertion_id, new_version)
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS assertions_no_update BEFORE UPDATE ON assertions BEGIN
    SELECT RAISE(ABORT, 'assertions are append-only');
END;
CREATE TRIGGER IF NOT EXISTS assertions_no_delete BEFORE DELETE ON assertions BEGIN
    SELECT RAISE(ABORT, 'assertions are append-only');
END;
CREATE TRIGGER IF NOT EXISTS reviews_no_update BEFORE UPDATE ON reviews BEGIN
    SELECT RAISE(ABORT, 'reviews are append-only');
END;
CREATE TRIGGER IF NOT EXISTS reviews_no_delete BEFORE DELETE ON reviews BEGIN
    SELECT RAISE(ABORT, 'reviews are append-only');
END;
CREATE TRIGGER IF NOT EXISTS leads_no_update BEFORE UPDATE ON candidate_leads BEGIN
    SELECT RAISE(ABORT, 'candidate leads are append-only');
END;
CREATE TRIGGER IF NOT EXISTS leads_no_delete BEFORE DELETE ON candidate_leads BEGIN
    SELECT RAISE(ABORT, 'candidate leads are append-only');
END;
"""


class InvestigationStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def append_event(
        self,
        *,
        case_id: str,
        run_id: str,
        kind: EventKind,
        payload: dict[str, object],
        causation_event_id: str | None = None,
        correlation_id: str | None = None,
        event_id: str | None = None,
    ) -> InvestigationEvent:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = self._append_event_connection(
                connection,
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                payload=payload,
                causation_event_id=causation_event_id,
                correlation_id=correlation_id or run_id,
                event_id=event_id,
            )
            connection.commit()
        return event

    def events(self, run_id: str) -> list[InvestigationEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY sequence", (run_id,)
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def add_lead(self, lead: CandidateLead, *, causation_event_id: str | None) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO candidate_leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lead.lead_id,
                    lead.case_id,
                    lead.run_id,
                    lead.url,
                    lead.discovery_method,
                    json.dumps(lead.source_observation_ids, sort_keys=True),
                    lead.collection_mode,
                    lead.initial_status,
                    lead.created_at.isoformat(),
                ),
            )
            self._append_event_connection(
                connection,
                case_id=lead.case_id,
                run_id=lead.run_id,
                kind="search.lead.discovered",
                payload=lead.model_dump(mode="json"),
                causation_event_id=causation_event_id,
                correlation_id=lead.run_id,
            )
            connection.commit()

    def add_assertion(
        self, assertion: CandidateAssertion, *, causation_event_id: str | None
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO assertions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assertion.assertion_id,
                    assertion.case_id,
                    assertion.run_id,
                    assertion.assertion_type,
                    assertion.subject,
                    assertion.object,
                    json.dumps(assertion.supporting_observation_ids, sort_keys=True),
                    json.dumps(assertion.source_artifact_ids, sort_keys=True),
                    assertion.initial_status,
                    assertion.created_at.isoformat(),
                    json.dumps(assertion.limitations, sort_keys=True),
                ),
            )
            proposed = self._append_event_connection(
                connection,
                case_id=assertion.case_id,
                run_id=assertion.run_id,
                kind="assertion.proposed",
                payload=assertion.model_dump(mode="json"),
                causation_event_id=causation_event_id,
                correlation_id=assertion.run_id,
            )
            self._append_event_connection(
                connection,
                case_id=assertion.case_id,
                run_id=assertion.run_id,
                kind="review.required",
                payload={"assertion_id": assertion.assertion_id},
                causation_event_id=proposed.event_id,
                correlation_id=assertion.run_id,
            )
            connection.commit()

    def assertion(self, assertion_id: str) -> CandidateAssertion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assertions WHERE assertion_id = ?", (assertion_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown assertion: {assertion_id}")
        return CandidateAssertion(
            assertion_id=row["assertion_id"],
            case_id=row["case_id"],
            run_id=row["run_id"],
            assertion_type=row["assertion_type"],
            subject=row["subject"],
            object=row["object"],
            supporting_observation_ids=json.loads(row["supporting_observation_ids_json"]),
            source_artifact_ids=json.loads(row["source_artifact_ids_json"]),
            initial_status=row["initial_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            limitations=json.loads(row["limitations_json"]),
        )

    def append_review(
        self,
        assertion_id: str,
        *,
        outcome: str,
        reviewer_label: str,
        reason: str,
    ) -> ReviewEvent:
        assertion = self.assertion(assertion_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(new_version), 0) AS version "
                "FROM reviews WHERE assertion_id = ?",
                (assertion_id,),
            ).fetchone()
            previous = int(row["version"])
            review = ReviewEvent(
                review_id=f"review-{uuid.uuid4().hex}",
                assertion_id=assertion_id,
                outcome=outcome,  # type: ignore[arg-type]
                reviewer_label=reviewer_label[:200],
                occurred_at=datetime.now(UTC),
                reason=reason[:2000],
                previous_version=previous,
                new_version=previous + 1,
            )
            connection.execute(
                "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    review.review_id,
                    review.assertion_id,
                    review.outcome,
                    review.reviewer_label,
                    review.occurred_at.isoformat(),
                    review.reason,
                    review.previous_version,
                    review.new_version,
                ),
            )
            kind_by_outcome: dict[str, EventKind] = {
                "verified": "assertion.verified",
                "rejected": "assertion.rejected",
                "needs_more_evidence": "assertion.needs_more_evidence",
                "duplicate": "assertion.duplicate",
                "uncertain": "assertion.uncertain",
            }
            self._append_event_connection(
                connection,
                case_id=assertion.case_id,
                run_id=assertion.run_id,
                kind=kind_by_outcome[review.outcome],
                payload=review.model_dump(mode="json"),
                correlation_id=assertion.run_id,
            )
            connection.commit()
        return review

    def review_history(self, assertion_id: str) -> list[ReviewEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reviews WHERE assertion_id = ? ORDER BY new_version",
                (assertion_id,),
            ).fetchall()
        return [ReviewEvent.model_validate(dict(row)) for row in rows]

    def current_assertion_status(self, assertion_id: str) -> str:
        history = self.review_history(assertion_id)
        return history[-1].outcome if history else self.assertion(assertion_id).initial_status

    def _append_event_connection(
        self,
        connection: sqlite3.Connection,
        *,
        case_id: str,
        run_id: str,
        kind: EventKind,
        payload: dict[str, object],
        causation_event_id: str | None = None,
        correlation_id: str,
        event_id: str | None = None,
    ) -> InvestigationEvent:
        chosen_id = event_id or f"event-{uuid.uuid4().hex}"
        existing = connection.execute(
            "SELECT * FROM events WHERE event_id = ?", (chosen_id,)
        ).fetchone()
        if existing is not None:
            existing_event = self._event_from_row(existing)
            if (
                existing_event.case_id == case_id
                and existing_event.run_id == run_id
                and existing_event.kind == kind
                and existing_event.payload == payload
            ):
                return existing_event
            raise ValueError("Event ID collision with different event content")
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        sequence = int(row["sequence"]) + 1
        event = InvestigationEvent(
            event_id=chosen_id,
            sequence=sequence,
            case_id=case_id,
            run_id=run_id,
            kind=kind,
            occurred_at=datetime.now(UTC),
            causation_event_id=causation_event_id,
            correlation_id=correlation_id,
            payload=payload,
        )
        connection.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.sequence,
                event.case_id,
                event.run_id,
                event.kind,
                event.occurred_at.isoformat(),
                event.causation_event_id,
                event.correlation_id,
                event.schema_version,
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        return event

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> InvestigationEvent:
        return InvestigationEvent(
            event_id=row["event_id"],
            sequence=row["sequence"],
            case_id=row["case_id"],
            run_id=row["run_id"],
            kind=row["kind"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            causation_event_id=row["causation_event_id"],
            correlation_id=row["correlation_id"],
            schema_version=row["schema_version"],
            payload=json.loads(row["payload_json"]),
        )
