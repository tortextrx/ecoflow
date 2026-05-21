import uuid, logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.config import settings
from app.core.job_queue import job_queue
from app.models.schemas.incoming import SimulateRequest
from app.models.db.raw_message import RawMessage
from app.models.db.idempotency import IdempotencyRecord
from app.repositories import job_repo

logger = logging.getLogger("ecoflow")
router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name,
            "version": settings.app_version, "ts": datetime.utcnow().isoformat() + "Z"}

@router.post("/simulate")
async def simulate(req: SimulateRequest, db: AsyncSession = Depends(get_db)):
    external_id = f"simulate:{req.user_id}:{uuid.uuid4()}"
    existing = (await db.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.key == external_id)
    )).scalar_one_or_none()
    if existing:
        return {"status": "duplicate"}
    
    # Generate ID explicitly so we have it before flush
    raw_id = uuid.uuid4()
    raw = RawMessage(id=raw_id, external_message_id=external_id, channel=req.channel,
                     raw_actor_id=req.user_id, raw_payload=req.model_dump())
    db.add(raw)
    idem = IdempotencyRecord(key=external_id, key_type="message", status="seen")
    db.add(idem)
    
    # Needs await db.flush() before using foreign key, or just pass the explicit raw_id
    await db.flush()
    job = await job_repo.create_job(db, raw.id)
    await db.commit()
    await job_queue.enqueue(raw.id)
    logger.info(f"simulate_accepted raw={raw.id} job={job.job_id}")
    return {"status": "accepted", "raw_message_id": str(raw.id), "job_id": str(job.job_id)}
