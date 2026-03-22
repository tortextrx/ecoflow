import logging, json, unicodedata, re
from datetime import datetime
from app.services.cognitive_service import cognitive_service
from app.services.resolver import resolver
from app.services.tools.registry import tool_registry
from app.services.orchestrator_routing import detect_active_flow, detect_proactive_history_intent, detect_new_flow
from app.services.conversational_logic import IntentAction, StateMachine

logger = logging.getLogger("ecoflow")

# ─── NIVELCONTROL prohibidos para borrado (API restriction) ───
NC_NO_BORRABLE = {13, 20}  # Facturas de venta y simplificadas

# ─── Mapa de NIVELCONTROL para facturación ───
NC_MAP = {
    "create_presupuesto_compra": 1,
    "create_pedido_compra": 2,
    "create_albaran_compra": 4,
    "create_factura_compra": 5,
    "create_gasto": 6,
    "create_presupuesto_venta": 10,
    "create_pedido_venta": 11,
    "create_albaran_venta": 12,
    "create_prefactura": 17,
}
NC_LABELS = {
    1: "Presupuesto de Compra", 2: "Pedido de Compra", 4: "Albarán de Compra",
    5: "Factura de Compra", 6: "Factura de Gasto", 10: "Presupuesto de Venta",
    11: "Pedido de Venta", 12: "Albarán de Venta", 17: "Prefactura de Venta",
}

def clean_text(text: str) -> str:
    if not text: return ""
    text = text.lower().strip()
    normalized = unicodedata.normalize('NFD', text)
    return "".join(c for c in normalized if unicodedata.category(c) != 'Mn')

def get_now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

CONFIRM_WORDS = {"si", "sí", "ok", "dale", "graba", "guardar", "adelante", "venga", "tira", "hazlo"}
STRONG_CONFIRM_WORDS = {"confirmo", "confirmo nueva", "confirmo incompleta", "confirmo minima", "confirmo mínima"}
CANCEL_WORDS = {"no", "para", "cancela", "olvida", "nada", "atras", "descarta"}
HARD_CANCEL_WORDS = {
    "cancela", "cancelar", "cancelalo", "cancelalo", "cancelad", "olvida", "olvidalo", "para", "parar",
    "deten", "detente", "aborta", "abortar", "descarta", "salir", "olvidalo"
}


