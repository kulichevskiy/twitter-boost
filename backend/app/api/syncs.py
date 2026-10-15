from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs import queue
from ..models import Snapshot, Sync
from ..schemas import JobOut, SyncOut
from ..services.sync import decompress_ids
from .deps import DB
from .jobs import job_out

router = APIRouter(prefix="/syncs", tags=["syncs"])


def sync_out(s: Sync) -> SyncOut:
    return SyncOut.model_validate(s, from_attributes=True)


@router.get("", response_model=list[SyncOut])
def list_syncs(limit: int = 50, session: Session = DB):
    rows = session.execute(select(Sync).order_by(Sync.id.desc()).limit(min(limit, 500))).scalars()
    return [sync_out(s) for s in rows]


@router.post("/run", response_model=JobOut, status_code=202)
def run_sync(session: Session = DB):
    job = queue.enqueue(session, "sync_full", {"trigger": "manual"}, priority=10, max_attempts=1)
    session.commit()
    return job_out(job)


@router.get("/{sync_id}", response_model=SyncOut)
def get_sync(sync_id: int, session: Session = DB):
    s = session.get(Sync, sync_id)
    if s is None:
        raise HTTPException(404, "sync not found")
    return sync_out(s)


@router.get("/{sync_id}/snapshot/{direction}")
def get_snapshot(sync_id: int, direction: str, session: Session = DB) -> dict:
    snap = session.execute(
        select(Snapshot).where(Snapshot.sync_id == sync_id, Snapshot.direction == direction)
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(404, "snapshot not found")
    return {"sync_id": sync_id, "direction": direction, "count": snap.count, "ids": decompress_ids(snap.ids_blob)}
