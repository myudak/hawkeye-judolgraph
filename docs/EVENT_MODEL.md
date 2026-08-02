# Investigation Event Model

SQLite `events` is the append-only source of truth. Every envelope includes event ID, run-monotonic
sequence, case and run IDs, kind, UTC occurrence time, optional causation event, correlation ID,
schema version, and JSON payload. A repeated event ID with identical content is idempotent; a
collision with different content fails. Database triggers reject event updates and deletes.

Implemented kinds cover run and collection lifecycle, artifacts, interactive elements, evidence
gaps, agent objectives/fallback, requested/blocked/completed tools, observations and entities,
search leads, candidate selection/approval/collection failure or success, assertion proposals,
review requirements/outcomes, and run completion/failure.

Candidate leads, assertions, and reviews are also immutable SQLite rows. A real-world lead begins
waiting for approval; synthetic fixtures may begin approved. An assertion starts `needs_review`.
Review rows carry reviewer label, reason, timestamp, and previous/new version. Current status is
derived from the latest review; `verified` supports only the stated evidence relationship.

