import re
from typing import Optional, Dict, Any

def detect_active_flow(state: str, session: dict) -> Optional[str]:
    """Detecta si hay un flujo activo en la sesión y devuelve su identificador."""
    if state == "AWAITING_DISAMBIGUATION": return "disambiguation"
    if state in ("AWAITING_ENTITY_CONFIRM",) or session.get("flow_mode") == "entity": return "entity"
    if state in ("AWAITING_SERVICE_CONFIRM",) or session.get("flow_mode") == "service": return "service"
    if state in ("AWAITING_EXPENSE_CONFIRM",) or session.get("flow_mode") == "expense": return "expense"
    if state in ("AWAITING_CONTRATO_COLLECT",) or session.get("flow_mode") == "contract": return "contract"
    if state in ("AWAITING_FACTURA_COLLECT",) or session.get("flow_mode") == "factura": return "factura"
    if state in ("AWAITING_ARTICULO_COLLECT",) or session.get("flow_mode") == "article": return "article"
    return None

def detect_proactive_history_intent(message: str, msg_c: str, intent: str, entities: dict) -> Optional[Dict[str, Any]]:
    """Detecta si la intención es operar sobre el historial de manera proactiva aportando un PKEY."""
    # Nunca pisar una creación de servicio con routing de histórico.
    if intent == "open_task" or any(k in msg_c for k in ["abre un servicio", "crear servicio", "crea un servicio", "nuevo servicio"]):
        return None

    found_pkey = None
    if not re.search(r'[a-zA-Z]', message) and len(message.strip()) <= 7:
        pkey_m = re.search(r'\b(\d{5})\b', message)
        if pkey_m: found_pkey = int(pkey_m.group(1))
    
    if not found_pkey:
        found_pkey = entities.get("pkey_servicio")

    if not found_pkey:
        m_any = re.search(r"\b(?:servicio\s*)?(\d{3,8})\b", msg_c)
        if m_any:
            try:
                found_pkey = int(m_any.group(1))
            except Exception:
                found_pkey = None

    if found_pkey:
        is_history_intent = intent in ["query_history", "add_history"]
        is_history_keyword = any(k in msg_c for k in ["historia", "actuacio", "nota", "ver", "dime"])
        if is_history_intent or is_history_keyword:
            if any(k in msg_c for k in ["meter", "pon", "graba", "linea", "anade", "añade", "añadir", "agrega", "inserta"]) or intent == "add_history":
                return {"action": "add_history", "pkey": found_pkey, "nota": entities.get("descripcion") or message}
            return {"action": "query_history", "pkey": found_pkey}
    return None

def detect_new_flow(intent: str, msg_c: str) -> Optional[str]:
    """Detecta si el usuario desea iniciar un flujo completamente nuevo."""
    # Priorización explícita de dominios para evitar cruces semánticos.
    if intent == "create_article" or any(k in msg_c for k in ["articulo", "artículo", "producto", "referencia"]):
        return "article"
    if intent == "open_task" or any(k in msg_c for k in ["servicio", "tarea", "parte de trabajo", "parte"]):
        return "service"
    if intent == "create_contract" or "contrato" in msg_c:
        return "contract"
    if intent.startswith("create_") and "factura" in intent:
        return "factura"
    if any(k in msg_c for k in ["factura", "albaran", "albarán", "pedido", "presupuesto", "prefactura", "gasto"]):
        return "factura"
    if intent == "create_entity" or any(k in msg_c for k in ["cliente", "proveedor", "entidad", "cif", "nif"]):
        return "entity"
    return None
