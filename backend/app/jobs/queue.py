"""SQLite-backed job queue. One worker process claims with an atomic UPDATE."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ..models import Job, utcnow

EXCLUSIVE_TYPES = {"sync_full"}  # never run concurrently with anything else


def dedupe_key(job_type: str, payload: dict[str, Any]) -> str:
    if job_type in EXCLUSIVE_TYPES:  # one pending sync at a time, whoever asked
        return job_type
    stable = json.dumps(payload, sort_keys=True, default=str)
    return f"{job_type}:{stable}"[:128]


def enqueue(
    session: Session,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    priority: int = 0,
    run_after: datetime | None = None,
    max_attempts: int = 3,
) -> Job:
    payload = payload or {}
    key = dedupe_key(job_type, payload)
    existing = session.execute(
        select(Job).where(Job.dedupe_key == key, Job.status.in_(("queued", "running"))).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    job = Job(
        type=job_type,
        payload=payload,
        dedupe_key=key,
        priority=priority,
        run_after=run_after or utcnow(),
        max_attempts=max_attempts,
    )
    session.add(job)
    session.flush()
    return job


def claim(session: Session, exclusive_running: bool) -> Job | None:
    """Atomically take the next runnable job. When an exclusive job is running,
    nothing else is claimed; an exclusive job is only claimed when idle."""
    if exclusive_running:
        return None
    running = session.execute(select(func.count(Job.id)).where(Job.status == "running")).scalar_one()
    now = utcnow()
    type_filter = "" if running == 0 else " AND type NOT IN (:excl)"
    params: dict[str, Any] = {"now": now}
    if running:
        params["excl"] = ",".join(EXCLUSIVE_TYPES)
    row = session.execute(
        text(
            "UPDATE jobs SET status='running', locked_at=:now, started_at=:now, attempts=attempts+1 "
            "WHERE id = (SELECT id FROM jobs WHERE status='queued' AND run_after <= :now"
            + type_filter
            + " ORDER BY priority DESC, id ASC LIMIT 1) RETURNING id"
        ),
        params,
    ).first()
    session.commit()
    if row is None:
        return None
    return session.get(Job, row[0])


def finish(session: Session, job: Job, result: dict[str, Any] | None = None) -> None:
    job.status = "done"
    job.result = result
    job.finished_at = utcnow()
    job.error = None


def fail(session: Session, job: Job, error: str, *, retry: bool = True) -> None:
    job.error = error[:4000]
    job.finished_at = utcnow()
    if retry and job.attempts < job.max_attempts:
        job.status = "queued"
        job.run_after = utcnow() + timedelta(seconds=30 * (2 ** (job.attempts - 1)))
        job.locked_at = None
    else:
        job.status = "failed"


def release_stale(session: Session, older_than_minutes: int = 45) -> int:
    cutoff = utcnow() - timedelta(minutes=older_than_minutes)
    res = session.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < cutoff)
        .values(status="queued", locked_at=None, error="released: worker died or timed out")
    )
    return res.rowcount or 0


def reset_running(session: Session) -> int:
    """On worker start: whatever was 'running' belongs to a dead process."""
    res = session.execute(update(Job).where(Job.status == "running").values(status="queued", locked_at=None))
    return res.rowcount or 0


def counts(session: Session) -> dict[str, int]:
    rows = session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    out = {"queued": 0, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
    for status, n in rows:
        out[status] = n
    return out
