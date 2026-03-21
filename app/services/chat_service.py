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
            
            # Pasar al motor principal determinista (Lógica Pura)
            res = await orchestrator.dispatch(session, message, file_bytes, filename, trace_id=trace_id)
            
            # Pasar la respuesta del sistema por la Humanization Layer (Presentación Pura)
            from app.services.response_service import response_service
            
            # Ignoramos la re-escritura si devolvió un error interno obvio que deba mostrarse o si
            # la petición era vacía (apertura de conexión), pero forzamos por lo general:
            tech_reply = res.get("reply", "")
            raw_state = res.get("state", "idle")
            
            # Solo aplicamos el coste de naturalización si hay respuesta de texto a mostrar y no es vacío,
            # y no es una subida de ficheros (multimodal a futuro donde mensaje=None).
            if message:
                human_reply = await response_service.humanize(message, tech_reply, raw_state)
            else:
                human_reply = tech_reply

            # Guardamos el último bot message humanizado en sesión (útil para historial y debug)
            session["_last_bot_reply"] = human_reply
            
            # Update DB and commit
            await conversation_repo.update_session_data(db, conv.conversation_id, session)
            await db.commit()
            
            logger.info(f"[TRACE:{trace_id}] Respuesta Técnica (Orquestador): {tech_reply[:60]}...")
            logger.info(f"[TRACE:{trace_id}] Respuesta Humana  (Res. Layer): {human_reply[:60]}...")
            
            return ChatResponse(
                reply=human_reply or "No he podido procesar tu solicitud.",
                state=raw_state
            )
