import re
from typing import Optional, Dict, Any

def detect_active_flow(state: str, session: dict) -> Optional[str]:
    """Detecta si hay un flujo activo en la sesión y devuelve su identificador."""
    if state == "AWAITING_DISAMBIGUATION": return "disambiguation"
    if state == "AWAITING_ENTITY_CONFIRM" or session.get("flow_mode") == "entity": return "entity"
    if state == "AWAITING_SERVICE_CONFIRM" or session.get("flow_mode") == "service": return "service"
    if state == "AWAITING_EXPENSE_CONFIRM" or session.get("flow_mode") == "expense": return "expense"
    return None

def detect_proactive_history_intent(message: str, msg_c: str, intent: str, entities: dict) -> Optional[Dict[str, Any]]:
    """Detecta si la intención es operar sobre el historial de manera proactiva aportando un PKEY."""
    found_pkey = None
    if not re.search(r'[a-zA-Z]', message) and len(message.strip()) <= 7:
        pkey_m = re.search(r'\b(\d{5})\b', message)
        if pkey_m: found_pkey = int(pkey_m.group(1))
    
    if not found_pkey: 
        found_pkey = entities.get("pkey_servicio")

    if found_pkey:
        is_history_intent = intent in ["query_history", "add_history"]
        is_history_keyword = any(k in msg_c for k in ["historia", "actuacio", "nota", "ver", "dime"])
        if is_history_intent or is_history_keyword:
            if any(k in msg_c for k in ["meter", "pon", "graba", "linea"]) or intent == "add_history":
                return {"action": "add_history", "pkey": found_pkey, "nota": entities.get("descripcion") or message}
            return {"action": "query_history", "pkey": found_pkey}
    return None

def detect_new_flow(intent: str, msg_c: str) -> Optional[str]:
    """Detecta si el usuario desea iniciar un flujo completamente nuevo."""
    if intent == "create_entity" or "alta" in msg_c:
        return "entity"
    if intent == "open_task" or any(k in msg_c for k in ["servicio", "tarea"]):
        return "service"
    return None
