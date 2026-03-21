import logging, json, os
from app.services.orchestrator import orchestrator

logger = logging.getLogger("ecoflow")
SESSIONS_FILE = "/tmp/ecoflow_sessions.json"

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
    # Si la sesion no existe, la inicializamos
    if sid not in s: 
        s[sid] = {"state": "idle", "context": {}, "last_pk": None, "resolved_entities": {}}
        _save_sessions(s)
    return s[sid]

def _commit_session(sid, session_data):
    """Guarda el objeto sesion completo, permitiendo la ELIMINACION de claves (pop)."""
    s = _load_sessions()
    s[sid] = session_data
    _save_sessions(s)

class ChatService:
    """Capa de Transporte: Gestor de Sesion (Fix Persistencia pop)."""

    async def handle(self, session_id: str, message: str, file_bytes=None, filename=None):
        from app.models.schemas.chat import ChatResponse
        
        # 1. Cargar Sesion
        session = _get_session(session_id)
        
        # 2. Delegar en Orquestador
        res = await orchestrator.dispatch(session, message, file_bytes, filename)
        
        # 3. Guardar SESION COMPLETA (Crucial para limpiar estados pendientes)
        _commit_session(session_id, session)
        
        # 4. Responder
        return ChatResponse(
            reply=res.get("reply", "No he podido procesar tu solicitud."),
            state=res.get("state", "idle")
        )
