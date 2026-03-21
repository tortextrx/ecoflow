import logging, time
from app.services.orchestrator import orchestrator
from app.connectors.base import ecoflow_trace_ctx
from app.core.db import AsyncSessionLocal
from app.services.identity_resolver import IdentityResolver
from app.repositories import conversation_repo

logger = logging.getLogger("ecoflow")

class ChatService:
    """Capa de Transporte: Gestor de Sesion Persistente en DB."""

    async def handle(self, session_id: str, message: str, file_bytes=None, filename=None, trace_id=None):
        from app.models.schemas.chat import ChatResponse
        
        trace_id = trace_id or "local-" + str(int(time.time()))
        ecoflow_trace_ctx.set(trace_id)
        
        logger.info(f"[TRACE:{trace_id}] === NUEVA PETICIÓN ===")
        logger.info(f"[TRACE:{trace_id}] Entrada: session='{session_id}' mensaje='{message}'")
        
        async with AsyncSessionLocal() as db:
            resolver = IdentityResolver()
            # El ID se hereda de session_id del frontend
            actor, conv = await resolver.resolve(db, channel="webchat", user_id=session_id)
            
            session = conv.session_data or {}
            
            if "state" not in session:
                session.update({
                    "state": "idle",
                    "context": {},
                    "session_version": "2.0-postgres"
                })
            
            # Pasar al motor principal
            res = await orchestrator.dispatch(session, message, file_bytes, filename, trace_id=trace_id)
            
            # Update DB and commit
            await conversation_repo.update_session_data(db, conv.conversation_id, session)
            await db.commit()
            
            logger.info(f"[TRACE:{trace_id}] Respuesta: {res.get('reply')[:50]}...")
            
            return ChatResponse(
                reply=res.get("reply", "No he podido procesar tu solicitud."),
                state=res.get("state", "idle")
            )
