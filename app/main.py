import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.db import AsyncSessionLocal, engine, Base
from app.core.job_queue import job_queue
from app.models.db.job import Job
from app.repositories import job_repo

import asyncio, logging
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.db.job import Job
from app.models.db.raw_message import RawMessage
from app.repositories import job_repo, raw_message_repo, event_repo
from app.services.identity_resolver import IdentityResolver
from app.services.orchestrator import Orchestrator
from app.providers.openai_responses import OpenAIResponsesProvider
from app.models.schemas.incoming import IncomingMessage

async def process_message(raw_message_id):
    log = logging.getLogger("ecoflow")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Job).where(Job.raw_message_id == raw_message_id))
            job = result.scalar_one_or_none()
            if not job: return
            if not await job_repo.lock_job(db, job.job_id): return
            await db.commit()
            res = await db.execute(select(RawMessage).where(RawMessage.id == raw_message_id))
            raw = res.scalar_one()
            msg = IncomingMessage(**raw.raw_payload)
            resolver = IdentityResolver()
            actor, conv = await resolver.resolve(db, raw.channel, raw.raw_actor_id)
            await event_repo.append(db, actor.actor_id, "message_received", {"text": msg.text}, conv.conversation_id)
            await db.commit()
            
            # [REFACTOR-PENDING] Flujo centralizado
            from app.services.chat_service import ChatService
            chat_svc = ChatService()
            res_dict = await chat_svc.handle(session_id=str(conv.conversation_id), message=msg.text)
            response_text = res_dict.reply
            
            await event_repo.append(db, actor.actor_id, "response_sent", {"text": response_text}, conv.conversation_id)
            await job_repo.complete_job(db, job.job_id)
            await raw_message_repo.set_status(db, raw_message_id, "done")
            await db.commit()
            log.info(f"job_completed raw={raw_message_id}")
        except Exception as e:
            log.exception(f"job_failed raw={raw_message_id}")
            async with AsyncSessionLocal() as db2:
                if 'job' in locals(): await job_repo.fail_job(db2, job.job_id, str(e))
                await raw_message_repo.set_status(db2, raw_message_id, "error")
                await db2.commit()

async def recover_pending_jobs():
    log = logging.getLogger("ecoflow")
    async with AsyncSessionLocal() as db:
        jobs = await job_repo.find_recoverable(
            db, max_attempts=settings.job_max_attempts, stale_minutes=settings.job_stale_minutes)
        for j in jobs:
            await job_queue.enqueue(j.raw_message_id)
        log.info(f"startup_recovery recovered={len(jobs)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_path=settings.log_path, debug=settings.debug)
    log = logging.getLogger("ecoflow")
    log.info(f"ecoflow_starting version={settings.app_version} port={settings.port}")
    async with engine.begin() as conn:
        from app.models.db import (RawMessage, Actor, Conversation, Operation,
                                    ConversationEvent, MediaAsset, MediaExtractionCache,
                                    IdempotencyRecord, Job)
        await conn.run_sync(Base.metadata.create_all)
    await job_queue.start(process_fn=process_message)
    await recover_pending_jobs()
    log.info("ecoflow_ready")
    yield
    await job_queue.stop()
    await engine.dispose()
    log.info("ecoflow_shutdown")

app = FastAPI(title="ecoFlow", version=settings.app_version, lifespan=lifespan)
from app.api.routes_internal import router
from app.api.routes_chat import router as chat_router
app.include_router(router)
app.include_router(chat_router)
app.mount("/ecoflow-chat", StaticFiles(directory="/home/ecoflow/app/static", html=True), name="chat")

@app.get("/")
async def root():
    return {"service": "ecoFlow", "version": settings.app_version}
