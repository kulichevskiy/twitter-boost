"""Worker loop: claims jobs, runs handlers with bounded concurrency, and
enqueues the scheduled sync when it is due. Run with `crm worker`."""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import timedelta

from ..config import settings as env
from ..db import session_scope
from ..models import Job, utcnow
from ..services.settings import load_effective
from ..services.sync import next_sync_at
from . import queue
from .handlers import HANDLERS, NON_RETRYABLE

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, concurrency: int | None = None, poll: float | None = None) -> None:
        self.concurrency = concurrency or env.worker_concurrency
        self.poll = poll or env.worker_poll_seconds
        self._stop = asyncio.Event()
        self._running: dict[int, asyncio.Task] = {}
        self._exclusive_running = False

    # ------------------------------------------------------------- lifecycle
    def request_stop(self) -> None:
        log.info("worker: stop requested")
        self._stop.set()

    async def run_forever(self) -> None:
        with session_scope() as session:
            n = queue.reset_running(session)
            if n:
                log.warning("worker: re-queued %d job(s) left running by a previous process", n)
        last_schedule_check = utcnow() - timedelta(minutes=5)
        while not self._stop.is_set():
            try:
                if utcnow() - last_schedule_check > timedelta(seconds=60):
                    self._maybe_schedule_sync()
                    last_schedule_check = utcnow()
                claimed = await self._claim_some()
                if not claimed:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=self.poll)
                    except TimeoutError:
                        pass
            except Exception:
                log.exception("worker loop error")
                await asyncio.sleep(self.poll)
        if self._running:
            log.info("worker: waiting for %d running job(s)", len(self._running))
            await asyncio.gather(*self._running.values(), return_exceptions=True)

    async def run_until_idle(self) -> int:
        """Drain the queue once (CLI / tests). Returns jobs processed."""
        done = 0
        while True:
            claimed = await self._claim_some()
            if not claimed and not self._running:
                return done
            if self._running:
                finished, _ = await asyncio.wait(self._running.values(), return_when=asyncio.FIRST_COMPLETED)
                done += len(finished)

    # ----------------------------------------------------------------- work
    def _maybe_schedule_sync(self) -> None:
        with session_scope() as session:
            eff = load_effective(session)
            due = next_sync_at(session, eff)
            if due is not None and due <= utcnow():
                job = queue.enqueue(session, "sync_full", {"trigger": "schedule"}, priority=5)
                log.info("worker: scheduled sync due, job %s", job.id)
            queue.release_stale(session)

    async def _claim_some(self) -> bool:
        claimed_any = False
        while len(self._running) < self.concurrency and not self._stop.is_set():
            with session_scope() as session:
                job = queue.claim(session, exclusive_running=self._exclusive_running)
                if job is None:
                    break
                if job.type in queue.EXCLUSIVE_TYPES and self._running:
                    # Someone else is running: put it back and wait for idle.
                    job.status = "queued"
                    job.locked_at = None
                    job.attempts -= 1
                    break
                job_id, job_type, payload = job.id, job.type, dict(job.payload or {})
            claimed_any = True
            if job_type in queue.EXCLUSIVE_TYPES:
                self._exclusive_running = True
            task = asyncio.create_task(self._run_job(job_id, job_type, payload), name=f"job-{job_id}")
            self._running[job_id] = task
            task.add_done_callback(lambda t, jid=job_id: self._running.pop(jid, None))
        return claimed_any

    async def _run_job(self, job_id: int, job_type: str, payload: dict) -> None:
        handler = HANDLERS.get(job_type)
        log.info("job %s %s start %s", job_id, job_type, payload)
        try:
            if handler is None:
                raise ValueError(f"no handler for job type {job_type}")
            with session_scope() as session:
                eff = load_effective(session)
            result = await handler(payload, eff)
            with session_scope() as session:
                job = session.get(Job, job_id)
                queue.finish(session, job, result)
            log.info("job %s %s done %s", job_id, job_type, result)
        except Exception as exc:
            retry = not isinstance(exc, NON_RETRYABLE)
            log.exception("job %s %s failed", job_id, job_type)
            with session_scope() as session:
                job = session.get(Job, job_id)
                queue.fail(session, job, f"{type(exc).__name__}: {exc}", retry=retry)
        finally:
            if job_type in queue.EXCLUSIVE_TYPES:
                self._exclusive_running = False


async def main() -> None:
    logging.basicConfig(level=env.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from ..migrate import upgrade_database

    upgrade_database()  # the worker may start before the API on a fresh machine
    worker = Worker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:  # pragma: no cover - windows
            pass
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