class UnifiedOrchestrator:
    """Orquestador Conversacional Unificado — ecoFlow v4.0
    Soporta: entidades, artículos, servicios, contratos y facturación.
    Separación estricta lógica-presentación.
    """

    async def dispatch(self, session: dict, message: str, file_bytes=None, filename=None, trace_id=None) -> dict:
        if file_bytes and filename:
            return await self._handle_multimodal(session, file_bytes, filename)

        st = session.get("state", StateMachine.IDLE)
        msg_c = clean_text(message)
        analysis = await cognitive_service.parse_intent(message, f"Estado: {st}, Flujo: {session.get('flow_mode', 'ninguno')}")
        intent = str(analysis.get("intent", ""))
        entities = analysis.get("entities", {})

        logger.info(f"[TRACE:{trace_id}] state={st} intent={intent} entities={list(entities.keys())}")

        # ── 0. OVERRIDE GLOBAL DE CANCELACIÓN (prioridad absoluta) ──────────────
        if self._has_active_context(session) and self._is_explicit_cancel(intent, msg_c):
            return self._clear_flow(session, "Operación cancelada. No he hecho ningún cambio.")

        # ── 1. FLUJOS ACTIVOS (prioridad máxima) ──────────────────────────────
        if st == "AWAITING_DISAMBIGUATION":
            return await self._handle_disambiguation(session, message)

        if st == "AWAITING_DELETE_CONFIRM":
            return await self._handle_delete_confirm(session, message, msg_c, intent)

        active = detect_active_flow(st, session)
        if active:
            if active == "entity": return await self._flow_entity(session, message, analysis)
            if active == "service": return await self._flow_service(session, message, analysis)
            if active == "expense": return await self._flow_expense(session, message, analysis)
            if active == "contract": return await self._flow_contract(session, message, analysis)
            if active == "factura": return await self._flow_factura(session, message, analysis)
            if active == "article": return await self._flow_article(session, message, analysis)

        # ── 2. HISTORIAL PROACTIVO (PKEY detectado) ───────────────────────────
        hist = detect_proactive_history_intent(message, msg_c, intent, entities)
        if hist:
            if hist["action"] == "add_history":
                return await self._handle_add_history(session, hist["pkey"], hist["nota"])
            return await self._handle_query_history(session, hist["pkey"])

        # ── 3. CONSULTA DE CAMPO DE ENTIDAD ───────────────────────────────────
        if intent == "consultar_campo":
            return await self._handle_query_field(session, entities)

        # ── 4. BORRADOS CON CONFIRMACIÓN DOBLE ────────────────────────────────
        if intent in ("delete_service", "delete_contract", "delete_factura"):
            return await self._initiate_delete(session, intent, entities, message)
        if self._looks_like_factura_delete(msg_c, entities):
            return await self._initiate_delete(session, "delete_factura", entities, message)
        if intent == "delete_entity" or self._looks_like_entity_delete(msg_c, entities):
            return await self._initiate_delete(session, "delete_entity", entities, message)

        # ── 4.1 MODIFICACIÓN DE ENTIDAD ───────────────────────────────────────
        if intent == "modify_entity" or self._looks_like_entity_modification(msg_c, entities):
            return await self._handle_modify_entity(session, message, entities)

        # ── 4.2 MODIFICACIÓN DE CONTRATO ──────────────────────────────────────
        if intent == "modify_contract" or self._looks_like_contract_modification(msg_c, entities):
            return await self._handle_modify_contract(session, message, entities)

        # ── 5. CONSULTAS ──────────────────────────────────────────────────────
        if intent in ("query_entity",):
            return await self._handle_query_entity(session, entities)
        if intent in ("query_contract",):
            return await self._handle_query_contract(session, entities)
        if intent == "list_contracts":
            return await self._handle_list_contracts(session, entities)
        if intent in ("query_factura",):
            return await self._handle_query_factura(session, entities)
        if intent == "list_facturas":
            return await self._handle_list_facturas(session, entities)
        if intent == "query_article":
            return await self._handle_query_article(session, entities)

        # ── 6. LANZAMIENTO DE NUEVOS FLUJOS ───────────────────────────────────
        new_flow = detect_new_flow(intent, msg_c)
        if new_flow:
            if new_flow == "entity":
                session.update({"flow_mode": "entity", "flow_data": {}}); return await self._flow_entity(session, message, analysis)
            if new_flow == "service":
                session.update({"flow_mode": "service", "flow_data": {}}); return await self._flow_service(session, message, analysis)
            if new_flow == "article":
                session.update({"flow_mode": "article", "flow_data": {}}); return await self._flow_article(session, message, analysis)
            if new_flow == "contract":
                session.update({"flow_mode": "contract", "flow_data": {}}); return await self._flow_contract(session, message, analysis)
            if new_flow == "factura":
                if intent in NC_MAP:
                    session.update({"flow_mode": "factura", "flow_data": {"nivelcontrol": NC_MAP[intent], "label": NC_LABELS.get(NC_MAP[intent], "Documento")}})
                else:
                    session.update({"flow_mode": "factura", "flow_data": session.get("flow_data", {})})
                return await self._flow_factura(session, message, analysis)

        if intent == "create_contract":
            session.update({"flow_mode": "contract", "flow_data": {}})
            return await self._flow_contract(session, message, analysis)

        if intent in NC_MAP:
            session.update({"flow_mode": "factura", "flow_data": {"nivelcontrol": NC_MAP[intent], "label": NC_LABELS.get(NC_MAP[intent], "Documento")}})
            return await self._flow_factura(session, message, analysis)

        if intent == "create_article":
            session.update({"flow_mode": "article", "flow_data": {}})
            return await self._flow_article(session, message, analysis)

        logger.info(f"[TRACE:{trace_id}] Fallback general")
        return await self._process_general(session, analysis, message)

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: ENTIDADES
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_entity(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "entity"
        d = session["flow_data"]
        e = analysis.get("entities", {})
        if e.get("nombre_cliente"): d["name"] = e["nombre_cliente"]
        if e.get("cif"): d["cif"] = e["cif"]
        if e.get("observaciones"): d["obs"] = e["observaciones"]

        # Fallback operativo en multi-turno real: capturar nombre/CIF aunque el parser no lo extraiga.
        msg_raw = (message or "").strip()
        cif_match = re.search(r"\b([A-Za-z]?\d{7,9}[A-Za-z]?)\b", msg_raw)
        msg_c_raw = clean_text(msg_raw)
        looks_like_command = any(k in msg_c_raw for k in ["crea", "crear", "alta", "dar de alta", "entidad", "cliente", "proveedor", "acreedor"])
        if (
            not d.get("name")
            and msg_raw
            and len(msg_raw.split()) <= 6
            and not cif_match
            and clean_text(msg_raw) not in CONFIRM_WORDS
            and analysis.get("intent") != "create_entity"
            and not looks_like_command
        ):
            d["name"] = msg_raw
        if not d.get("cif") and cif_match:
            d["cif"] = cif_match.group(1).upper()

        for k in ["direccion", "poblacion", "provincia", "cp", "telefono", "email"]:
            if e.get(k):
                d[k] = e[k]
        parsed_guided = self._extract_entity_guided_fields(message)
        if parsed_guided.get("email_explicit_none"):
            d["email_explicit_none"] = True
            d.pop("email", None)
        d.update({k: v for k, v in parsed_guided.items() if k != "email_explicit_none"})

        if not d.get("entity_type"):
            t = self._infer_entity_type(message, e)
            if t.get("status") == "AMBIGUOUS":
                session["state"] = "AWAITING_ENTITY_CONFIRM"
                return {
                    "reply": "Necesito el tipo de entidad para no contaminar datos. Indícame uno: cliente, proveedor, acreedor, personal laboral, sucursal o usuario del sistema.",
                    "state": "AWAITING_ENTITY_CONFIRM"
                }
            d["entity_type"] = t.get("tipo") or "PREENTIDAD"

        if not d.get("name"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": "¿A qué nombre damos el alta?", "state": "AWAITING_ENTITY_CONFIRM"}

        # Guardrail temprano de duplicado por nombre antes de pedir CIF.
        if d.get("name"):
            if d.get("last_checked_name") != d.get("name"):
                d.pop("name_candidates", None)
                d.pop("name_candidates_ack", None)
                d["last_checked_name"] = d.get("name")

            if not d.get("name_candidates_ack") and not d.get("cif"):
                if not d.get("name_candidates"):
                    by_name = await resolver.resolve_entity(name=d.get("name"))
                    if by_name.get("status") == "RESOLVED":
                        d["name_candidates"] = [by_name.get("data")]
                    elif by_name.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                        d["name_candidates"] = by_name.get("options", [])

                if d.get("name_candidates"):
                    sel = resolver.parse_selection(message, len(d.get("name_candidates", [])))
                    if sel is not None:
                        chosen = d["name_candidates"][sel - 1]
                        session["last_resolved_entity"] = chosen
                        return self._clear_flow(session, f"Operación detenida: la entidad ya existe (**{chosen.get('nombre')}**, ID {chosen.get('pkey')}).")

                    if len(d.get("name_candidates", [])) == 1 and self._is_positive_duplicate_confirmation(message):
                        chosen = d["name_candidates"][0]
                        session["last_resolved_entity"] = chosen
                        return self._clear_flow(session, f"Perfecto, no doy de alta una entidad nueva. Ya existe **{chosen.get('nombre')}** (CIF {chosen.get('cif')}).")

                    msg_c_name = self._normalize_for_confirm(message)
                    if msg_c_name in {"continuar", "ninguna", "no es ninguna", "crear nueva"}:
                        d["name_candidates_ack"] = True
                    else:
                        session["state"] = "AWAITING_ENTITY_CONFIRM"
                        opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(d["name_candidates"])])
                        return {
                            "reply": f"He encontrado posibles coincidencias por nombre:\n{opts}\n\nResponde con el número si es una existente, o escribe **CONTINUAR** si quieres crear una nueva.",
                            "state": "AWAITING_ENTITY_CONFIRM"
                        }

        if not d.get("cif"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": f"¿Y el CIF de **{d['name']}**?", "state": "AWAITING_ENTITY_CONFIRM"}

        if not d.get("duplicate_checked"):
            dup = await resolver.detect_entity_duplicates(name=d.get("name"), cif=d.get("cif"))
            d["duplicate_checked"] = True
            if dup.get("status") == "POSSIBLE_DUPLICATE" and dup.get("options"):
                d["duplicate_candidates"] = dup.get("options", [])
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(d["duplicate_candidates"])])
                session["state"] = "AWAITING_ENTITY_CONFIRM"
                return {
                    "reply": f"⚠️ Posibles duplicados antes de crear:\n{opts}\n\nResponde con el número si ya existe, o escribe **CONFIRMO NUEVA** para forzar alta nueva.",
                    "state": "AWAITING_ENTITY_CONFIRM"
                }

        if d.get("duplicate_candidates") and not d.get("duplicate_ack"):
            sel = resolver.parse_selection(message, len(d.get("duplicate_candidates", [])))
            if sel is not None:
                chosen = d["duplicate_candidates"][sel - 1]
                session["last_resolved_entity"] = chosen
                return self._clear_flow(session, f"Operación detenida: usaré la entidad existente **{chosen.get('nombre')}** (ID {chosen.get('pkey')}).")
            if len(d.get("duplicate_candidates", [])) == 1 and self._is_positive_duplicate_confirmation(message):
                chosen = d["duplicate_candidates"][0]
                session["last_resolved_entity"] = chosen
                return self._clear_flow(session, f"Perfecto, no la doy de alta de nuevo. Ya existe como **{chosen.get('nombre')}** (CIF {chosen.get('cif')}).")
            if self._normalize_for_confirm(message) == "confirmo nueva":
                d["duplicate_ack"] = True
            else:
                session["state"] = "AWAITING_ENTITY_CONFIRM"
                return {
                    "reply": "Hay riesgo de duplicado. Escribe **CONFIRMO NUEVA** para continuar o selecciona una coincidencia existente por número.",
                    "state": "AWAITING_ENTITY_CONFIRM"
                }

        missing = [k for k in ["direccion", "poblacion", "provincia", "cp", "telefono"] if not d.get(k)]
        if not d.get("email") and not d.get("email_explicit_none"):
            missing.append("email")
        if missing and not d.get("guided_ack"):
            if self._normalize_for_confirm(message) in {"confirmo incompleta", "confirmo minima", "confirmo mínima"}:
                d["guided_ack"] = True
            else:
                session["state"] = "AWAITING_ENTITY_CONFIRM"
                mtxt = ", ".join(missing)
                return {
                    "reply": f"Recomendado completar ficha antes de grabar. Faltan: {mtxt}. Puedes enviarme esos datos ahora o escribir **CONFIRMO INCOMPLETA** para alta mínima.",
                    "state": "AWAITING_ENTITY_CONFIRM"
                }

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            p = {
                "DENCOM": d["name"],
                "CIF": d["cif"],
                "SUCURSAL": 1,
                "PAIS": 1,
                "ESTADO": 0,
                "CLIENTE": 0,
                "PROVEEDOR": 0,
                "ACREEDOR": 0,
                "P_LABORAL": 0,
                "SUCURSALES": 0,
                "USUARIO": 0,
                "PREENTIDAD": 0,
            }
            tipo = d.get("entity_type", "PREENTIDAD")
            if tipo == "CLIENTE": p["CLIENTE"] = 1
            elif tipo == "PROVEEDOR": p["PROVEEDOR"] = 1
            elif tipo == "ACREEDOR": p["ACREEDOR"] = 1
            elif tipo == "P_LABORAL": p["P_LABORAL"] = 1
            elif tipo == "SUCURSAL": p["SUCURSALES"] = 1
            elif tipo == "USUARIO": p["USUARIO"] = 1
            else: p["PREENTIDAD"] = 1

            field_map = {
                "direccion": "DIRECCION",
                "poblacion": "POBLACION",
                "provincia": "PROVINCIA",
                "cp": "CP",
                "telefono": "TLF1",
                "email": "EMAIL",
            }
            for k, target in field_map.items():
                if d.get(k):
                    p[target] = d[k]
            if d.get("obs"):
                p["OBSERVACIONES"] = d.get("obs")
            r = await tool_registry.crear_entidad.execute(p)
            if r.get("success"):
                session["last_resolved_entity"] = {"pkey": r.get("pkey"), "nombre": d["name"], "cif": d["cif"]}
                return self._clear_flow(session, f"✅ Alta completada (ID {r.get('pkey')})")
            return {"reply": f"❌ Error ERP: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_ENTITY_CONFIRM"
        obs_txt = f"\n- Obs: {d['obs']}" if d.get("obs") else ""
        return {"reply": f"📋 **Confirmación de Alta**\n- Nombre: **{d['name']}**\n- CIF/NIF: {d['cif']}\n- Tipo: {d.get('entity_type', 'PREENTIDAD')}{obs_txt}\n\n¿Lo grabo ya?", "state": "AWAITING_ENTITY_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: SERVICIOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_service(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "service"
        d = session["flow_data"]
        e = analysis.get("entities", {})

        if not d.get("client_pk"):
            direct_pk = self._extract_contextual_entity_pkey(message, e)
            if direct_pk:
                direct_res = await resolver.resolve_entity(context_pk=direct_pk)
                if direct_res.get("status") == "RESOLVED":
                    d["client_pk"], d["client_name"] = direct_res["data"]["pkey"], direct_res["data"]["nombre"]
                    session["last_resolved_entity"] = direct_res["data"]
                else:
                    d["client_pk"], d["client_name"] = int(direct_pk), f"PKEY {int(direct_pk)}"

        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}

        if not d.get("client_pk") and session.get("last_resolved_entity"):
            ent = session["last_resolved_entity"]
            d["client_pk"], d["client_name"] = ent["pkey"], ent["nombre"]

        if not d.get("client_pk"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": "¿Para qué cliente es el servicio?", "state": "AWAITING_SERVICE_CONFIRM"}

        if e.get("descripcion"): d["task"] = e["descripcion"]
        if not d.get("task"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": f"¿Qué trabajo hacemos para **{d['client_name']}**?", "state": "AWAITING_SERVICE_CONFIRM"}

        if e.get("operario"):
            d["operario_name"] = e["operario"]
        extracted_operario = self._extract_operario_candidate(message)
        if extracted_operario:
            d["operario_name"] = extracted_operario

        if d.get("operario_name") and not d.get("operario_pk"):
            op_res = await resolver.resolve_entity(name=d.get("operario_name"), allowed_types=["USUARIO", "P_LABORAL"])
            if op_res.get("status") == "RESOLVED":
                d["operario_pk"] = op_res["data"]["pkey"]
                d["operario_name"] = op_res["data"].get("nombre", d.get("operario_name"))
            elif op_res.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({
                    "state": "AWAITING_DISAMBIGUATION",
                    "ambiguous_options": op_res.get("options", []),
                    "pending_action": {"intent": "service_operario_select"}
                })
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (ID {x.get('pkey')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varios operarios válidos:\n{opts}\n\nElige uno por número.", "state": "AWAITING_DISAMBIGUATION"}

        if not d.get("operario_pk"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": "Necesito operario para continuar. Indícame nombre o ID de operario (usuario del sistema o personal laboral).", "state": "AWAITING_SERVICE_CONFIRM"}

        if len(clean_text(d["task"])) < 8:
            d.pop("task", None)
            return {"reply": "La descripción es muy corta. ¿Puedes darme un poco más de detalle?", "state": "AWAITING_SERVICE_CONFIRM"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {
                "MODO_ID": 0,
                "CLIENTE": d["client_pk"],
                "CLIENTE_DELEGACION": 1,
                "ESTADO": 0,
                "SUCURSAL": "1",
                "NIVELCONTROL": 1,
                "TIPO_SERVICIO": 2,
                "TIPOCONTACTO": 1,
                "SERVICIO_DESCRIPCION": d["task"],
                "OPERARIO": d["operario_pk"],
                "FECHA_INICIO": get_now_iso(),
            }
            logger.info(f"[SERVICE_TRACE] flow_create_confirm payload={payload}")
            r = await tool_registry.crear_servicio.execute(payload)
            logger.info(f"[SERVICE_TRACE] flow_create_result={r}")
            if r.get("success"):
                return self._clear_flow(session, f"✅ Servicio {r['pkey']} creado para {d['client_name']}.")
            return {"reply": f"❌ Error al grabar el servicio: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_SERVICE_CONFIRM"
        task_short = d['task'][:60] + "..." if len(d['task']) > 60 else d['task']
        return {"reply": f"📋 **Nuevo Servicio**\n- **Cliente**: {d['client_name']}\n- **Operario**: {d.get('operario_name', d.get('operario_pk'))}\n- **Tarea**: {task_short}\n\n¿Grabo?", "state": "AWAITING_SERVICE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: CONTRATOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_contract(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "contract"
        d = session["flow_data"]
        e = analysis.get("entities", {})

        if not d.get("client_pk"):
            direct_pk = self._extract_contextual_entity_pkey(message, e)
            if direct_pk:
                direct_res = await resolver.resolve_entity(context_pk=direct_pk)
                if direct_res.get("status") == "RESOLVED":
                    d["client_pk"], d["client_name"] = direct_res["data"]["pkey"], direct_res["data"]["nombre"]
                    session["last_resolved_entity"] = direct_res["data"]
                else:
                    d["client_pk"], d["client_name"] = int(direct_pk), f"PKEY {int(direct_pk)}"

        # Resolver cliente
        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
                opts = "\n".join([f"{i+1}. {x.get('nombre')}" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}

        if not d.get("client_pk") and session.get("last_resolved_entity"):
            ent = session["last_resolved_entity"]
            d["client_pk"], d["client_name"] = ent["pkey"], ent["nombre"]

        if not d.get("client_pk"):
            session["state"] = "AWAITING_CONTRATO_COLLECT"
            return {"reply": "¿Para qué cliente es el contrato?", "state": "AWAITING_CONTRATO_COLLECT"}

        if e.get("descripcion"): d["descripcion"] = e["descripcion"]
        if e.get("precio"): d["precio"] = float(e["precio"])
        if e.get("referencia"): d["referencia"] = e["referencia"]
        if e.get("observaciones"): d["observaciones"] = e["observaciones"]

        if not d.get("descripcion"):
            session["state"] = "AWAITING_CONTRATO_COLLECT"
            return {"reply": f"¿Qué cubre el contrato para **{d['client_name']}**? (descripción breve)", "state": "AWAITING_CONTRATO_COLLECT"}

        if not d.get("precio"):
            session["state"] = "AWAITING_CONTRATO_COLLECT"
            return {"reply": f"¿Cuál es el precio mensual del contrato?", "state": "AWAITING_CONTRATO_COLLECT"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {
                "pkey_entidad": d["client_pk"],
                "DESCRIPCION": d["descripcion"],
                "PRECIO_UNITARIO": d["precio"],
                "REFERENCIA": d.get("referencia", ""),
                "OBSERVACIONES": d.get("observaciones", "Alta vía ecoFlow"),
            }
            r = await tool_registry.crear_contrato.execute(payload)
            if r.get("success"):
                return self._clear_flow(session, f"✅ Contrato {r['pkey']} creado para {d['client_name']}.")
            return {"reply": f"❌ Error ERP: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_CONTRATO_COLLECT"
        return {"reply": f"📋 **Nuevo Contrato**\n- **Cliente**: {d['client_name']}\n- **Descripción**: {d['descripcion']}\n- **Precio/mes**: {d['precio']}€\n\n¿Lo grabo?", "state": "AWAITING_CONTRATO_COLLECT"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: FACTURACIÓN (todos los NIVELCONTROL permitidos vía NC_MAP)
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_factura(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "factura"
        d = session["flow_data"]
        e = analysis.get("entities", {})

        if not d.get("client_pk"):
            direct_pk = self._extract_contextual_entity_pkey(message, e)
            if direct_pk:
                direct_res = await resolver.resolve_entity(context_pk=direct_pk)
                if direct_res.get("status") == "RESOLVED":
                    d["client_pk"], d["client_name"] = direct_res["data"]["pkey"], direct_res["data"]["nombre"]
                    session["last_resolved_entity"] = direct_res["data"]
                else:
                    d["client_pk"], d["client_name"] = int(direct_pk), f"PKEY {int(direct_pk)}"

        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
                opts = "\n".join([f"{i+1}. {x.get('nombre')}" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}

        if not d.get("client_pk") and session.get("last_resolved_entity"):
            ent = session["last_resolved_entity"]
            d["client_pk"], d["client_name"] = ent["pkey"], ent["nombre"]

        nc = d.get("nivelcontrol")
        label = d.get("label", "Documento")

        if not d.get("client_pk"):
            session["state"] = "AWAITING_FACTURA_COLLECT"
            return {"reply": f"¿Para qué cliente es {label}?", "state": "AWAITING_FACTURA_COLLECT"}

        if e.get("descripcion"): d["descripcion"] = e["descripcion"]
        if e.get("total"): d["total"] = float(e["total"])
        if not d.get("total") and e.get("precio"):
            d["total"] = float(e["precio"])
        if e.get("referencia"): d["referencia"] = e["referencia"]
        if not d.get("descripcion") and d.get("nivelcontrol") == 6 and "gasto" in clean_text(message):
            d["descripcion"] = "Gasto"

        if not d.get("descripcion"):
            session["state"] = "AWAITING_FACTURA_COLLECT"
            return {"reply": f"¿Cuál es la descripción del concepto?", "state": "AWAITING_FACTURA_COLLECT"}

        if not d.get("total"):
            session["state"] = "AWAITING_FACTURA_COLLECT"
            return {"reply": "¿Cuál es el importe total (sin IVA)?", "state": "AWAITING_FACTURA_COLLECT"}

        # Confirmación obligatoria para todos los documentos de facturación
        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            from app.mappers.facturacion_mapper import FacturacionMapper
            mapper = FacturacionMapper()
            payload = mapper.build(
                nivelcontrol=nc,
                pkey_entidad=d["client_pk"],
                descripcion=d["descripcion"],
                total=d["total"],
                referencia=d.get("referencia", ""),
            )
            r = await tool_registry.grabar_facturacion.execute(payload)
            if r.get("success"):
                return self._clear_flow(session, f"✅ {label} {r.get('pkey')} registrado para {d['client_name']}.")
            return self._clear_flow(session, f"❌ Error ERP al registrar {label}: {r.get('error')}")

        session["state"] = "AWAITING_FACTURA_COLLECT"
        return {"reply": f"📋 **{label}**\n- **Cliente**: {d['client_name']}\n- **Concepto**: {d['descripcion']}\n- **Importe**: {d['total']}€\n\n¿Grabo?", "state": "AWAITING_FACTURA_COLLECT"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: ARTÍCULOS (crear)
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_article(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}
        session["flow_mode"] = "article"
        d = session["flow_data"]
        e = analysis.get("entities", {})
        if e.get("descripcion"): d["descripcion"] = e["descripcion"]
        if e.get("referencia"): d["referencia"] = e["referencia"]
        if e.get("familia") is not None:
            try:
                d["familia"] = int(e.get("familia"))
            except Exception:
                pass

        if not d.get("descripcion"):
            session["state"] = "AWAITING_ARTICULO_COLLECT"
            return {"reply": "¿Cómo se llama o describe el artículo?", "state": "AWAITING_ARTICULO_COLLECT"}

        prov_name = self._extract_provider_candidate(message, analysis.get("entities", {}))
        if prov_name:
            d["proveedor_name"] = prov_name

        if d.get("proveedor_name") and not d.get("proveedor_pk"):
            p_res = await resolver.resolve_entity(name=d.get("proveedor_name"), allowed_types=["PROVEEDOR"])
            if p_res.get("status") == "RESOLVED":
                d["proveedor_pk"] = p_res["data"]["pkey"]
                d["proveedor_name"] = p_res["data"].get("nombre", d.get("proveedor_name"))
            elif p_res.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({
                    "state": "AWAITING_DISAMBIGUATION",
                    "ambiguous_options": p_res.get("options", []),
                    "pending_action": {"intent": "article_provider_select"}
                })
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varios proveedores posibles:\n{opts}\n\nElige uno por número.", "state": "AWAITING_DISAMBIGUATION"}

        missing_recommended = []
        if not d.get("familia"):
            missing_recommended.append("familia")
        if not d.get("proveedor_pk"):
            missing_recommended.append("proveedor")

        if missing_recommended and not d.get("guided_ack"):
            if self._normalize_for_confirm(message) in {"confirmo incompleta", "confirmo minima", "confirmo mínima"}:
                d["guided_ack"] = True
            else:
                miss = ", ".join(missing_recommended)
                session["state"] = "AWAITING_ARTICULO_COLLECT"
                return {
                    "reply": f"Recomendado completar {miss} antes de crear. Puedes indicarlos ahora o escribir **CONFIRMO INCOMPLETA** para alta mínima.",
                    "state": "AWAITING_ARTICULO_COLLECT"
                }

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {"DESCRIPCION": d["descripcion"], "REFERENCIA": d.get("referencia", "")}
            if d.get("familia"):
                payload["FAMILIA"] = d.get("familia")
            if d.get("proveedor_pk"):
                payload["PROVEEDOR"] = d.get("proveedor_pk")
            r = await tool_registry.crear_articulo.execute(payload)
            if r.get("success"):
                return self._clear_flow(session, f"✅ Artículo '{d['descripcion']}' creado (ID {r['pkey']}).")
            return {"reply": f"❌ Error: {r.get('response')}", "state": "idle"}

        session["state"] = "AWAITING_ARTICULO_COLLECT"
        ref_txt = f"\n- Ref: `{d['referencia']}`" if d.get("referencia") else ""
        return {"reply": f"📋 **Nuevo Artículo**\n- Descripción: {d['descripcion']}{ref_txt}\n\n¿Lo creo?", "state": "AWAITING_ARTICULO_COLLECT"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO GASTO (multimodal)
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_expense(self, session: dict, message: str, analysis: dict) -> dict:
        d = session.get("flow_data", {})
        msg_c = clean_text(message)

        if analysis.get("intent") == "confirm" or msg_c in CONFIRM_WORDS:
            cif, nombre = d.get("cif", ""), d.get("proveedor_nombre", "Desconocido")
            pkey_entidad = 0
            res_ent = await tool_registry.buscar_entidad.execute(cif=cif, dencom=nombre)
            if res_ent.get("found"):
                pkey_entidad = int(res_ent.get("pkey"))
            else:
                from app.models.schemas.domain import DomainCommand
                from app.mappers.entidades_mapper import EntidadesMapper
                from uuid import uuid4
                cmd = DomainCommand(intent_name="crear_entidad", operation_id=uuid4(), fields={"DENCOM": nombre, "CIF": cif, "TIPO_ENTIDAD": "ACREEDOR"})
                payload_ent = EntidadesMapper().build(cmd)
                rc = await tool_registry.crear_entidad.execute(payload_ent)
                if rc.get("success"): pkey_entidad = int(rc.get("pkey"))

            r = await tool_registry.registrar_gasto.execute(
                cif=cif, pkey_entidad=pkey_entidad, fecha=d.get("fecha"), total=d.get("total"),
                base=d.get("base"), referencia=d.get("referencia"), descripcion=d.get("descripcion") or f"Gasto {nombre}"
            )
            if r.get("success"): return self._clear_flow(session, f"✅ Gasto registrado (Doc ID {r.get('pkey')})")
            return self._clear_flow(session, f"❌ Error al registrar gasto: {r.get('error')}")

        if analysis.get("intent") == "cancel" or msg_c in CANCEL_WORDS:
            return self._clear_flow(session, "Gasto descartado.")

        return {"reply": f"¿Registro el gasto de **{d.get('total')}€** de {d.get('proveedor_nombre')}? (si/no)", "state": "AWAITING_EXPENSE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: BORRADO CON DOBLE CONFIRMACIÓN
    # ─────────────────────────────────────────────────────────────────────────
    async def _initiate_delete(self, session: dict, intent: str, entities: dict, raw_message: str = "") -> dict:
        """Primera confirmación de borrado — instancia el estado de espera."""
        logger.info(f"[DELETE_TRACE] initiate intent={intent} state_before={session.get('state')} pending_before={session.get('pending_delete')}")
        pkey = entities.get("pkey_servicio") or entities.get("pkey_contrato") or entities.get("pkey_factura") or entities.get("pkey_entidad") or entities.get("pkey")

        if intent == "delete_entity" and not pkey and raw_message:
            pkey = self._extract_contextual_entity_pkey(raw_message, entities)

        if intent == "delete_entity" and not pkey:
            resolved = await self._resolve_delete_entity_target(session, entities)
            if resolved.get("status") == "RESOLVED":
                pkey = resolved.get("pkey")
            elif resolved.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                return {"reply": "He encontrado varias entidades. Indícame el PKEY exacto para borrar de forma segura.", "state": "idle"}

        if not pkey:
            return {"reply": "¿Cuál es el ID del registro que quieres eliminar?", "state": "idle"}

        module_map = {
            "delete_entity": ("entidad", "ENTIDADES"),
            "delete_service": ("servicio", "SERVICIOS"),
            "delete_contract": ("contrato", "CONTRATOS"),
            "delete_factura": ("documento", "FACTURACIÓN"),
        }
        kind, module = module_map.get(intent, ("registro", "SISTEMA"))

        # Guardar petición pendiente de double-confirm
        session["state"] = "AWAITING_DELETE_CONFIRM"
        session["pending_delete"] = {"intent": intent, "pkey": pkey, "kind": kind}
        logger.info(f"[DELETE_TRACE] pending_set={session.get('pending_delete')} state_after={session.get('state')}")

        return {
            "reply": f"⚠️ Estás a punto de **eliminar** el {kind} ID `{pkey}`. Esta acción es **irreversible**.\n\nEscribe **CONFIRMO** para proceder.",
            "state": "AWAITING_DELETE_CONFIRM"
        }

    async def _handle_delete_confirm(self, session: dict, message: str, msg_c: str, intent: str) -> dict:
        """Segunda confirmación estricta de borrado."""
        logger.info(f"[DELETE_TRACE] confirm_enter state={session.get('state')} msg={clean_text(message)} intent={intent} pending={session.get('pending_delete')}")
        pd = session.get("pending_delete", {})
        if not pd:
            session["state"] = "idle"
            return {"reply": "No había ninguna operación de borrado pendiente.", "state": "idle"}

        if self._is_explicit_cancel(intent, msg_c):
            session.pop("pending_delete", None)
            session["state"] = "idle"
            return {"reply": "Borrado cancelado explícitamente.", "state": "idle"}

        # Exige "confirmo" literal para operaciones destructivas
        if clean_text(message).strip() != "confirmo":
            session["state"] = "AWAITING_DELETE_CONFIRM"
            return {"reply": "Para borrar necesito confirmación estricta. Escribe exactamente CONFIRMO o cancela.", "state": "AWAITING_DELETE_CONFIRM"}

        kind, pkey, intent_name = pd["kind"], pd["pkey"], pd["intent"]

        tool_map = {
            "delete_entity": tool_registry.borrar_entidad,
            "delete_service": tool_registry.borrar_servicio,
            "delete_contract": tool_registry.borrar_contrato,
            "delete_factura": tool_registry.borrar_facturacion,
        }
        tool = tool_map.get(intent_name)
        if tool:
            r = await tool.execute({"pkey": pkey})
            logger.info(f"[DELETE_TRACE] tool_result intent={intent_name} pkey={pkey} result={r}")
            if r.get("success"):
                session.pop("pending_delete", None)
                session["state"] = "idle"
                return {"reply": f"✅ {kind.capitalize()} `{pkey}` eliminado.", "state": "idle"}
            session["state"] = "AWAITING_DELETE_CONFIRM"
            return {"reply": f"❌ Error al eliminar: {r.get('error')}. El borrado sigue pendiente; escribe CONFIRMO para reintentar o cancela.", "state": "AWAITING_DELETE_CONFIRM"}

        session["state"] = "AWAITING_DELETE_CONFIRM"
        return {"reply": "No tengo forma de ejecutar ese borrado todavía. Escribe cancela para limpiar la operación pendiente.", "state": "AWAITING_DELETE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: CONSULTAS
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_query_entity(self, session: dict, entities: dict) -> dict:
        name = entities.get("nombre_cliente")
        cif = entities.get("cif")
        res = await resolver.resolve_entity(name=name, cif=cif)
        if res["status"] == "RESOLVED":
            ent = res["data"]
            session["last_resolved_entity"] = ent
            return {"reply": f"📇 **{ent['nombre']}**\n- ID: {ent['pkey']}\n- CIF: {ent.get('cif', '-')}\n- Tel: {ent.get('telefono', '-')}\n- Email: {ent.get('email', '-')}", "state": "idle"}
        if res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
            opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
            return {"reply": f"Hay varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        return {"reply": "No he encontrado ninguna entidad con esos datos.", "state": "idle"}

    async def _handle_modify_entity(self, session: dict, message: str, entities: dict) -> dict:
        """Modificación mínima end-to-end de entidad con verificación post-condición por lectura."""
        target = await self._resolve_entity_target(session, message, entities)
        if target.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": target.get("options", [])})
            opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
            return {"reply": f"Hay varias entidades posibles:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        if target.get("status") != "RESOLVED":
            return {"reply": "No he podido identificar la entidad a modificar.", "state": "idle"}

        ent = target["data"]
        updates = self._extract_entity_updates(message, entities)
        if not updates:
            return {"reply": "Indica al menos un campo modificable: email, teléfono, dirección u observaciones.", "state": "idle"}

        payload = {"PKEY": ent["pkey"], **updates}
        r = await tool_registry.modificar_entidad.execute(payload)
        if not r.get("success"):
            return {"reply": f"❌ Error al modificar entidad: {r.get('error')}", "state": "idle"}

        read_back = await tool_registry.obtener_entidad.execute({"pkey": ent["pkey"]})
        if not read_back.get("found"):
            return {"reply": "⚠️ Modificación enviada, pero no he podido leer la entidad para verificar el cambio.", "state": "idle"}

        normalized = resolver.normalize_entidad(read_back.get("data", {}))
        ok, detail = self._verify_entity_updates(normalized, updates)
        session["last_resolved_entity"] = normalized
        if not ok:
            return {
                "reply": f"⚠️ La modificación se ejecutó, pero la lectura posterior no refleja todos los cambios esperados ({detail}).",
                "state": "idle",
            }

        changed = ", ".join(detail)
        return {"reply": f"✅ Entidad {ent['pkey']} modificada correctamente ({changed}).", "state": "idle"}

    async def _handle_query_contract(self, session: dict, entities: dict) -> dict:
        pkey = entities.get("pkey_contrato")
        if pkey:
            r = await tool_registry.obtener_contrato.execute({"pkey": pkey})
            if r.get("found"):
                c = r["data"]
                return {"reply": f"📄 **Contrato {pkey}**\n- Cliente: {c.get('ENTIDAD_DES', '-')}\n- Descripción: {c.get('DESCRIPCION', '-')}\n- Referencia: {c.get('REFERENCIA', '-')}\n- Precio: {c.get('PRECIO_UNITARIO', '-')}€\n- Observaciones: {c.get('OBSERVACIONES', '-')}\n- Estado: {c.get('ESTADO', '-')}", "state": "idle"}
        return {"reply": f"No encuentro el contrato `{pkey}`.", "state": "idle"}

    async def _handle_modify_contract(self, session: dict, message: str, entities: dict) -> dict:
        """Modificación robusta de contrato por PKEY con verificación post-condición."""
        pkey = self._extract_contract_pkey(message, entities)
        if not pkey:
            return {"reply": "Indica el PKEY del contrato a modificar (ej: contrato 12345).", "state": "idle"}

        updates = self._extract_contract_updates(message, entities)
        if not updates:
            return {
                "reply": "Indica al menos un campo de contrato modificable: precio, referencia, descripción u observaciones.",
                "state": "idle",
            }

        current = await tool_registry.obtener_contrato.execute({"pkey": pkey})
        if not current.get("found"):
            return {"reply": f"No encuentro el contrato {pkey} para modificarlo.", "state": "idle"}

        base = current.get("data", {}) or {}
        payload = dict(base)
        payload["PKEY"] = pkey
        payload.update(updates)

        logger.info(f"[CONTRACT_TRACE] modify_start pkey={pkey} updates={updates}")
        wr = await tool_registry.modificar_contrato.execute(payload)
        logger.info(f"[CONTRACT_TRACE] modify_result pkey={pkey} result={wr}")
        if not wr.get("success"):
            return {"reply": f"❌ Error al modificar contrato: {wr.get('error')}", "state": "idle"}

        read_back = await tool_registry.obtener_contrato.execute({"pkey": pkey})
        if not read_back.get("found"):
            return {"reply": "⚠️ Modificación enviada, pero no he podido releer el contrato para verificarla.", "state": "idle"}

        ok, detail = self._verify_contract_updates(read_back.get("data", {}) or {}, updates)
        if not ok:
            return {
                "reply": f"⚠️ Contrato {pkey} modificado, pero la lectura posterior no refleja todos los cambios esperados ({', '.join(detail)}).",
                "state": "idle",
            }

        return {"reply": f"✅ Contrato {pkey} modificado correctamente ({', '.join(detail)}).", "state": "idle"}

    async def _handle_list_contracts(self, session: dict, entities: dict) -> dict:
        name = entities.get("nombre_cliente")
        last = session.get("last_resolved_entity")
        pkey_entidad = None
        if name:
            res = await resolver.resolve_entity(name=name)
            if res["status"] == "RESOLVED": pkey_entidad = res["data"]["pkey"]; session["last_resolved_entity"] = res["data"]
        elif last:
            pkey_entidad = last["pkey"]
        if not pkey_entidad:
            return {"reply": "¿De qué cliente quieres ver los contratos?", "state": "idle"}
        r = await tool_registry.listar_contratos.execute({"pkey_entidad": pkey_entidad})
        if not r.get("found"):
            return {"reply": "No hay contratos para ese cliente.", "state": "idle"}
        lines = [f"📋 **Contratos de {last.get('nombre', 'cliente')} ({r['count']} encontrados):**"]
        for c in r["data"][:5]:
            lines.append(f"- ID {c.get('PKEY')}: {c.get('DESCRIPCION', '-')} — {c.get('PRECIO_UNITARIO', 0)}€/mes")
        return {"reply": "\n".join(lines), "state": "idle"}

    async def _handle_query_factura(self, session: dict, entities: dict) -> dict:
        pkey = entities.get("pkey_factura")
        if not pkey:
            return {"reply": "¿Cuál es el ID del documento que quieres consultar?", "state": "idle"}
        r = await tool_registry.obtener_facturacion.execute({"pkey": pkey})
        if r.get("found"):
            f = r["data"]
            nc = f.get("NIVELCONTROL", "?")
            label = NC_LABELS.get(nc, f"Documento NC={nc}")
            return {"reply": f"📑 **{label} {pkey}**\n- Cliente: {f.get('ENTIDAD_DES', '-')}\n- Ref: {f.get('REFERENCIA', '-')}\n- Fecha: {f.get('FECHA', '-')}", "state": "idle"}
        return {"reply": f"No encuentro el documento `{pkey}`.", "state": "idle"}

    async def _handle_list_facturas(self, session: dict, entities: dict) -> dict:
        last = session.get("last_resolved_entity")
        name = entities.get("nombre_cliente")
        client_pk = None
        if name:
            res = await resolver.resolve_entity(name=name)
            if res["status"] == "RESOLVED": client_pk = res["data"]["pkey"]
        elif last:
            client_pk = last["pkey"]
        if not client_pk:
            return {"reply": "¿De qué cliente quieres ver las facturas?", "state": "idle"}
        r = await tool_registry.listar_facturaciones.execute({"ENTIDAD": client_pk})
        if not r.get("found"):
            return {"reply": "No hay documentos de facturación para ese cliente.", "state": "idle"}
        lines = [f"📑 **{r['found']} documentos encontrados:**"]
        for f in r["data"][:5]:
            nc = f.get("NIVELCONTROL", "?")
            label = NC_LABELS.get(nc, f"NC={nc}")
            lines.append(f"- ID {f.get('PKEY')}: {label} — {f.get('REFERENCIA', '-')}")
        return {"reply": "\n".join(lines), "state": "idle"}

    async def _handle_query_article(self, session: dict, entities: dict) -> dict:
        desc = entities.get("descripcion") or entities.get("referencia", "")
        if not desc:
            return {"reply": "¿Qué artículo buscas? (nombre o referencia)", "state": "idle"}
        r = await tool_registry.listar_articulos.execute({"DESCRIPCION": f"%{desc}%"})
        if not r.get("found"):
            return {"reply": f"No encuentro artículos con '{desc}'.", "state": "idle"}
        lines = [f"🔍 **{len(r['data'])} artículo(s) encontrado(s):**"]
        for a in r["data"][:5]:
            lines.append(f"- ID {a.get('PKEY')}: {a.get('DESCRIPCION', '-')} (Ref: {a.get('REFERENCIA', '-')})")
        return {"reply": "\n".join(lines), "state": "idle"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: HISTORIAL DE SERVICIOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_add_history(self, session: dict, pkey: int, nota: str) -> dict:
        logger.info(f"[SERVICE_TRACE] add_history_start pkey={pkey} nota={nota}")
        res_s = await tool_registry.obtener_servicio.execute({"pkey": pkey})
        logger.info(f"[SERVICE_TRACE] add_history_service_lookup={res_s}")
        if not res_s.get("success"):
            return {"reply": f"No encuentro el servicio con ID {pkey}.", "state": "idle"}
        op = res_s.get("data", {}).get("OPERARIO") or -1
        note_clean = self._sanitize_history_note(nota)
        payload = {"PKEY": pkey, "MODO_ID": 0, "DESCRIPCION": note_clean, "OBSERVACIONES": "", "OPERARIO": op, "FECHA": get_now_iso()}
        hr = await tool_registry.grabar_historico.execute(payload)
        logger.info(f"[SERVICE_TRACE] add_history_write_result={hr}")
        return {"reply": f"✅ Nota añadida al historial del servicio {pkey}.", "state": "idle"}

    async def _handle_query_history(self, session: dict, pkey: int) -> dict:
        logger.info(f"[SERVICE_TRACE] query_history_start pkey={pkey}")
        res = await tool_registry.obtener_historico_servicio.execute({"pkey": pkey})
        logger.info(f"[SERVICE_TRACE] query_history_result found={res.get('found')} success={res.get('success')} count={len(res.get('data', [])) if isinstance(res.get('data'), list) else 'n/a'}")
        if not res.get("success") or not res.get("found"):
            return {"reply": f"No hay actuaciones registradas en el servicio {pkey}.", "state": "idle"}
        lines = [f"📋 **Historial del Servicio {pkey}:**"]
        for it in res.get("data", [])[:10]:
            lines.append(f"- {it.get('TEXTO_HISTORIAL', '—')}")
        return {"reply": "\n".join(lines), "state": "idle"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: CAMPO ESPECÍFICO DE ENTIDAD
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_query_field(self, session: dict, entities: dict) -> dict:
        campo = entities.get("campo")
        target_name = entities.get("nombre_cliente")
        last = session.get("last_resolved_entity")
        entidad = None
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED": entidad = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", []), "pending_action": {"intent": "consultar_campo", "campo": campo}})
                opts = "\n".join([f"{i+1}. {x.get('nombre')}" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"¿Cuál exactamente?\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        elif last:
            entidad = last
        if not entidad:
            return {"reply": f"¿De qué cliente quieres saber el {campo or 'dato'}?", "state": "idle"}
        if not campo:
            return {"reply": f"¿Qué quieres saber de {entidad['nombre']}? (teléfono, email, dirección)", "state": "idle"}
        valor = await resolver.obtener_campo(entidad["pkey"], campo)
        session["last_resolved_entity"] = entidad
        return {"reply": f"El/La {campo} de {entidad['nombre']} es: {valor}", "state": "idle"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: DESAMBIGUACIÓN
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_disambiguation(self, session: dict, message: str) -> dict:
        options = session.get("ambiguous_options", [])
        sel = resolver.parse_selection(message, len(options))
        if sel is None:
            return {"reply": f"Elige un número del 1 al {len(options)}.", "state": "AWAITING_DISAMBIGUATION"}
        chosen = options[sel - 1]
        session["last_resolved_entity"] = chosen
        session.pop("ambiguous_options", None)

        pa = session.pop("pending_action", None)
        if pa and pa["intent"] == "consultar_campo":
            v = await resolver.obtener_campo(chosen["pkey"], pa["campo"])
            session["state"] = "idle"
            return {"reply": f"El/La {pa['campo']} de {chosen['nombre']} es: {v}", "state": "idle"}
        if pa and pa.get("intent") == "service_operario_select":
            session.setdefault("flow_data", {})["operario_pk"] = chosen["pkey"]
            session["flow_data"]["operario_name"] = chosen.get("nombre")
            return await self._flow_service(session, "", {"intent": "unknown", "entities": {}})
        if pa and pa.get("intent") == "article_provider_select":
            session.setdefault("flow_data", {})["proveedor_pk"] = chosen["pkey"]
            session["flow_data"]["proveedor_name"] = chosen.get("nombre")
            return await self._flow_article(session, "", {"intent": "unknown", "entities": {}})

        fm = session.get("flow_mode")
        if fm == "service":
            session["flow_data"]["client_pk"] = chosen["pkey"]
            session["flow_data"]["client_name"] = chosen["nombre"]
            return await self._flow_service(session, "", {"intent": "unknown", "entities": {}})
        if fm == "contract":
            session["flow_data"]["client_pk"] = chosen["pkey"]
            session["flow_data"]["client_name"] = chosen["nombre"]
            return await self._flow_contract(session, "", {"intent": "unknown", "entities": {}})
        if fm == "factura":
            session["flow_data"]["client_pk"] = chosen["pkey"]
            session["flow_data"]["client_name"] = chosen["nombre"]
            return await self._flow_factura(session, "", {"intent": "unknown", "entities": {}})

        session["state"] = "idle"
        return {"reply": f"Seleccionado: **{chosen['nombre']}**. ¿Qué necesitas?", "state": "idle"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: MULTIMODAL (GASTO POR DOCUMENTO)
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_multimodal(self, session: dict, file_bytes, filename) -> dict:
        data = await tool_registry.extractor.extract(file_bytes, filename)
        if not data or not data.get("total"):
            return {"reply": "No he podido extraer datos válidos del documento.", "state": "idle"}
        def pf(v):
            if not v: return 0.0
            if isinstance(v, (int, float)): return float(v)
            return float(str(v).replace(",", "."))
        session.update({"flow_mode": "expense", "flow_data": {
            "cif": data.get("cif", ""), "fecha": data.get("fecha", ""),
            "total": pf(data.get("total", 0.0)), "base": pf(data.get("base") or 0.0),
            "referencia": data.get("referencia", ""), "descripcion": data.get("descripcion", ""),
            "proveedor_nombre": data.get("proveedor", "Desconocido")
        }, "state": "AWAITING_EXPENSE_CONFIRM"})
        d = session["flow_data"]
        summary = (f"📄 **Datos extraídos:**\n- Proveedor: {d['proveedor_nombre']}\n- CIF: {d['cif']}\n"
                   f"- Total: **{d['total']}€**\n- Fecha: {d['fecha']}\n\n¿Registramos este gasto?")
        return {"reply": summary, "state": "AWAITING_EXPENSE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: GENERAL FALLBACK
    # ─────────────────────────────────────────────────────────────────────────
    async def _process_general(self, session: dict, analysis: dict, message: str) -> dict:
        target_name = analysis.get("entities", {}).get("nombre_cliente")
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                session["last_resolved_entity"] = res["data"]
                return {"reply": f"He localizado a **{res['data']['nombre']}**. ¿Qué quieres hacer con este cliente?", "state": "idle"}
        return {"reply": "No estoy seguro de qué necesitas. Puedo ayudarte con clientes, servicios, contratos, artículos o facturación.", "state": "idle"}

    # ─────────────────────────────────────────────────────────────────────────
    # UTILS
    # ─────────────────────────────────────────────────────────────────────────
    def _clear_flow(self, session: dict, reply: str) -> dict:
        for k in ["flow_mode", "flow_data", "state", "pending_action", "ambiguous_options", "pending_delete"]:
            session.pop(k, None)
        return {"reply": reply, "state": "idle"}

    def _has_active_context(self, session: dict) -> bool:
        state = str(session.get("state", ""))
        if state.startswith("AWAITING_"):
            return True
        return any(session.get(k) for k in ["flow_mode", "flow_data", "pending_delete", "pending_action", "ambiguous_options"])

    def _is_explicit_cancel(self, intent: str, msg_c: str) -> bool:
        if intent == "cancel":
            return True
        tokens = set(re.findall(r"\b\w+\b", msg_c))
        return bool(tokens.intersection(HARD_CANCEL_WORDS))

    def _normalize_for_confirm(self, text: str) -> str:
        return re.sub(r"\s+", " ", clean_text(text)).strip()

    def _extract_entity_guided_fields(self, message: str) -> dict:
        m = message or ""
        out = {}

        # Ausencia explícita de email (no bloqueante)
        if re.search(r"\b(?:no\s+tiene|sin|no\s+dispone\s+de)\s+email\b", m, flags=re.IGNORECASE):
            out["email_explicit_none"] = True

        dir_m = re.search(r"(?:la\s+)?direcci[oó]n\s*(?:es)?\s*[,=:]?\s*([^\.;]+)", m, flags=re.IGNORECASE)
        if dir_m:
            direccion = dir_m.group(1).strip(" ,")
            direccion = re.sub(r"^(?:es|la|de|en)\b\s*", "", direccion, flags=re.IGNORECASE).strip(" ,")
            direccion = re.split(r"\b(?:en\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+,\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+)$", direccion, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,")
            if len(direccion) > 4 and direccion.lower() not in {"es", "la", "de", "en"}:
                out["direccion"] = direccion

        pob_prov_inline = re.search(r"\ben\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+),\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+)", m, flags=re.IGNORECASE)
        if pob_prov_inline:
            out["poblacion"] = pob_prov_inline.group(1).strip(" ,")
            out["provincia"] = pob_prov_inline.group(2).strip(" ,")

        pob_m = re.search(r"(?:poblacion|población|ciudad)\s*(?:es|:|=)?\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+)", m, flags=re.IGNORECASE)
        if pob_m:
            pob = pob_m.group(1).strip(" ,")
            if pob and pob.lower() not in {"es", "la", "de", "en"}:
                out["poblacion"] = pob

        prov_m = re.search(r"(?:provincia)\s*(?:es|:|=)?\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]+)", m, flags=re.IGNORECASE)
        if prov_m:
            prov = prov_m.group(1).strip(" ,")
            if prov and prov.lower() not in {"es", "la", "de", "en"}:
                out["provincia"] = prov

        cp_m = re.search(r"(?:cp|c\.?p\.?|codigo postal|código postal)\s*(?:es|:|=)?\s*(\d{4,6})", m, flags=re.IGNORECASE)
        if cp_m:
            out["cp"] = cp_m.group(1).strip()
        tel_m = re.search(r"(?:el\s+)?(?:telefono|teléfono|tlf|movil|móvil)\s*(?:es|:|=)?\s*([+\d][\d\s-]{6,})", m, flags=re.IGNORECASE)
        if tel_m:
            out["telefono"] = re.sub(r"\s+", "", tel_m.group(1))
        email_m = re.search(r"(?:mi\s+)?email\s*(?:es|:|=)?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", m, flags=re.IGNORECASE)
        if not email_m:
            email_m = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", m)
        if email_m and not out.get("email_explicit_none"):
            out["email"] = email_m.group(1)
        return out

    def _is_positive_duplicate_confirmation(self, message: str) -> bool:
        t = clean_text(message)
        hints = {
            "si", "sí", "correcto", "efectivamente", "ya esta dada de alta", "ya está dada de alta",
            "ya existe", "esa misma", "es esa", "vale esa", "vale, esa", "es correcto",
        }
        return t in hints or any(x in t for x in hints)

    def _infer_entity_type(self, message: str, entities: dict) -> dict:
        txt = clean_text(message)
        if entities.get("tipo_entidad"):
            t = str(entities.get("tipo_entidad")).strip().upper()
            if t in {"CLIENTE", "PROVEEDOR", "ACREEDOR", "P_LABORAL", "SUCURSAL", "USUARIO", "PREENTIDAD"}:
                return {"status": "RESOLVED", "tipo": t}
        detected = []
        if "cliente" in txt: detected.append("CLIENTE")
        if "proveedor" in txt: detected.append("PROVEEDOR")
        if "acreedor" in txt: detected.append("ACREEDOR")
        if any(k in txt for k in ["personal laboral", "empleado", "trabajador"]): detected.append("P_LABORAL")
        if "sucursal" in txt: detected.append("SUCURSAL")
        if any(k in txt for k in ["usuario del sistema", "usuario interno", "usuario"]): detected.append("USUARIO")
        detected = list(dict.fromkeys(detected))
        if len(detected) > 1:
            return {"status": "AMBIGUOUS"}
        if len(detected) == 1:
            return {"status": "RESOLVED", "tipo": detected[0]}
        return {"status": "NOT_FOUND", "tipo": "PREENTIDAD"}

    def _extract_operario_candidate(self, message: str) -> str | None:
        m = re.search(r"(?:operario|t[eé]cnico|asignar a)\s*[:=]?\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ._-]+)$", message or "", flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .")
        return None

    def _extract_provider_candidate(self, message: str, entities: dict) -> str | None:
        if entities.get("nombre_proveedor"):
            return str(entities.get("nombre_proveedor")).strip()
        m = re.search(r"(?:proveedor)\s*[:=]?\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ._-]+)", message or "", flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .")
        return None

    def _sanitize_history_note(self, nota: str) -> str:
        text = str(nota or "").strip()
        patterns = [
            r"^(?:mete|meter|añade|anade|pon|graba|escribe)\s+(?:una\s+)?(?:linea|línea)?\s*(?:de\s+)?(?:historial)?\s*(?:que\s+diga\s+)?",
            r"^(?:en\s+historial\s+)?(?:pon|añade|anade|mete|graba)\s+",
            r"^(?:historial\s*[:\-]\s*)",
        ]
        for p in patterns:
            text = re.sub(p, "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^[\"'“”]+|[\"'“”]+$", "", text).strip()
        if text:
            return text[:1].upper() + text[1:]
        return "Actuación registrada"

    def _looks_like_entity_modification(self, msg_c: str, entities: dict) -> bool:
        has_action = any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "])
        has_domain = any(k in msg_c for k in ["cliente", "proveedor", "entidad"]) or bool(entities.get("nombre_cliente") or entities.get("cif") or entities.get("pkey_entidad"))
        has_field = any(k in msg_c for k in ["email", "correo", "telefono", "teléfono", "direccion", "dirección", "observaciones", "obs"]) 
        return has_action and has_domain and has_field

    def _looks_like_entity_delete(self, msg_c: str, entities: dict) -> bool:
        has_delete = any(k in msg_c for k in ["borra", "borrar", "elimina", "eliminar"])
        has_domain = any(k in msg_c for k in ["entidad", "cliente", "proveedor"]) or bool(entities.get("nombre_cliente") or entities.get("cif") or entities.get("pkey_entidad"))
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey") or entities.get("pkey_entidad"))
        return has_delete and has_domain and has_ref

    def _looks_like_factura_delete(self, msg_c: str, entities: dict) -> bool:
        has_delete = any(k in msg_c for k in ["borra", "borrar", "elimina", "eliminar"])
        has_domain = any(k in msg_c for k in ["factura", "documento", "albaran", "albaran", "pedido", "presupuesto", "prefactura"])
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey_factura") or entities.get("pkey"))
        return has_delete and has_domain and has_ref

    def _looks_like_contract_modification(self, msg_c: str, entities: dict) -> bool:
        has_action = any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "])
        has_domain = "contrato" in msg_c or bool(entities.get("pkey_contrato"))
        has_field = any(k in msg_c for k in ["precio", "referencia", "descripcion", "descripción", "observaciones", "obs"])
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey_contrato"))
        return has_action and has_domain and has_field and has_ref

    def _extract_contract_pkey(self, message: str, entities: dict) -> int | None:
        pkey = entities.get("pkey_contrato") or entities.get("pkey")
        if pkey:
            try:
                return int(pkey)
            except Exception:
                return None

        msg_c = clean_text(message)
        m = re.search(r"\b(?:contrato|pkey)\s*(\d{3,8})\b", msg_c)
        if m:
            return int(m.group(1))
        m_any = re.search(r"\b(\d{3,8})\b", msg_c)
        if m_any and "contrato" in msg_c:
            return int(m_any.group(1))
        return None

    def _extract_contract_updates(self, message: str, entities: dict) -> dict:
        updates = {}

        precio = entities.get("precio")
        if precio is None:
            m_precio = re.search(r"(?:precio(?:\s+unitario)?|importe)\s*(?:a|es|=)?\s*(\d+(?:[\.,]\d+)?)", clean_text(message))
            if m_precio:
                precio = m_precio.group(1).replace(",", ".")
        if precio is not None:
            try:
                updates["PRECIO_UNITARIO"] = float(precio)
            except Exception:
                pass

        referencia = entities.get("referencia")
        if not referencia:
            m_ref = re.search(r"(?:referencia|ref)\s*(?:a|es|=)?\s*([A-Za-z0-9._\-/]+)", message, flags=re.IGNORECASE)
            if m_ref:
                referencia = m_ref.group(1).strip()
        if referencia:
            updates["REFERENCIA"] = str(referencia).strip()

        descripcion = entities.get("descripcion")
        if not descripcion:
            m_desc = re.search(r"(?:descripcion|descripción)\s*(?:a|es|=)?\s+(.+?)(?:\s+y\s+cambia\s+|\s+y\s+pon\s+|$)", message, flags=re.IGNORECASE)
            if m_desc:
                descripcion = m_desc.group(1).strip(" .")
        if descripcion:
            updates["DESCRIPCION"] = str(descripcion).strip()

        observaciones = entities.get("observaciones")
        if not observaciones:
            m_obs = re.search(r"(?:observaciones?|obs)\s*(?:a|es|:|=)?\s+(.+)$", message, flags=re.IGNORECASE)
            if m_obs:
                observaciones = m_obs.group(1).strip()
        if observaciones:
            updates["OBSERVACIONES"] = str(observaciones).strip()

        return updates

    def _verify_contract_updates(self, contract_data: dict, requested_updates: dict) -> tuple[bool, list[str]]:
        checks = []
        all_ok = True
        for k, v in requested_updates.items():
            current = contract_data.get(k)
            if k == "PRECIO_UNITARIO":
                try:
                    cur_v = float(current)
                    req_v = float(v)
                    ok = abs(cur_v - req_v) < 0.0001
                except Exception:
                    ok = False
            else:
                ok = clean_text(str(current or "")) == clean_text(str(v or ""))
            checks.append(f"{k}={'OK' if ok else 'MISMATCH'}")
            all_ok = all_ok and ok
        return all_ok, checks

    async def _resolve_delete_entity_target(self, session: dict, entities: dict) -> dict:
        name = entities.get("nombre_cliente")
        cif = entities.get("cif")
        if name or cif:
            resolved = await resolver.resolve_entity(name=name, cif=cif)
            if resolved.get("status") == "RESOLVED":
                ent = resolved.get("data", {})
                session["last_resolved_entity"] = ent
                return {"status": "RESOLVED", "pkey": ent.get("pkey")}
            return {"status": resolved.get("status")}
        if session.get("last_resolved_entity"):
            return {"status": "RESOLVED", "pkey": session["last_resolved_entity"].get("pkey")}
        return {"status": "NOT_FOUND"}

    async def _resolve_entity_target(self, session: dict, message: str, entities: dict) -> dict:
        pkey = entities.get("pkey_entidad") or entities.get("pkey")
        if not pkey:
            pkey = self._extract_contextual_entity_pkey(message, entities)
        if pkey:
            try:
                pkey_int = int(pkey)
            except Exception:
                pkey_int = None
            if pkey_int:
                resolved = await resolver.resolve_entity(context_pk=pkey_int)
                if resolved.get("status") == "RESOLVED":
                    session["last_resolved_entity"] = resolved["data"]
                    return resolved

        name = entities.get("nombre_cliente")
        cif = entities.get("cif")
        if name or cif:
            resolved = await resolver.resolve_entity(name=name, cif=cif)
            if resolved.get("status") == "RESOLVED":
                session["last_resolved_entity"] = resolved["data"]
            return resolved

        if session.get("last_resolved_entity"):
            return {"status": "RESOLVED", "data": session["last_resolved_entity"]}
        return {"status": "NOT_FOUND"}

    def _extract_entity_updates(self, message: str, entities: dict) -> dict:
        updates = {}
        msg = message.strip()

        email = entities.get("email")
        tel = entities.get("telefono")
        direccion = entities.get("direccion")
        observaciones = entities.get("observaciones")

        if not email:
            m_email = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", msg)
            if m_email:
                email = m_email.group(1)
        if email:
            updates["EMAIL"] = str(email).strip()

        if not tel:
            m_tel = re.search(r"(?:telefono|teléfono|tlf|movil|móvil)\s*(?:es|a)?\s*([+\d][\d\s-]{5,})", clean_text(msg))
            if m_tel:
                tel = re.sub(r"\s+", "", m_tel.group(1))
        if tel:
            updates["TLF1"] = str(tel).strip()

        if not direccion:
            m_dir = re.search(r"(?:direccion|dirección)\s*(?:es|a)?\s+(.+)$", msg, flags=re.IGNORECASE)
            if m_dir:
                direccion = m_dir.group(1).strip()
        if direccion:
            updates["DIRECCION"] = str(direccion).strip()

        if not observaciones:
            m_obs = re.search(r"(?:observaciones?|obs)\s*(?:es|:)?\s+(.+)$", msg, flags=re.IGNORECASE)
            if m_obs:
                observaciones = m_obs.group(1).strip()
        if observaciones:
            updates["OBSERVACIONES"] = str(observaciones).strip()

        return updates

    def _verify_entity_updates(self, normalized_entity: dict, requested_updates: dict) -> tuple[bool, list[str]]:
        checks = []
        all_ok = True
        for k, v in requested_updates.items():
            if k == "EMAIL":
                current = str(normalized_entity.get("email") or "").strip()
            elif k == "TLF1":
                current = str(normalized_entity.get("telefono") or "").strip()
                current = re.sub(r"\s+", "", current)
                v = re.sub(r"\s+", "", str(v))
            elif k == "DIRECCION":
                current = str(normalized_entity.get("direccion") or "").strip()
            elif k == "OBSERVACIONES":
                # Este campo no está en normalize_entidad; se verifica de forma conservadora por lectura cruda
                current = ""
            else:
                continue

            if k == "OBSERVACIONES":
                checks.append(f"{k}=pendiente_de_lectura_explícita")
                continue

            ok = clean_text(current) == clean_text(str(v))
            all_ok = all_ok and ok
            checks.append(f"{k}={'OK' if ok else 'MISMATCH'}")

        return all_ok, checks

    def _extract_contextual_entity_pkey(self, message: str, entities: dict) -> int | None:
        """Resolución conservadora de PKEY directa para entidad en dominios que ya están activos."""
        pkey = entities.get("pkey_entidad") or entities.get("pkey")
        if pkey:
            try:
                return int(pkey)
            except Exception:
                return None

        msg = clean_text(message)
        # Formatos explícitos: "PKEY 12345", "cliente 12345", "proveedor 12345", "entidad 12345"
        m = re.search(r"\b(?:pkey|cliente|proveedor|entidad)\s*(\d{3,8})\b", msg)
        if m:
            return int(m.group(1))

        # Solo números (ej. "12345") cuando el usuario responde con la referencia directa
        m_only = re.fullmatch(r"\s*(\d{3,8})\s*", msg)
        if m_only:
            return int(m_only.group(1))
        return None


orchestrator = UnifiedOrchestrator()
