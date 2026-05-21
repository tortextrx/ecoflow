import asyncio, logging
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.db.job import Job
from app.models.db.raw_message import RawMessage
from app.repositories import job_repo, raw_message_repo, event_repo
from app.services.identity_resolver import IdentityResolver
from app.services.orchestrator import Orchestrator
from app.services.intent_service import IntentService
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
            
            # Guardamos el mensaje de entrada
            await event_repo.append(db, actor.actor_id, "message_received", {"text": msg.text}, conv.conversation_id)
            await db.commit()
            
            provider = OpenAIResponsesProvider()
            intent_service = IntentService(llm=provider)
            orch = Orchestrator(intent_service=intent_service)
            
            # Si orch.run lanza una excepción (ej. ConnectTimeout), saltamos al except
            response_text = await orch.run(db, actor, conv, msg)
            
            # Si llegamos aquí, se considera ÉXITO lógico o de negocio
            await event_repo.append(db, actor.actor_id, "response_sent", {"text": response_text}, conv.conversation_id)
            await job_repo.complete_job(db, job.job_id)
            await raw_message_repo.set_status(db, raw_message_id, "done")
            await db.commit()
            log.info(f"job_completed raw={raw_message_id}")

        except Exception as e:
            # ERROR DE INFRAESTRUCTURA O CRÍTICO
            log.error(f"job_failed_infra_error raw={raw_message_id} error={str(e)}")
            # No marcamos como DONE. El Job quedará como FAILED en DB para auditoría.
            async with AsyncSessionLocal() as db2:
                # Buscamos el job de nuevo en la nueva sesión
                res_job = await db2.execute(select(Job).where(Job.raw_message_id == raw_message_id))
                db_job = res_job.scalar_one_or_none()
                if db_job:
                    await job_repo.fail_job(db2, db_job.job_id, str(e))
                await raw_message_repo.set_status(db2, raw_message_id, "error")
                await db2.commit()
