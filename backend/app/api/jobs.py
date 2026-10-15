from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs import queue
from ..models import Job, utcnow
from ..schemas import JobOut
from .deps import DB

router = APIRouter(prefix="/jobs", tags=["jobs"])


def job_out(j: Job) -> JobOut:
    return JobOut(
        id=j.id,
        type=j.type,
        payload=j.payload or {},
        status=j.status,
        priority=j.priority,
        attempts=j.attempts,
        max_attempts=j.max_attempts,
        run_after=j.run_after,
        started_at=j.started_at,
        finished_at=j.finished_at,
        result=j.result,
        error=j.error,
        created_at=j.created_at,
    )


@router.get("", response_model=list[JobOut])
def list_jobs(status: str | None = None, type: str | None = None, limit: int = 100, session: Session = DB):
    stmt = select(Job).order_by(Job.id.desc()).limit(min(limit, 500))
    if status:
        stmt = stmt.where(Job.status.in_(status.split(",")))
    if type:
        stmt = stmt.where(Job.type == type)
    return [job_out(j) for j in session.execute(stmt).scalars()]


@router.get("/counts")
def job_counts(session: Session = DB) -> dict[str, int]:
    return queue.counts(session)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: Session = DB):
    j = session.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    return job_out(j)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: int, session: Session = DB):
    j = session.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status not in ("failed", "cancelled", "done"):
        raise HTTPException(409, f"job is {j.status}")
    j.status = "queued"
    j.attempts = 0
    j.error = None
    j.result = None
    j.run_after = utcnow()
    j.finished_at = None
    session.commit()
    return job_out(j)


@router.delete("/{job_id}", response_model=JobOut)
def cancel_job(job_id: int, session: Session = DB):
    j = session.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status == "queued":
        j.status = "cancelled"
        j.finished_at = utcnow()
        session.commit()
    return job_out(j)
