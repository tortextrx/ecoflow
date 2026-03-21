import os, socket
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.job import Job

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"

async def create_job(db: AsyncSession, raw_message_id: UUID) -> Job:
    job = Job(raw_message_id=raw_message_id)
    db.add(job)
    await db.flush()
    return job

async def find_recoverable(db: AsyncSession, max_attempts: int = 3, stale_minutes: int = 5) -> list[Job]:
    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
    result = await db.execute(
        select(Job).where(
            ((Job.status == "pending") | ((Job.status == "running") & (Job.locked_at < cutoff)))
            & (Job.attempts < max_attempts)
        )
    )
    return list(result.scalars().all())

async def lock_job(db: AsyncSession, job_id: UUID) -> bool:
    r = await db.execute(
        update(Job).where(Job.job_id == job_id, Job.status.in_(["pending", "running"]))
        .values(status="running", locked_at=datetime.utcnow(), locked_by=WORKER_ID,
                attempts=Job.attempts + 1, updated_at=datetime.utcnow())
    )
    return r.rowcount > 0

async def complete_job(db: AsyncSession, job_id: UUID):
    await db.execute(update(Job).where(Job.job_id == job_id)
                     .values(status="done", updated_at=datetime.utcnow()))

async def fail_job(db: AsyncSession, job_id: UUID, error: str):
    await db.execute(update(Job).where(Job.job_id == job_id)
                     .values(status="failed", last_error=error[:2048], updated_at=datetime.utcnow()))

async def skip_job(db: AsyncSession, job_id: UUID):
    await db.execute(update(Job).where(Job.job_id == job_id)
                     .values(status="skipped", updated_at=datetime.utcnow()))
