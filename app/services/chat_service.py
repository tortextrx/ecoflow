import logging, json, os, time
from app.services.orchestrator import orchestrator

logger = logging.getLogger("ecoflow")
SESSIONS_FILE = "/tmp/ecoflow_sessions.json"
SESSION_TTL_SECONDS = 86400  # 24 horas

def _load_sessions():
    if not os.path.exists(SESSIONS_FILE): return {}
    try:
        with open(SESSIONS_FILE, "r") as f: return json.load(f)
    except: return {}

def _save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, "w") as f: json.dump(sessions, f)
    except: pass

def _get_session(sid):
    s = _load_sessions()
    now_ts = time.time()
    
    # TTL cleanup local
    expired = [k for k, v in s.items() if (now_ts - v.get("updated_at", now_ts)) > SESSION_TTL_SECONDS]
    for k in expired: 
        if k != sid: s.pop(k, None)

    # Iniciar o refrescar
    if sid not in s or (now_ts - s.get(sid, {}).get("updated_at", now_ts)) > SESSION_TTL_SECONDS:
        s[sid] = {
            "state": "idle", 
            "context": {}, 
            "last_pk": None, 
            "resolved_entities": {},
            "session_version": "1.1" # metadata
        }
    
    s[sid]["updated_at"] = now_ts
    _save_sessions(s)
    return s[sid]

def _commit_session(sid, session_data):
    s = _load_sessions()
    session_data["updated_at"] = time.time()
    s[sid] = session_data
    _save_sessions(s)

from app.connectors.base import ecoflow_trace_ctx

class ChatService:
    """Capa de Transporte: Gestor de Sesion (Fix Persistencia pop)."""

    async def handle(self, session_id: str, message: str, file_bytes=None, filename=None, trace_id=None):
        from app.models.schemas.chat import ChatResponse
        
        trace_id = trace_id or "local-" + str(int(time.time()))
        ecoflow_trace_ctx.set(trace_id)
        
        logger.info(f"[TRACE:{trace_id}] === NUEVA PETICIÓN ===")
        logger.info(f"[TRACE:{trace_id}] Entrada: session='{session_id}' mensaje='{message}'")
        
        # 1. Cargar Sesion
        session = _get_session(session_id)
        
        # 2. Delegar en Orquestador
        res = await orchestrator.dispatch(session, message, file_bytes, filename, trace_id=trace_id)
        
        # 3. Guardar SESION COMPLETA (Crucial para limpiar estados pendientes)
        _commit_session(session_id, session)
        
        logger.info(f"[TRACE:{trace_id}] Respuesta: {res.get('reply')[:50]}...")
        
        # 4. Responder
        return ChatResponse(
            reply=res.get("reply", "No he podido procesar tu solicitud."),
            state=res.get("state", "idle")
        )
