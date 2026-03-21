import logging, json, unicodedata, re
from datetime import datetime
from app.services.cognitive_service import cognitive_service
from app.services.resolver import resolver
from app.services.tools.registry import tool_registry
from app.services.orchestrator_routing import detect_active_flow, detect_proactive_history_intent, detect_new_flow
from app.services.conversational_logic import IntentAction, StateMachine

logger = logging.getLogger("ecoflow")

def clean_text(text: str) -> str:
    if not text: return ""
    text = text.lower().strip()
    normalized = unicodedata.normalize('NFD', text)
    return "".join(c for c in normalized if unicodedata.category(c) != 'Mn')

def get_now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

class UnifiedOrchestrator:
    """Orquestador Conversacional Unificado (Domain-Driven).
    Centraliza la lógica de intención/acción y la máquina de estados.
    """
    
    async def dispatch(self, session: dict, message: str, file_bytes=None, filename=None, trace_id=None) -> dict:
        if file_bytes and filename:
            return await self._handle_multimodal(session, file_bytes, filename)

        st = session.get("state", StateMachine.IDLE)
        msg_c = clean_text(message)
        analysis = await cognitive_service.parse_intent(message, f"Estado: {st}")
        intent_name = str(analysis.get("intent", ""))
        entities = analysis.get("entities", {})

        logger.info(f"[TRACE:{trace_id}] Despachando a {st} con intencion {intent_name}")

        # 1. PRIORIDAD: FLUJOS EN CURSO (Máquina de Estados)
        if st == "AWAITING_DISAMBIGUATION":
            return await self._handle_disambiguation(session, message)
        
        # 2. DETECCION DE HISTORIAL PROACTIVO (Páginas ERP Críticas)
        hist = detect_proactive_history_intent(message, msg_c, intent_name, entities)
        if hist:
            if hist["action"] == "add_history":
                return await self._handle_add_history(session, hist["pkey"], hist["nota"])
            return await self._handle_query_history(session, hist["pkey"])

        # 3. LANZAMIENTO O CONTINUIDAD DE FLUJO UNIFICADO
        # Si hay flujo activo o el usuario quiere iniciar uno nuevo
        active_flow_key = detect_active_flow(st, session)
        new_flow_key = detect_new_flow(intent_name, msg_c)
        
        if active_flow_key or new_flow_key:
            flow_to_use = active_flow_key or new_flow_key
            if flow_to_use == "entity": return await self._flow_entity(session, message, analysis)
            if flow_to_use == "service": return await self._flow_service(session, message, analysis)
            if flow_to_use == "expense": return await self._flow_expense(session, message, analysis)

        # 4. CONSULTA DE CAMPOS (Capa de Consulta)
        if intent_name == "consultar_campo":
            return await self._handle_query_field(session, entities)

        return await self._process_general(session, analysis, message)

    # --- FLUJO: ENTIDADES (ALTA CLIENTE/ACREEDOR) ---
    async def _flow_entity(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {"type": "ENTIDADES"}; session["flow_mode"] = "entity"
        d = session["flow_data"]
        new_entities = analysis.get("entities", {})
        
        # Inyectar datos nuevos
        if new_entities.get("nombre_cliente"): d["name"] = new_entities["nombre_cliente"]
        if new_entities.get("cif"): d["cif"] = new_entities["cif"]
        
        # Contrato de Intencion
        action = IntentAction(
            intent="CREATE",
            module="ENTIDADES",
            operation="crear_entidad",
            entities={},
            fields={"DENCOM": d.get("name"), "CIF": d.get("cif")},
            risk_level="LOW"
        )
        
        # Validar Complitud
        if not d.get("name"):
            session["state"] = "AWAITING_ENTITY_CONFIRM" # Reusamos este para recolección
            return {"reply": "¿A qué nombre damos el alta?", "state": session["state"]}
        if not d.get("cif"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": f"¿Y el CIF de **{d['name']}**?", "state": session["state"]}

        # Estado: CONFIRMING
        if analysis.get("intent") == "confirm" or clean_text(message) in ["si", "ok", "graba", "guardar"]:
            p = {"DENCOM": d["name"], "CIF": d["cif"], "SUCURSAL": 1, "CLIENTE": 1, "ESTADO": 0}
            r = await tool_registry.crear_entidad.execute(p)
            if r.get("success"):
                session["last_resolved_entity"] = {"pkey": r.get("pkey"), "nombre": d["name"]}
                return self._clear_flow(session, f"✅ Alta Realizada con éxito (ID {r.get('pkey')})")
            return {"reply": f"❌ Error ERP: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_ENTITY_CONFIRM"
        return {"reply": f"📋 **Confirmación de Alta**\n- Cliente: **{d['name']}**\n- CIF: {d['cif']}\n\n¿Es correcto? (si/no)", "state": "AWAITING_ENTITY_CONFIRM"}

    # --- FLUJO: SERVICIOS ---
    async def _flow_service(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {"type": "SERVICIOS"}; session["flow_mode"] = "service"
        d = session["flow_data"]
        new_e = analysis.get("entities", {})

        # 1. Resolución de Cliente (Entidad Primaria)
        # Si el usuario menciona un nombre ahora o ya lo tenemos de antes
        target_name = new_e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"] = res["data"]["pkey"]
                d["client_name"] = res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] == "AMBIGUOUS":
                session["state"] = "AWAITING_DISAMBIGUATION"
                session["ambiguous_options"] = res.get("options", [])
                opts_text = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"He encontrado varias coincidencias para el cliente. Elige una:\n{opts_text}", "state": "AWAITING_DISAMBIGUATION"}
        
        # Fallback a última entidad usada si no hay nombre en el mensaje actual
        if not d.get("client_pk") and session.get("last_resolved_entity"):
            ent = session["last_resolved_entity"]
            d["client_pk"], d["client_name"] = ent["pkey"], ent["nombre"]

        # 2. Recolección de Campos Faltantes
        if not d.get("client_pk"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": "¿Para qué cliente es el servicio?", "state": "AWAITING_SERVICE_CONFIRM"}
            
        if new_e.get("descripcion"): d["task"] = new_e["descripcion"]
        if not d.get("task"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": f"¿Qué trabajo hay que hacer para **{d['client_name']}**?", "state": "AWAITING_SERVICE_CONFIRM"}

        # Validación de calidad
        if len(clean_text(d["task"])) < 8:
            d.pop("task", None)
            return {"reply": "La descripción es muy corta. Por favor, dime qué hay que hacer con un poco más de detalle.", "state": "AWAITING_SERVICE_CONFIRM"}

        # 3. Confirmación (Máquina de Estados)
        if analysis.get("intent") == "confirm" or clean_text(message) in ["si", "adelante", "ok", "graba"]:
            payload = {"MODO_ID": 0, "CLIENTE": d["client_pk"], "CLIENTE_DELEGACION": 1, "ESTADO": 0, "SUCURSAL": "1", "NIVELCONTROL": 1, "SERVICIO_DESCRIPCION": d["task"], "FECHA_INICIO": get_now_iso()}
            r = await tool_registry.crear_servicio.execute(payload)
            if r.get("success"):
                return self._clear_flow(session, f"✅ Servicio {r['pkey']} creado para {d['client_name']}.")
            return {"reply": "❌ Error al grabar el servicio.", "state": "idle"}

        session["state"] = "AWAITING_SERVICE_CONFIRM"
        resumen = d['task'][:60] + "..." if len(d['task']) > 60 else d['task']
        return {"reply": f"📋 **Nuevo Servicio**\n- **Cliente**: {d['client_name']}\n- **Tarea**: {resumen}\n\n¿Procedo con el registro?", "state": "AWAITING_SERVICE_CONFIRM"}

    # --- CAPA DE CONSULTA DE CAMPOS ---
    async def _handle_query_field(self, session: dict, entities: dict) -> dict:
        campo = entities.get("campo")
        target_name = entities.get("nombre_cliente")
        last = session.get("last_resolved_entity")
        
        entidad = None
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED": entidad = res["data"]
            elif res["status"] == "AMBIGUOUS":
                session["state"] = "AWAITING_DISAMBIGUATION"
                session["ambiguous_options"] = res.get("options", [])
                session["pending_action"] = {"intent": "consultar_campo", "campo": campo}
                opts_text = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varios. ¿Cuál buscas?\n{opts_text}", "state": "AWAITING_DISAMBIGUATION"}
        elif last:
            entidad = last
        
        if not entidad:
            return {"reply": f"¿De qué cliente quieres ver el/la {campo or 'ficha'}?", "state": "idle"}
        
        if not campo:
            return {"reply": f"He localizado a **{entidad['nombre']}** (CIF: {entidad['cif']}). ¿Quieres su teléfono, email o dirección?", "state": "idle"}
            
        valor = await resolver.obtener_campo(entidad["pkey"], campo)
        session["last_resolved_entity"] = entidad
        return {"reply": f"El/La {campo} de {entidad['nombre']} es: {valor}", "state": "idle"}

    # --- HELPERS GENERALES ---
    async def _handle_disambiguation(self, session: dict, message: str) -> dict:
        options = session.get("ambiguous_options", [])
        sel = resolver.parse_selection(message, len(options))
        if sel is None:
            return {"reply": f"Elige un número del 1 al {len(options)}.", "state": "AWAITING_DISAMBIGUATION"}
        
        chosen = options[sel - 1]
        session["last_resolved_entity"] = chosen
        session.pop("ambiguous_options", None)
        
        # Recuperar acción pendiente (ej: consulta de campo)
        pa = session.pop("pending_action", None)
        if pa and pa["intent"] == "consultar_campo":
            v = await resolver.obtener_campo(chosen["pkey"], pa["campo"])
            session["state"] = "idle"
            return {"reply": f"El/La {pa['campo']} de {chosen['nombre']} es: {v}", "state": "idle"}
        
        # Si estábamos en un flujo de servicio
        if session.get("flow_mode") == "service":
            session["flow_data"]["client_pk"] = chosen["pkey"]
            session["flow_data"]["client_name"] = chosen["nombre"]
            return await self._flow_service(session, "ok", {"intent": "confirm"}) # Forzamos re-entrada

        session["state"] = "idle"
        return {"reply": f"Entendido, trabajamos con **{chosen['nombre']}**. ¿Qué necesitas?", "state": "idle"}

    async def _process_general(self, session: dict, analysis: dict, message: str) -> dict:
        target_name = analysis.get("entities", {}).get("nombre_cliente")
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                session["last_resolved_entity"] = res["data"]
                return {"reply": f"Veo que mencionas a **{res['data']['nombre']}**. ¿Qué quieres hacer con este cliente?", "state": "idle"}
        return {"reply": "No estoy seguro de qué necesitas. Puedes pedirme crear un servicio, dar de alta un cliente o consultar datos.", "state": "idle"}

    def _clear_flow(self, session: dict, reply: str) -> dict:
        for k in ["flow_mode", "flow_data", "state", "pending_action", "ambiguous_options"]: session.pop(k, None)
        return {"reply": reply, "state": "idle"}

    # [STUB] Para no romper compatibilidad temporal
    async def _handle_multimodal(self, session, fb, fn): return {"reply": "Procesando documento...", "state": "idle"}
    async def _handle_add_history(self, s, p, n): return {"reply": "Nota guardada.", "state":"idle"}
    async def _handle_query_history(self, s, p): return {"reply": "Historial leído.", "state":"idle"}

orchestrator = UnifiedOrchestrator()
