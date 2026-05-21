import logging, json, unicodedata, re
from datetime import datetime
from app.services.cognitive_service import cognitive_service
from app.services.resolver import resolver
from app.services.tools.registry import tool_registry
from app.services.orchestrator_routing import detect_active_flow, detect_proactive_history_intent, detect_new_flow
from app.services.conversational_logic import IntentAction, StateMachine
from app.services.normalizers import (
    classify_short_user_act,
    looks_like_short_value,
    is_explicit_no_email,
    extract_service_datetime_text,
    normalize_cif_nif,
    normalize_phone,
    normalize_cp,
    normalize_email,
)

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
FACT_NC_ALLOWED = {1, 4, 5, 6}
FACT_NC_BLOCKED = {13, 20}

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

SOFT_SELECT_WORDS = {"si", "sí", "esa", "ese", "esa misma", "ese mismo", "correcto", "correcta", "vale", "ok"}
LIST_QUERY_HINTS = {"dime los", "que hay", "listar", "lista", "busca", "buscar", "muéstrame", "muestrame", "clientes"}

ENTITY_CONTEXT_STATE = "ENTITY_CONTEXT"
SERVICE_CONTEXT_STATE = "SERVICE_CONTEXT"
CONTRACT_CONTEXT_STATE = "CONTRAT_CONTEXT"
ARTICLE_CONTEXT_STATE = "ARTICLE_CONTEXT"
FACT_CONTEXT_STATE = "FACT_CONTEXT"


class UnifiedOrchestrator:
    """Orquestador Conversacional Unificado — ecoFlow v4.0
    Soporta: entidades, artículos, servicios, contratos y facturación.
    Separación estricta lógica-presentación.
    """

    async def dispatch(self, session: dict, message: str, file_bytes=None, filename=None, trace_id=None) -> dict:
        if file_bytes and filename:
            return await self._handle_multimodal(session, file_bytes, filename)

        session.setdefault("flow_slots", {})
        session.setdefault("pending_field", None)
        session.setdefault("candidate", None)
        session.setdefault("last_prompt_type", None)
        # Contexto canónico Fase B (sin tocar modelo DB):
        # - active_entity: entidad activa para consulta/acción
        # - active_service: servicio activo para follow-ups
        # - last_operation_result: resultado operacional mínimo y disciplinado
        session.setdefault("active_entity", session.get("last_resolved_entity"))
        session.setdefault("active_service", None)
        session.setdefault("active_article", None)
        session.setdefault("active_contract", None)
        session.setdefault("active_fact_doc", None)
        session.setdefault("active_fact_line", None)
        session.setdefault("last_operation_result", None)
        session["last_user_act"] = classify_short_user_act(message or "")

        st = session.get("state", StateMachine.IDLE)
        msg_c = clean_text(message)
        analysis = await cognitive_service.parse_intent(message, f"Estado: {st}, Flujo: {session.get('flow_mode', 'ninguno')}")
        intent = str(analysis.get("intent", ""))
        entities = analysis.get("entities", {})

        logger.info(f"[TRACE:{trace_id}] state={st} intent={intent} entities={list(entities.keys())}")

        # ── 0.b CAMBIO EXPLÍCITO DE FLUJO A MITAD DE UNO ACTIVO ────────────────
        # Evita bucles cuando el usuario abandona un alta incompleta y pide otro dominio.
        active_now = detect_active_flow(st, session)
        requested_new_flow = detect_new_flow(intent, msg_c)
        if (
            active_now
            and active_now != "disambiguation"
            and requested_new_flow
            and requested_new_flow != active_now
            and clean_text(message) not in CONFIRM_WORDS
        ):
            self._clear_flow(session, "")
            session.update({"flow_mode": requested_new_flow, "flow_data": {}})
            if requested_new_flow == "entity":
                return await self._flow_entity(session, message, analysis)
            if requested_new_flow == "service":
                return await self._flow_service(session, message, analysis)
            if requested_new_flow == "contract":
                return await self._flow_contract(session, message, analysis)
            if requested_new_flow == "factura":
                return await self._flow_factura(session, message, analysis)
            if requested_new_flow == "article":
                return await self._flow_article(session, message, analysis)

        # ── 0. OVERRIDE GLOBAL DE CANCELACIÓN (prioridad absoluta) ──────────────
        if self._has_active_context(session) and self._is_explicit_cancel(intent, msg_c) and not requested_new_flow:
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

        # ── 1.1 FOLLOW-UP OPERATIVO SOBRE ÚLTIMO SERVICIO (consulta rápida) ───
        if self._looks_like_last_service_followup(session, msg_c):
            return await self._handle_last_service_followup(session, msg_c)

        # ── 1.2 CONTINUIDAD DE CONTEXTO EN IDLE (multi-turno) ─────────────────
        context_followup = await self._handle_domain_context_followup(session, message, msg_c, intent, entities)
        if context_followup is not None:
            return context_followup

        # ── 2. HISTORIAL PROACTIVO (PKEY detectado) ───────────────────────────
        hist = detect_proactive_history_intent(message, msg_c, intent, entities)
        if hist:
            if hist["action"] == "add_history":
                return await self._handle_add_history(session, hist["pkey"], hist["nota"])
            return await self._handle_query_history(session, hist["pkey"])

        # ── 3. CONSULTA DE CAMPO (ARTÍCULO / CONTRATO / ENTIDAD) ──────────────
        if self._looks_like_article_field_query(intent, msg_c, entities, session):
            return await self._handle_query_article_field(session, message, entities)

        if self._looks_like_contract_field_query(intent, msg_c, entities, session):
            return await self._handle_query_contract_field(session, message, entities)

        if intent == "consultar_campo":
            return await self._handle_query_field(session, entities, message)

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

        # ── 4.3 MODIFICACIÓN DE FACTURACIÓN (C4 controlado) ───────────────────
        if intent == "modify_factura" or self._looks_like_factura_modification(msg_c, entities, session):
            return await self._handle_modify_factura(session, message, entities)

        # ── 4.4 MODIFICACIÓN DE ARTÍCULO ──────────────────────────────────────
        if intent == "modify_article" or self._looks_like_article_modification(msg_c, entities, session):
            return await self._handle_modify_article(session, message, entities)

        # ── 5. CONSULTAS ──────────────────────────────────────────────────────
        if intent in ("query_entity",):
            return await self._handle_query_entity(session, entities)
        if intent in ("query_contract",):
            return await self._handle_query_contract(session, entities)
        if intent == "list_contracts":
            return await self._handle_list_contracts(session, entities)
        if intent in ("query_factura",):
            return await self._handle_query_factura(session, entities, message)
        if self._looks_like_factura_lines_query(msg_c, entities, session):
            return await self._handle_query_factura_lines(session, message, entities)
        if intent == "list_facturas":
            return await self._handle_list_facturas(session, entities)
        if self._looks_like_factura_listing_query(intent, msg_c, entities):
            return await self._handle_list_facturas(session, entities)
        if intent == "query_article":
            return await self._handle_query_article(session, entities)

        # ── 5.1 CONTINUIDAD PRONOMINAL DE CAMPO EN ENTIDADES ─────────────────
        inferred_field = self._infer_entity_field_from_text(msg_c)
        if inferred_field and session.get("last_resolved_entity"):
            inferred_entities = dict(entities or {})
            inferred_entities.setdefault("campo", inferred_field)
            return await self._handle_query_field(session, inferred_entities, message)

        # ── 5.2 BÚSQUEDA/LISTADO DE ENTIDADES POR TEXTO LIBRE ─────────────────
        if self._looks_like_entity_listing_query(intent, msg_c, entities):
            return await self._handle_list_entities(session, message, entities)

        # ── 5.3 BÚSQUEDA/LISTADO NATURAL DE CONTRATOS ─────────────────────────
        if self._looks_like_contract_listing_query(intent, msg_c, entities):
            return await self._handle_list_contracts(session, entities, message)

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
        # Aislamiento de contexto: al entrar en entidad, invalidamos servicio activo previo.
        session["active_service"] = None
        session["active_article"] = None
        session.setdefault("flow_slots", {})["entity"] = d
        e = analysis.get("entities", {})
        if e.get("nombre_cliente"): d["name"] = e["nombre_cliente"]
        if e.get("cif"): d["cif"] = normalize_cif_nif(e["cif"])
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
        if d.get("cp"):
            d["cp"] = normalize_cp(d.get("cp"))
        if d.get("telefono"):
            d["telefono"] = normalize_phone(d.get("telefono"))
        if d.get("email"):
            d["email"] = normalize_email(d.get("email"))
        parsed_guided = self._extract_entity_guided_fields(message)
        if parsed_guided.get("email_explicit_none"):
            d["email_explicit_none"] = True
            d.pop("email", None)
        if is_explicit_no_email(message):
            d["email_explicit_none"] = True
            d.pop("email", None)
        d.update({k: v for k, v in parsed_guided.items() if k != "email_explicit_none"})

        pre_entity = self._precheck_entity_create(d)
        if not pre_entity.get("ok"):
            return {"reply": f"Bloqueado por validación previa de entidad: {pre_entity.get('reason')}", "state": "AWAITING_ENTITY_CONFIRM"}

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
            session["pending_field"] = "name"
            session["last_prompt_type"] = "ask_missing_name"
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
                        return self._clear_flow(session, f"Perfecto, no doy de alta una entidad nueva. Ya existe **{chosen.get('nombre')}** (ID {chosen.get('pkey')}, CIF {chosen.get('cif')}).")

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
            session["pending_field"] = "cif"
            session["last_prompt_type"] = "ask_missing_cif"
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
                return self._clear_flow(session, f"Perfecto, no la doy de alta de nuevo. Ya existe como **{chosen.get('nombre')}** (ID {chosen.get('pkey')}, CIF {chosen.get('cif')}).")
            if clean_text(message) in CONFIRM_WORDS and d.get("duplicate_candidates"):
                chosen = d["duplicate_candidates"][0]
                session["last_resolved_entity"] = chosen
                return self._clear_flow(session, f"Confirmado. Para evitar duplicados usaré la entidad existente **{chosen.get('nombre')}** (ID {chosen.get('pkey')}).")
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
            if self._normalize_for_confirm(message) in {"confirmo incompleta", "confirmo minima", "confirmo mínima"} or clean_text(message) in CONFIRM_WORDS:
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
                session["active_entity"] = session["last_resolved_entity"]
                verify_ok = False
                verify_err = None
                try:
                    vr = await resolver.resolve_entity(context_pk=int(r.get("pkey")))
                    verify_ok = vr.get("status") == "RESOLVED"
                except Exception as ex:
                    verify_err = str(ex)
                session["last_operation_result"] = {
                    "domain": "entity",
                    "operation": "create",
                    "identifier": int(r.get("pkey")) if r.get("pkey") else None,
                    "verifiable": True,
                    "verified": bool(verify_ok),
                    "reusable_summary": {
                        "entity_id": int(r.get("pkey")) if r.get("pkey") else None,
                        "name": d.get("name"),
                        "cif": d.get("cif"),
                    },
                }
                if verify_ok:
                    return self._clear_flow(session, f"✅ Alta completada (ID {r.get('pkey')}) y verificada.")
                if verify_err:
                    return self._clear_flow(session, f"✅ Alta completada (ID {r.get('pkey')}), pero la verificación por lectura ha fallado ({verify_err}).")
                return self._clear_flow(session, f"✅ Alta completada (ID {r.get('pkey')}), pero no he podido verificar por lectura.")
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
        session.setdefault("flow_slots", {})["service"] = d
        e = analysis.get("entities", {})
        # Contexto dominante de servicio durante el flujo activo.
        session.setdefault("active_service", None)
        session["active_article"] = None
        logger.info(
            "[SERVICE_TRACE] entry state=%s intent=%s keys=%s flow_data_keys=%s msg=%r",
            session.get("state"),
            analysis.get("intent"),
            list((e or {}).keys()),
            list((d or {}).keys()),
            (message or "")[:160],
        )

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
                session["active_entity"] = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}

        if not d.get("client_pk") and session.get("last_resolved_entity"):
            ent = session["last_resolved_entity"]
            d["client_pk"], d["client_name"] = ent["pkey"], ent["nombre"]
            session["active_entity"] = ent

        # Captura temprana: retener datos aportados aunque aún falte otro campo.
        if e.get("operario"):
            d["operario_name"] = e["operario"]
        extracted_operario = self._extract_operario_candidate(message)
        if extracted_operario:
            d["operario_name"] = extracted_operario
        extracted_fecha_hora = extract_service_datetime_text(message, e.get("fecha"))
        if extracted_fecha_hora and not d.get("fecha_hora_text"):
            d["fecha_hora_text"] = extracted_fecha_hora
        extracted_contexto = self._extract_service_context_candidate(message)
        if extracted_contexto and not d.get("contexto_text"):
            d["contexto_text"] = extracted_contexto

        if not d.get("client_pk"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            session["pending_field"] = "client"
            session["last_prompt_type"] = "ask_missing_client"
            logger.info("[SERVICE_TRACE] missing client -> ask_client flow_data=%s", d)
            return {"reply": "¿Para qué cliente es el servicio?", "state": "AWAITING_SERVICE_CONFIRM"}

        if e.get("descripcion"):
            d["task"] = e["descripcion"]
        if e.get("tipo_contacto") is not None:
            try:
                d["tipo_contacto"] = int(e.get("tipo_contacto"))
            except Exception:
                pass
        if e.get("estado") is not None:
            try:
                d["estado"] = int(e.get("estado"))
            except Exception:
                pass
        if e.get("tipo_servicio") is not None:
            try:
                d["tipo_servicio"] = int(e.get("tipo_servicio"))
            except Exception:
                pass
        if e.get("nivelcontrol") is not None:
            try:
                d["nivelcontrol"] = int(e.get("nivelcontrol"))
            except Exception:
                pass
        if not d.get("task"):
            task_candidate = self._extract_service_task_candidate(message)
            if task_candidate:
                d["task"] = task_candidate

        if d.get("task") and d.get("contexto_text"):
            task_n = clean_text(str(d.get("task")))
            ctx_n = clean_text(str(d.get("contexto_text")))
            if ctx_n and ctx_n not in task_n:
                d["task"] = f"{d['task']} {d['contexto_text']}".strip()
        if not d.get("task"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            session["pending_field"] = "task"
            session["last_prompt_type"] = "ask_missing_task"
            logger.info(
                "[SERVICE_TRACE] missing task -> ask_task preserved_operario=%s preserved_fecha=%s preserved_contexto=%s",
                d.get("operario_name"),
                d.get("fecha_hora_text"),
                d.get("contexto_text"),
            )
            return {"reply": f"¿Qué trabajo hacemos para **{d['client_name']}**?", "state": "AWAITING_SERVICE_CONFIRM"}

        pending_operario = bool(d.get("client_pk") and d.get("task") and not d.get("operario_pk"))
        pending_field = session.get("pending_field")
        fallback_operario = self._extract_pending_field_value(message, analysis, field="operario")
        if pending_field == "operario" and fallback_operario:
            d["operario_name"] = fallback_operario
        elif pending_operario and not d.get("operario_name") and fallback_operario:
            d["operario_name"] = fallback_operario

        if pending_field == "operario" and clean_text(message) in CONFIRM_WORDS and session.get("pending_operario_candidate_name"):
            d["operario_name"] = session.get("pending_operario_candidate_name")

        if d.get("operario_name"):
            session["pending_operario_candidate_name"] = d.get("operario_name")
            session["candidate"] = {"field": "operario", "value": d.get("operario_name")}

        if pending_operario and not d.get("operario_name"):
            fallback_operario = self._extract_pending_field_value(message, analysis, field="operario")
            if fallback_operario:
                d["operario_name"] = fallback_operario
        logger.info(
            "[SERVICE_TRACE] operario candidates entity=%r extracted=%r final=%r",
            e.get("operario"),
            extracted_operario,
            d.get("operario_name"),
        )

        if d.get("operario_name") and not d.get("operario_pk"):
            op_res = await resolver.resolve_entity(name=d.get("operario_name"), allowed_types=["USUARIO", "P_LABORAL"])
            if op_res.get("status") == "NOT_FOUND":
                # Fallback real: algunos operarios válidos no vienen tipados en ERP.
                op_res = await resolver.resolve_entity(name=d.get("operario_name"))
            if op_res.get("status") == "RESOLVED":
                d["operario_pk"] = op_res["data"]["pkey"]
                d["operario_name"] = op_res["data"].get("nombre", d.get("operario_name"))
                session.pop("pending_field", None)
                session.pop("pending_operario_candidate_name", None)
                session["candidate"] = None
                session["last_prompt_type"] = "operario_resolved"
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
            session["pending_field"] = "operario"
            session["last_prompt_type"] = "ask_missing_operario"
            if d.get("operario_name") and clean_text(message) not in CONFIRM_WORDS:
                session["pending_operario_candidate_name"] = d.get("operario_name")
                session["candidate"] = {"field": "operario", "value": d.get("operario_name")}
                logger.info("[SERVICE_TRACE] unresolved operario candidate=%r -> ask_confirmation", d.get("operario_name"))
                return {
                    "reply": f"Por prudencia, ¿confirmas que el operario es **{d.get('operario_name')}**? Si no, indícame otro nombre o ID.",
                    "state": "AWAITING_SERVICE_CONFIRM",
                }
            logger.info("[SERVICE_TRACE] missing operario_pk -> ask_operario flow_data=%s", d)
            return {"reply": "Necesito operario para continuar. Indícame nombre o ID de operario (usuario del sistema o personal laboral).", "state": "AWAITING_SERVICE_CONFIRM"}

        if len(clean_text(d["task"])) < 8:
            d.pop("task", None)
            return {"reply": "La descripción es muy corta. ¿Puedes darme un poco más de detalle?", "state": "AWAITING_SERVICE_CONFIRM"}

        pre_service = self._precheck_service_create(d)
        if not pre_service.get("ok"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": f"Bloqueado por validación previa de servicio: {pre_service.get('reason')}", "state": "AWAITING_SERVICE_CONFIRM"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {
                "MODO_ID": 0,
                "CLIENTE": d["client_pk"],
                "CLIENTE_DELEGACION": 1,
                "ESTADO": d.get("estado", 0),
                "SUCURSAL": "1",
                "NIVELCONTROL": d.get("nivelcontrol", 1),
                "TIPO_SERVICIO": d.get("tipo_servicio", 2),
                "TIPOCONTACTO": d.get("tipo_contacto", 1),
                "SERVICIO_DESCRIPCION": d["task"],
                "OPERARIO": d["operario_pk"],
                "FECHA_INICIO": d.get("fecha_hora_text") or get_now_iso(),
            }
            logger.info(f"[SERVICE_TRACE] flow_create_confirm payload={payload}")
            r = await tool_registry.crear_servicio.execute(payload)
            logger.info(f"[SERVICE_TRACE] flow_create_result={r}")
            if r.get("success"):
                pkey = r.get("pkey")
                verify_ok = False
                verify_err = None
                if pkey:
                    try:
                        vr = await tool_registry.obtener_servicio.execute({"pkey": int(pkey)})
                        verify_ok = bool(vr.get("success"))
                    except Exception as ex:
                        verify_ok = False
                        verify_err = str(ex)
                service_ctx = {
                    "pkey": int(pkey) if pkey else None,
                    "client_pk": d.get("client_pk"),
                    "client_name": d.get("client_name"),
                    "task": d.get("task"),
                    "fecha_hora_text": d.get("fecha_hora_text") or get_now_iso(),
                    "operario_pk": d.get("operario_pk"),
                    "operario_name": d.get("operario_name"),
                }
                session["active_service"] = service_ctx
                session["last_operation_result"] = {
                    "domain": "service",
                    "operation": "create",
                    "identifier": service_ctx.get("pkey"),
                    "verifiable": True,
                    "verified": verify_ok,
                    "reusable_summary": {
                        "service_id": service_ctx.get("pkey"),
                        "client": service_ctx.get("client_name"),
                        "fecha": service_ctx.get("fecha_hora_text"),
                        "task": service_ctx.get("task"),
                    },
                }
                if verify_ok:
                    return self._clear_flow(session, f"✅ Servicio {pkey} creado para {d['client_name']} y verificado.")
                # Regla estricta: NO usar "no verificable" cuando la API sí permite verificar.
                err_txt = f" ({verify_err})" if verify_err else ""
                return self._clear_flow(session, f"✅ Servicio {pkey} creado para {d['client_name']}, pero la verificación por lectura ha fallado{err_txt}.")
            return {"reply": f"❌ Error al grabar el servicio: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_SERVICE_CONFIRM"
        task_short = d['task'][:60] + "..." if len(d['task']) > 60 else d['task']
        fecha_txt = f"\n- **Fecha/hora**: {d.get('fecha_hora_text')}" if d.get("fecha_hora_text") else ""
        return {"reply": f"📋 **Nuevo Servicio**\n- **Cliente**: {d['client_name']}\n- **Operario**: {d.get('operario_name', d.get('operario_pk'))}{fecha_txt}\n- **Tarea**: {task_short}\n\n¿Grabo?", "state": "AWAITING_SERVICE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: CONTRATOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_contract(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "contract"
        d = session["flow_data"]
        session["active_article"] = None
        session["active_service"] = None
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
        if not target_name:
            target_name = self._extract_contract_client_hint(message)
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
        session["active_entity"] = None
        session["active_article"] = None
        session["active_contract"] = None
        e = analysis.get("entities", {})

        provider_hint = e.get("proveedor_nombre") or e.get("nombre_proveedor") or e.get("proveedor")
        if not provider_hint:
            m_prov = re.search(r"proveedor\s+([\w\-\s]+)$", clean_text(message or ""))
            if m_prov:
                provider_hint = m_prov.group(1).strip()
        if provider_hint and not d.get("client_name_candidate"):
            d["client_name_candidate"] = str(provider_hint)

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

        if not d.get("client_pk") and session.get("pending_field") == "client" and clean_text(message) in CONFIRM_WORDS:
            cand = d.get("client_name_candidate")
            if cand:
                cand_res = await resolver.resolve_entity(name=cand)
                if cand_res.get("status") == "RESOLVED":
                    d["client_pk"], d["client_name"] = cand_res["data"]["pkey"], cand_res["data"]["nombre"]
                    session["last_resolved_entity"] = cand_res["data"]

        nc = d.get("nivelcontrol")
        label = d.get("label", "Documento")

        if not d.get("client_pk"):
            session["state"] = "AWAITING_FACTURA_COLLECT"
            session["pending_field"] = "client"
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
            session["pending_field"] = "descripcion"
            return {"reply": f"¿Cuál es la descripción del concepto?", "state": "AWAITING_FACTURA_COLLECT"}

        if not d.get("total"):
            session["state"] = "AWAITING_FACTURA_COLLECT"
            session["pending_field"] = "total"
            return {"reply": "¿Cuál es el importe total (sin IVA)?", "state": "AWAITING_FACTURA_COLLECT"}

        # Confirmación obligatoria para todos los documentos de facturación
        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            pre = self._precheck_facturacion_create(d)
            if not pre.get("ok"):
                session["state"] = "AWAITING_FACTURA_COLLECT"
                return {"reply": f"Bloqueado por validación previa de facturación: {pre.get('reason')}", "state": "AWAITING_FACTURA_COLLECT"}

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
                pkey = r.get("pkey")
                verified = False
                rb_data = {}
                if pkey:
                    rb = await tool_registry.obtener_facturacion.execute({"pkey": int(pkey)})
                    verified = bool(rb.get("found"))
                    rb_data = rb.get("data") or {}
                if verified:
                    session["active_fact_doc"] = {
                        "pkey": int(pkey),
                        "nivelcontrol": rb_data.get("NIVELCONTROL", nc),
                        "referencia": rb_data.get("REFERENCIA", d.get("referencia", "")),
                        "entidad": rb_data.get("ENTIDAD") or d.get("client_pk"),
                        "raw": rb_data,
                    }
                    session["active_fact_line"] = None
                    session["last_operation_result"] = {
                        "domain": "facturacion",
                        "operation": "create",
                        "identifier": int(pkey),
                        "verifiable": True,
                        "verified": True,
                        "reusable_summary": {"fact_doc_id": int(pkey)},
                    }
                    return self._clear_flow(session, f"✅ {label} {pkey} registrado para {d['client_name']} y verificado por lectura.")
                return self._clear_flow(session, f"✅ {label} {pkey} registrado para {d['client_name']}.")
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
        session["active_entity"] = None
        session["active_service"] = None
        e = analysis.get("entities", {})
        if e.get("descripcion"): d["descripcion"] = e["descripcion"]
        if e.get("referencia"): d["referencia"] = e["referencia"]
        if e.get("familia") is not None:
            try:
                d["familia"] = int(e.get("familia"))
            except Exception:
                pass
        if e.get("marca") is not None:
            try:
                d["marca"] = int(e.get("marca"))
            except Exception:
                d["marca_name"] = str(e.get("marca"))

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

        if e.get("familia") is not None and not d.get("familia"):
            fam_candidate = str(e.get("familia")).strip()
            fam_res = await self._resolve_article_catalog_id("FAMILIA", fam_candidate)
            if fam_res.get("status") == "RESOLVED":
                d["familia"] = fam_res["id"]
            elif fam_res.get("status") == "AMBIGUOUS":
                session.update({
                    "state": "AWAITING_DISAMBIGUATION",
                    "ambiguous_options": fam_res.get("options", []),
                    "pending_action": {"intent": "article_family_select"}
                })
                lines = "\n".join([f"{i+1}. {x.get('nombre')} (ID {x.get('pkey')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"He encontrado varias familias posibles:\n{lines}\n\nElige una por número.", "state": "AWAITING_DISAMBIGUATION"}

        if e.get("marca") is not None and not d.get("marca"):
            marca_candidate = str(e.get("marca")).strip()
            marca_res = await self._resolve_article_catalog_id("MARCA", marca_candidate)
            if marca_res.get("status") == "RESOLVED":
                d["marca"] = marca_res["id"]
            elif marca_res.get("status") == "AMBIGUOUS":
                session.update({
                    "state": "AWAITING_DISAMBIGUATION",
                    "ambiguous_options": marca_res.get("options", []),
                    "pending_action": {"intent": "article_brand_select"}
                })
                lines = "\n".join([f"{i+1}. {x.get('nombre')} (ID {x.get('pkey')})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"He encontrado varias marcas posibles:\n{lines}\n\nElige una por número.", "state": "AWAITING_DISAMBIGUATION"}

        pre_article = self._precheck_article_create(d)
        if not pre_article.get("ok"):
            session["state"] = "AWAITING_ARTICULO_COLLECT"
            return {"reply": f"Bloqueado por validación previa de artículo: {pre_article.get('reason')}", "state": "AWAITING_ARTICULO_COLLECT"}

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
            if d.get("marca"):
                payload["MARCA"] = d.get("marca")
            r = await tool_registry.crear_articulo.execute(payload)
            if r.get("success"):
                pkey = r.get("pkey")
                verified = False
                if pkey:
                    rb = await tool_registry.obtener_articulo.execute(int(pkey))
                    verified = bool(rb.get("found"))
                    if verified:
                        a = rb.get("data") or {}
                        session["active_article"] = {
                            "pkey": int(pkey),
                            "descripcion": a.get("DESCRIPCION", d.get("descripcion")),
                            "referencia": a.get("REFERENCIA", d.get("referencia", "")),
                            "raw": a,
                        }
                if verified:
                    session["last_operation_result"] = {
                        "domain": "article",
                        "operation": "create",
                        "identifier": int(pkey),
                        "verifiable": True,
                        "verified": True,
                        "reusable_summary": {"article_id": int(pkey)},
                    }
                    return self._clear_flow(session, f"✅ Artículo '{d['descripcion']}' creado (ID {pkey}) y verificado por lectura.")
                return self._clear_flow(session, f"✅ Artículo '{d['descripcion']}' creado (ID {pkey}).")
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
            session["active_entity"] = ent
            session["active_service"] = None
            return {"reply": f"📇 **{ent['nombre']}**\n- ID: {ent['pkey']}\n- CIF: {ent.get('cif', '-')}\n- Tel: {ent.get('telefono', '-')}\n- Email: {ent.get('email', '-')}", "state": "idle"}
        if res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
            opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
            return {"reply": f"Hay varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        return {"reply": "No he encontrado ninguna entidad con esos datos.", "state": "idle"}

    async def _handle_list_entities(self, session: dict, message: str, entities: dict) -> dict:
        hint = (entities or {}).get("nombre_cliente") or self._extract_entity_listing_hint(message)
        if not hint:
            return {"reply": "Dime un nombre o parte del nombre para buscar (por ejemplo: Cristian).", "state": "idle"}

        res = await resolver.resolve_entity(name=hint)
        if res.get("status") == "RESOLVED":
            ent = res["data"]
            session["last_resolved_entity"] = ent
            return {"reply": f"He encontrado una coincidencia: **{ent.get('nombre')}** (ID {ent.get('pkey')}).", "state": "idle"}

        if res.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            opts = res.get("options", [])
            session.update({
                "state": "AWAITING_DISAMBIGUATION",
                "ambiguous_options": opts,
                "pending_action": {"intent": "list_entities", "hint": hint}
            })
            lines = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif') or '-'})" for i, x in enumerate(opts)])
            return {"reply": f"He encontrado estas coincidencias para '{hint}':\n{lines}\n\nElige por número o escribe el nombre completo.", "state": "AWAITING_DISAMBIGUATION"}

        return {"reply": f"No he encontrado entidades que coincidan con '{hint}'.", "state": "idle"}

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
        pkey = entities.get("pkey_contrato") or entities.get("pkey")
        if not pkey and session.get("active_contract"):
            pkey = session["active_contract"].get("pkey")
        if pkey:
            r = await tool_registry.obtener_contrato.execute({"pkey": pkey})
            if r.get("found"):
                c = r["data"]
                session["active_contract"] = {
                    "pkey": int(c.get("PKEY") or pkey),
                    "referencia": c.get("REFERENCIA", "-"),
                    "codigo_contrato": c.get("CODIGO_CONTRATO", "-"),
                    "estado": c.get("ESTADO"),
                    "periodicidad": c.get("PERIODICIDAD"),
                    "raw": c,
                }
                session["active_entity"] = None
                session["active_article"] = None
                session["active_service"] = None
                return {"reply": f"📄 **Contrato {pkey}**\n- Cliente: {c.get('ENTIDAD_DES', '-')}\n- Descripción: {c.get('DESCRIPCION', '-')}\n- Referencia: {c.get('REFERENCIA', '-')}\n- Precio: {c.get('PRECIO_UNITARIO', '-')}€\n- Observaciones: {c.get('OBSERVACIONES', '-')}\n- Estado: {c.get('ESTADO', '-')}", "state": CONTRACT_CONTEXT_STATE}
        return {"reply": f"No encuentro el contrato `{pkey}`.", "state": CONTRACT_CONTEXT_STATE}

    async def _handle_query_contract_field(self, session: dict, message: str, entities: dict) -> dict:
        field = self._infer_contract_field_from_text(clean_text(message or ""))
        if not field:
            return {"reply": "¿Qué campo del contrato quieres consultar? (referencia, código, periodicidad, estado, bloque)", "state": CONTRACT_CONTEXT_STATE}

        target = await self._resolve_contract_target(session, message, entities)
        if target.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            opts = target.get("options", [])
            session.update({
                "state": "AWAITING_DISAMBIGUATION",
                "ambiguous_options": opts,
                "pending_action": {"intent": "query_contract_field_select", "field": field, "entities": entities},
            })
            lines = "\n".join([f"{i+1}. Contrato {x.get('pkey')} ({x.get('referencia') or '-'})" for i, x in enumerate(opts)])
            return {"reply": f"Hay varios contratos posibles:\n{lines}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}
        if target.get("status") != "RESOLVED":
            return {"reply": "No tengo un contrato activo. Indícame ID o un criterio de búsqueda.", "state": CONTRACT_CONTEXT_STATE}

        contract = target.get("data", {})
        rb = await tool_registry.obtener_contrato.execute({"pkey": int(contract.get("pkey"))})
        if not rb.get("found"):
            return {"reply": f"No he podido leer el contrato {contract.get('pkey')}", "state": CONTRACT_CONTEXT_STATE}
        raw = rb.get("data") or {}
        session["active_contract"] = {
            "pkey": int(raw.get("PKEY") or contract.get("pkey")),
            "referencia": raw.get("REFERENCIA", "-"),
            "codigo_contrato": raw.get("CODIGO_CONTRATO", "-"),
            "estado": raw.get("ESTADO"),
            "periodicidad": raw.get("PERIODICIDAD"),
            "raw": raw,
        }
        session["active_entity"] = None
        session["active_article"] = None
        session["active_service"] = None
        value = self._get_contract_field_value(raw, field)
        return {"reply": f"El campo **{field}** del contrato {contract.get('pkey')} es: {value}", "state": CONTRACT_CONTEXT_STATE}

    async def _handle_modify_contract(self, session: dict, message: str, entities: dict) -> dict:
        """Modificación robusta de contrato por PKEY con verificación post-condición."""
        target = await self._resolve_contract_target(session, message, entities)
        if target.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            opts = target.get("options", [])
            session.update({
                "state": "AWAITING_DISAMBIGUATION",
                "ambiguous_options": opts,
                "pending_action": {"intent": "modify_contract_select", "message": message, "entities": entities},
            })
            lines = "\n".join([f"{i+1}. Contrato {x.get('pkey')} ({x.get('referencia') or '-'})" for i, x in enumerate(opts)])
            return {"reply": f"Hay varios contratos posibles:\n{lines}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}
        if target.get("status") != "RESOLVED":
            return {"reply": "Indica el PKEY del contrato a modificar o selecciona uno por listado.", "state": "idle"}
        pkey = int(target["data"]["pkey"])

        out_scope = self._detect_contract_out_of_scope_request(message, entities)
        if out_scope:
            return {"reply": f"Bloqueado por validación previa de contrato: campos fuera de alcance C3 ({', '.join(out_scope)}).", "state": "idle"}

        updates = self._extract_contract_updates(message, entities)
        if not updates:
            return {
                "reply": "Indica al menos un campo modificable permitido: referencia, código, periodicidad, estado o bloque.",
                "state": "idle",
            }

        pre = self._precheck_contract_modify_safe(updates)
        if not pre.get("ok"):
            return {"reply": f"Bloqueado por validación previa de contrato: {pre.get('reason')}", "state": "idle"}

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
        rb = read_back.get("data", {}) or {}
        session["active_contract"] = {
            "pkey": int(rb.get("PKEY") or pkey),
            "referencia": rb.get("REFERENCIA", "-"),
            "codigo_contrato": rb.get("CODIGO_CONTRATO", "-"),
            "estado": rb.get("ESTADO"),
            "periodicidad": rb.get("PERIODICIDAD"),
            "raw": rb,
        }
        session["active_entity"] = None
        session["active_article"] = None
        session["active_service"] = None
        if not ok:
            return {
                "reply": f"⚠️ Contrato {pkey} modificado, pero la lectura posterior no refleja todos los cambios esperados ({', '.join(detail)}).",
                "state": "idle",
            }

        session["last_operation_result"] = {
            "domain": "contract",
            "operation": "modify",
            "identifier": int(pkey),
            "verifiable": True,
            "verified": True,
            "reusable_summary": {"contract_id": int(pkey)},
        }
        return {"reply": f"✅ Contrato {pkey} modificado correctamente ({', '.join(detail)}).", "state": "idle"}

    async def _handle_list_contracts(self, session: dict, entities: dict, message: str | None = None) -> dict:
        name = entities.get("nombre_cliente")
        last = session.get("last_resolved_entity")
        pkey_entidad = None
        if name:
            res = await resolver.resolve_entity(name=name)
            if res["status"] == "RESOLVED": pkey_entidad = res["data"]["pkey"]; session["last_resolved_entity"] = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", []), "pending_action": {"intent": "list_contracts_pick_entity", "message": message}})
                opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif') or '-'})" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"Hay varias entidades posibles:\n{opts}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}
        elif last:
            pkey_entidad = last["pkey"]
        elif session.get("active_contract"):
            pkey_entidad = (session.get("active_contract", {}).get("raw") or {}).get("ENTIDAD")
        elif message:
            hint = self._extract_contract_listing_hint(message)
            if hint and hint.isdigit():
                pkey_entidad = int(hint)
        if not pkey_entidad:
            return {"reply": "¿De qué cliente quieres ver los contratos?", "state": CONTRACT_CONTEXT_STATE}
        r = await tool_registry.listar_contratos.execute({"pkey_entidad": pkey_entidad})
        if not r.get("found"):
            return {"reply": "No hay contratos para ese cliente.", "state": CONTRACT_CONTEXT_STATE}
        options = [
            {
                "pkey": int(c.get("PKEY") or 0),
                "referencia": c.get("REFERENCIA", ""),
                "codigo_contrato": c.get("CODIGO_CONTRATO", ""),
                "nombre": c.get("DESCRIPCION", "-"),
                "raw": c,
            }
            for c in r["data"][:5]
        ]
        if len(options) == 1:
            chosen = options[0]
            session["active_contract"] = {
                "pkey": chosen["pkey"],
                "referencia": chosen.get("referencia") or "-",
                "codigo_contrato": chosen.get("codigo_contrato") or "-",
                "estado": (chosen.get("raw") or {}).get("ESTADO"),
                "periodicidad": (chosen.get("raw") or {}).get("PERIODICIDAD"),
                "raw": chosen.get("raw") or {},
            }
            session["active_entity"] = None
            session["active_article"] = None
            session["active_service"] = None
            return {"reply": f"📄 Contrato {chosen['pkey']} seleccionado automáticamente (única coincidencia).", "state": CONTRACT_CONTEXT_STATE}

        session.update({
            "state": "AWAITING_DISAMBIGUATION",
            "ambiguous_options": options,
            "pending_action": {"intent": "list_contracts"},
        })
        lines = [f"📋 **Contratos encontrados ({len(options)}):**"]
        for i, c in enumerate(options, start=1):
            lines.append(f"{i}. ID {c.get('pkey')} — Ref: {c.get('referencia') or '-'} — {c.get('nombre')}")
        lines.append("\nElige uno por número para fijar contrato activo.")
        return {"reply": "\n".join(lines), "state": "AWAITING_DISAMBIGUATION"}

    async def _handle_query_factura(self, session: dict, entities: dict, message: str | None = None) -> dict:
        pkey = entities.get("pkey_factura") or entities.get("pkey")
        if not pkey and message:
            m = re.search(r"\b(?:documento|factura|id)?\s*(\d{1,8})\b", clean_text(message or ""))
            if m:
                try:
                    pkey = int(m.group(1))
                except Exception:
                    pkey = None
        if not pkey and session.get("active_fact_doc"):
            pkey = session["active_fact_doc"].get("pkey")
        if not pkey:
            return {"reply": "¿Cuál es el ID del documento que quieres consultar?", "state": FACT_CONTEXT_STATE}
        r = await tool_registry.obtener_facturacion.execute({"pkey": pkey})
        if r.get("found"):
            f = r["data"]
            session["active_fact_doc"] = {
                "pkey": int(f.get("PKEY") or pkey),
                "nivelcontrol": f.get("NIVELCONTROL"),
                "referencia": f.get("REFERENCIA", ""),
                "entidad": f.get("ENTIDAD"),
                "raw": f,
            }
            session["active_fact_line"] = None
            session["active_entity"] = None
            session["active_article"] = None
            session["active_contract"] = None
            nc = f.get("NIVELCONTROL", "?")
            label = NC_LABELS.get(nc, f"Documento NC={nc}")
            return {"reply": f"📑 **{label} {pkey}**\n- Cliente: {f.get('ENTIDAD_DES', '-')}\n- Ref: {f.get('REFERENCIA', '-')}\n- Fecha: {f.get('FECHA', '-')}", "state": FACT_CONTEXT_STATE}
        return {"reply": f"No encuentro el documento `{pkey}`.", "state": FACT_CONTEXT_STATE}

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
            return {"reply": "¿De qué cliente quieres ver las facturas?", "state": FACT_CONTEXT_STATE}

        payload = {"ENTIDAD": client_pk}
        nc = entities.get("nivelcontrol")
        if nc is not None:
            try:
                payload["NIVELCONTROL"] = int(nc)
            except Exception:
                pass
        r = await tool_registry.listar_facturaciones.execute(payload)
        if not r.get("found"):
            return {"reply": "No hay documentos de facturación para ese cliente.", "state": FACT_CONTEXT_STATE}

        options = [
            {
                "pkey": int(f.get("PKEY") or 0),
                "nombre": NC_LABELS.get(f.get("NIVELCONTROL", "?"), f"NC={f.get('NIVELCONTROL', '?')}"),
                "referencia": f.get("REFERENCIA", ""),
                "raw": f,
            }
            for f in r.get("data", [])[:5]
        ]

        if len(options) == 1:
            chosen = options[0]
            session["active_fact_doc"] = {
                "pkey": chosen["pkey"],
                "nivelcontrol": (chosen.get("raw") or {}).get("NIVELCONTROL"),
                "referencia": chosen.get("referencia", ""),
                "entidad": (chosen.get("raw") or {}).get("ENTIDAD"),
                "raw": chosen.get("raw") or {},
            }
            session["active_fact_line"] = None
            session["active_entity"] = None
            session["active_article"] = None
            session["active_contract"] = None
            return {"reply": f"📑 Documento {chosen['pkey']} seleccionado automáticamente (única coincidencia).", "state": FACT_CONTEXT_STATE}

        session.update({
            "state": "AWAITING_DISAMBIGUATION",
            "ambiguous_options": options,
            "pending_action": {"intent": "list_fact_docs"},
        })
        lines = [f"📑 **{len(options)} documentos encontrados:**"]
        for i, it in enumerate(options, start=1):
            lines.append(f"{i}. ID {it.get('pkey')}: {it.get('nombre')} — Ref: {it.get('referencia') or '-'}")
        lines.append("\nElige uno por número para fijar documento activo.")
        return {"reply": "\n".join(lines), "state": "AWAITING_DISAMBIGUATION"}

    async def _handle_modify_factura(self, session: dict, message: str, entities: dict) -> dict:
        target = await self._resolve_fact_doc_target(session, message, entities)
        if target.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            opts = target.get("options", [])
            session.update({
                "state": "AWAITING_DISAMBIGUATION",
                "ambiguous_options": opts,
                "pending_action": {"intent": "modify_fact_doc_select", "message": message, "entities": entities},
            })
            lines = "\n".join([f"{i+1}. ID {x.get('pkey')} — {x.get('nombre') or x.get('referencia') or '-'}" for i, x in enumerate(opts)])
            return {"reply": f"Hay varios documentos posibles:\n{lines}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}
        if target.get("status") != "RESOLVED":
            return {"reply": "No tengo un documento de facturación inequívoco para modificar.", "state": "idle"}

        doc = target.get("data", {})
        updates = self._extract_fact_doc_updates(message, entities)
        if not updates:
            return {"reply": "Indica al menos un campo modificable permitido: referencia, observaciones o fecha.", "state": "idle"}

        pre = self._precheck_facturacion_modify(doc, updates)
        if not pre.get("ok"):
            return {"reply": f"Bloqueado por validación previa de facturación: {pre.get('reason')}", "state": "idle"}

        base = await tool_registry.obtener_facturacion.execute({"pkey": int(doc.get("pkey"))})
        if not base.get("found"):
            return {"reply": f"No encuentro el documento {doc.get('pkey')} para modificarlo.", "state": "idle"}

        payload = dict(base.get("data") or {})
        payload.update(updates)
        payload["PKEY"] = int(doc.get("pkey"))

        from app.connectors.facturacion import FacturacionConnector
        wr = await FacturacionConnector().modificar_facturacion(payload)
        if wr.get("mensaje") != "OK":
            return {"reply": f"❌ Error al modificar documento: {wr.get('lista')}", "state": "idle"}

        rb = await tool_registry.obtener_facturacion.execute({"pkey": int(doc.get("pkey"))})
        if not rb.get("found"):
            return {"reply": "⚠️ Modificación enviada, pero no he podido verificar por lectura.", "state": "idle"}

        rb_data = rb.get("data") or {}
        ok, detail = self._verify_fact_doc_updates(rb_data, updates)
        session["active_fact_doc"] = {
            "pkey": int(rb_data.get("PKEY") or doc.get("pkey")),
            "nivelcontrol": rb_data.get("NIVELCONTROL"),
            "referencia": rb_data.get("REFERENCIA", ""),
            "entidad": rb_data.get("ENTIDAD"),
            "raw": rb_data,
        }
        session["active_fact_line"] = None
        session["active_entity"] = None
        session["active_article"] = None
        session["active_contract"] = None

        if not ok:
            return {"reply": f"⚠️ Documento {doc.get('pkey')} modificado, pero la lectura posterior no refleja todo ({', '.join(detail)}).", "state": "idle"}

        session["last_operation_result"] = {
            "domain": "facturacion",
            "operation": "modify",
            "identifier": int(doc.get("pkey")),
            "verifiable": True,
            "verified": True,
            "reusable_summary": {"fact_doc_id": int(doc.get("pkey"))},
        }
        return {"reply": f"✅ Documento {doc.get('pkey')} modificado correctamente ({', '.join(detail)}).", "state": "idle"}

    async def _handle_query_factura_lines(self, session: dict, message: str, entities: dict) -> dict:
        pkey = entities.get("pkey_factura") or entities.get("pkey")
        if not pkey and session.get("active_fact_doc"):
            pkey = session["active_fact_doc"].get("pkey")
        if not pkey:
            return {"reply": "Indica el documento (ID) para consultar líneas.", "state": FACT_CONTEXT_STATE}

        msg_c = clean_text(message or "")
        line_no = entities.get("linea")
        if line_no is None:
            m_line = re.search(r"\blinea\s*(\d{1,4})\b", msg_c)
            if m_line:
                line_no = m_line.group(1)

        if line_no is not None:
            try:
                line_i = int(line_no)
            except Exception:
                return {"reply": "El número de línea no es válido.", "state": FACT_CONTEXT_STATE}
            rb = await tool_registry.obtener_facturacion_linea.execute({"PKEY": int(pkey), "LINEA": int(line_i)})
            if not rb.get("found"):
                return {"reply": f"No encuentro la línea {line_i} del documento {pkey}.", "state": FACT_CONTEXT_STATE}
            ln = rb.get("data") or {}
            session["active_fact_doc"] = {"pkey": int(pkey), "nivelcontrol": session.get("active_fact_doc", {}).get("nivelcontrol"), "referencia": session.get("active_fact_doc", {}).get("referencia", ""), "entidad": session.get("active_fact_doc", {}).get("entidad"), "raw": session.get("active_fact_doc", {}).get("raw", {})}
            session["active_fact_line"] = {"pkey": int(pkey), "linea": int(line_i), "raw": ln}
            return {"reply": f"📄 Línea {line_i} del documento {pkey}:\n- Artículo: {ln.get('ARTICULO_DES', ln.get('CODART', '-'))}\n- Cantidad: {ln.get('UNIDADES', '-')}\n- Precio: {ln.get('PRECIO_UNITARIO', '-')}", "state": FACT_CONTEXT_STATE}

        r = await tool_registry.listar_facturacion_lineas.execute({"PKEY": int(pkey)})
        if not r.get("found"):
            return {"reply": f"No hay líneas para el documento {pkey}.", "state": FACT_CONTEXT_STATE}
        data = r.get("data", [])
        lines = [f"📄 **Líneas del documento {pkey}** ({len(data)}):"]
        for ln in data[:8]:
            lines.append(f"- Línea {ln.get('LINEA')}: {ln.get('ARTICULO_DES', ln.get('CODART', '-'))} · Uds {ln.get('UNIDADES', '-')} · Precio {ln.get('PRECIO_UNITARIO', '-')}")
        lines.append("\n(Consulta en solo lectura en C4)")
        return {"reply": "\n".join(lines), "state": FACT_CONTEXT_STATE}

    async def _handle_query_article(self, session: dict, entities: dict) -> dict:
        hint = entities.get("descripcion") or entities.get("referencia")
        if not hint:
            return {"reply": "¿Qué artículo buscas? (nombre o referencia)", "state": ARTICLE_CONTEXT_STATE}

        hint_s = str(hint).strip()
        filters = {"DESCRIPCION": f"%{hint_s}%"}
        if re.search(r"[A-Za-z].*\d|\d.*[A-Za-z]", hint_s):
            filters = {"REFERENCIA": f"%{hint_s}%"}

        r = await tool_registry.listar_articulos.execute(filters)
        data = r.get("data", []) if r.get("found") else []
        if not data and filters.get("REFERENCIA"):
            r = await tool_registry.listar_articulos.execute({"DESCRIPCION": f"%{hint_s}%"})
            data = r.get("data", []) if r.get("found") else []

        if not data:
            return {"reply": f"No encuentro artículos con '{hint_s}'.", "state": ARTICLE_CONTEXT_STATE}

        if len(data) == 1:
            a = data[0]
            article = {
                "pkey": int(a.get("PKEY") or 0),
                "descripcion": a.get("DESCRIPCION", "-"),
                "referencia": a.get("REFERENCIA", "-"),
                "raw": a,
            }
            session["active_article"] = article
            session["active_entity"] = None
            session["active_service"] = None
            session["last_operation_result"] = {
                "domain": "article",
                "operation": "query",
                "identifier": article["pkey"],
                "verifiable": True,
                "verified": True,
                "reusable_summary": {"article_id": article["pkey"]},
            }
            return {
                "reply": f"📦 **{article['descripcion']}**\n- ID: {article['pkey']}\n- Ref: {article['referencia']}",
                "state": ARTICLE_CONTEXT_STATE,
            }

        options = [
            {
                "pkey": int(a.get("PKEY") or 0),
                "nombre": a.get("DESCRIPCION", "-"),
                "referencia": a.get("REFERENCIA", "-"),
                "raw": a,
            }
            for a in data[:5]
        ]
        session.update({
            "state": "AWAITING_DISAMBIGUATION",
            "ambiguous_options": options,
            "pending_action": {"intent": "list_articles", "hint": hint_s},
        })
        lines = "\n".join([f"{i+1}. {x.get('nombre')} (Ref: {x.get('referencia')}, ID {x.get('pkey')})" for i, x in enumerate(options)])
        return {"reply": f"He encontrado varios artículos para '{hint_s}':\n{lines}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}

    async def _handle_query_article_field(self, session: dict, message: str, entities: dict) -> dict:
        field = self._infer_article_field_from_text(clean_text(message or ""))
        if not field:
            return {"reply": "¿Qué dato del artículo necesitas? (referencia, proveedor, familia, marca, estado)", "state": ARTICLE_CONTEXT_STATE}

        article = session.get("active_article")
        if not article and entities.get("descripcion"):
            return await self._handle_query_article(session, {"descripcion": entities.get("descripcion")})

        if not article:
            return {"reply": "No tengo un artículo activo. Indícame nombre o referencia primero.", "state": ARTICLE_CONTEXT_STATE}

        rb = await tool_registry.obtener_articulo.execute(int(article.get("pkey")))
        if not rb.get("found"):
            return {"reply": f"No he podido leer el artículo {article.get('pkey')}", "state": ARTICLE_CONTEXT_STATE}

        raw = rb.get("data") or {}
        session["active_article"] = {
            "pkey": int(article.get("pkey")),
            "descripcion": raw.get("DESCRIPCION", article.get("descripcion", "-")),
            "referencia": raw.get("REFERENCIA", article.get("referencia", "-")),
            "raw": raw,
        }
        value = self._get_article_field_value(raw, field)
        return {"reply": f"El campo **{field}** del artículo {article.get('pkey')} es: {value}", "state": ARTICLE_CONTEXT_STATE}

    async def _handle_modify_article(self, session: dict, message: str, entities: dict) -> dict:
        target = await self._resolve_article_target(session, message, entities)
        if target.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
            opts = target.get("options", [])
            session.update({
                "state": "AWAITING_DISAMBIGUATION",
                "ambiguous_options": opts,
                "pending_action": {"intent": "modify_article_select", "message": message, "entities": entities},
            })
            lines = "\n".join([f"{i+1}. {x.get('nombre')} (Ref: {x.get('referencia')}, ID {x.get('pkey')})" for i, x in enumerate(opts)])
            return {"reply": f"Hay varios artículos posibles:\n{lines}\n\nElige por número.", "state": "AWAITING_DISAMBIGUATION"}
        if target.get("status") != "RESOLVED":
            return {"reply": "No he podido identificar el artículo a modificar.", "state": "idle"}

        article = target["data"]
        updates = await self._extract_article_updates(message, entities)

        fam_raw = entities.get("familia")
        if fam_raw is not None and not str(fam_raw).strip().isdigit() and "FAMILIA" not in updates:
            return {"reply": "Bloqueado por validación previa de artículo: familia no resuelta a ID", "state": "idle"}
        marca_raw = entities.get("marca")
        if marca_raw is not None and not str(marca_raw).strip().isdigit() and "MARCA" not in updates:
            return {"reply": "Bloqueado por validación previa de artículo: marca no resuelta a ID", "state": "idle"}
        prov_name = self._extract_provider_candidate(message, entities)
        if prov_name and "PROVEEDOR" not in updates:
            return {"reply": "Bloqueado por validación previa de artículo: proveedor no resuelto", "state": "idle"}

        if not updates:
            return {"reply": "Indica al menos un campo modificable: descripción, referencia, proveedor, familia, marca u observaciones.", "state": "idle"}

        pre = self._precheck_article_modify(updates)
        if not pre.get("ok"):
            return {"reply": f"Bloqueado por validación previa de artículo: {pre.get('reason')}", "state": "idle"}

        wr = await tool_registry.modificar_articulo.execute({"PKEY": int(article["pkey"]), **updates})
        if not wr.get("success"):
            return {"reply": f"❌ Error al modificar artículo: {wr.get('response')}", "state": "idle"}

        rb = await tool_registry.obtener_articulo.execute(int(article["pkey"]))
        if not rb.get("found"):
            return {"reply": "⚠️ Modificación enviada, pero no he podido releer el artículo para verificarla.", "state": "idle"}

        ok, detail = self._verify_article_updates(rb.get("data") or {}, updates)
        session["active_article"] = {
            "pkey": int(article["pkey"]),
            "descripcion": (rb.get("data") or {}).get("DESCRIPCION", article.get("descripcion", "-")),
            "referencia": (rb.get("data") or {}).get("REFERENCIA", article.get("referencia", "-")),
            "raw": rb.get("data") or {},
        }
        session["active_entity"] = None
        session["active_service"] = None

        if not ok:
            return {"reply": f"⚠️ Artículo {article['pkey']} modificado, pero la lectura posterior no refleja todo ({', '.join(detail)}).", "state": "idle"}

        session["last_operation_result"] = {
            "domain": "article",
            "operation": "modify",
            "identifier": int(article["pkey"]),
            "verifiable": True,
            "verified": True,
            "reusable_summary": {"article_id": int(article["pkey"])},
        }
        return {"reply": f"✅ Artículo {article['pkey']} modificado correctamente ({', '.join(detail)}).", "state": "idle"}

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
        session["active_service"] = {"pkey": int(pkey), "raw": session.get("active_service", {}).get("raw", {}) if isinstance(session.get("active_service"), dict) else {}}
        res = await tool_registry.obtener_historico_servicio.execute({"pkey": pkey})
        logger.info(f"[SERVICE_TRACE] query_history_result found={res.get('found')} success={res.get('success')} count={len(res.get('data', [])) if isinstance(res.get('data'), list) else 'n/a'}")
        if not res.get("success") or not res.get("found"):
            rb = await tool_registry.obtener_servicio.execute({"pkey": int(pkey)})
            if rb.get("success"):
                data = rb.get("data") or {}
                session["active_service"] = {
                    "pkey": int(pkey),
                    "fecha_hora_text": data.get("FECHA_INICIO") or data.get("FECHA"),
                    "raw": data,
                }
            return {"reply": f"No hay actuaciones registradas en el servicio {pkey}.", "state": SERVICE_CONTEXT_STATE}
        lines = [f"📋 **Historial del Servicio {pkey}:**"]
        for it in res.get("data", [])[:10]:
            lines.append(f"- {it.get('TEXTO_HISTORIAL', '—')}")
        return {"reply": "\n".join(lines), "state": SERVICE_CONTEXT_STATE}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: CAMPO ESPECÍFICO DE ENTIDAD
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_query_field(self, session: dict, entities: dict, message: str | None = None) -> dict:
        campo = entities.get("campo")
        target_name = entities.get("nombre_cliente")
        if not target_name and message:
            target_name = self._extract_entity_name_hint_from_field_query(message, campo)

        last = session.get("last_resolved_entity")
        entidad = None
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                entidad = res["data"]
            elif res["status"] in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", []), "pending_action": {"intent": "consultar_campo", "campo": campo}})
                opts = "\n".join([f"{i+1}. {x.get('nombre')}" for i, x in enumerate(session["ambiguous_options"])])
                return {"reply": f"¿Cuál exactamente?\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        elif last:
            entidad = last
        elif session.get("active_entity"):
            entidad = session.get("active_entity")

        if not entidad:
            return {"reply": f"¿De qué cliente quieres saber el {campo or 'dato'}?", "state": ENTITY_CONTEXT_STATE}
        if not campo:
            return {"reply": f"¿Qué quieres saber de {entidad['nombre']}? (teléfono, email, dirección)", "state": ENTITY_CONTEXT_STATE}

        valor = await resolver.obtener_campo(entidad["pkey"], campo)
        session["last_resolved_entity"] = entidad
        session["active_entity"] = entidad
        return {"reply": f"El/La {campo} de {entidad['nombre']} es: {valor}", "state": ENTITY_CONTEXT_STATE}

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE: DESAMBIGUACIÓN
    # ─────────────────────────────────────────────────────────────────────────
    async def _handle_disambiguation(self, session: dict, message: str) -> dict:
        options = session.get("ambiguous_options", [])
        msg_c = self._normalize_for_confirm(message or "")
        sel = resolver.parse_selection(message, len(options))

        if sel is None and options:
            # Confirmación natural cuando ya hay una opción clara o selección implícita.
            if msg_c in SOFT_SELECT_WORDS and len(options) >= 1:
                sel = 1
            else:
                msg_norm = clean_text(message or "")
                matched_idx = [
                    i for i, x in enumerate(options, start=1)
                    if clean_text(x.get("nombre") or "") and clean_text(x.get("nombre") or "") in msg_norm
                ]
                if len(matched_idx) == 1:
                    sel = matched_idx[0]

        if sel is None:
            return {"reply": f"Elige un número del 1 al {len(options)} o escribe el nombre exacto.", "state": "AWAITING_DISAMBIGUATION"}

        chosen = options[sel - 1]
        pa = session.pop("pending_action", None)
        session.pop("ambiguous_options", None)

        if pa and pa.get("intent") in {"list_articles", "modify_article_select", "query_article_field_select"}:
            article = {
                "pkey": int(chosen.get("pkey") or 0),
                "descripcion": chosen.get("nombre") or chosen.get("descripcion") or "-",
                "referencia": chosen.get("referencia") or "-",
                "raw": chosen.get("raw") or {},
            }
            session["active_article"] = article
            session["active_entity"] = None
            session["active_service"] = None
            session["state"] = ARTICLE_CONTEXT_STATE
            if pa.get("intent") == "modify_article_select":
                return await self._handle_modify_article(
                    session,
                    pa.get("message") or "",
                    pa.get("entities") or {"pkey": article.get("pkey")},
                )
            if pa.get("intent") == "query_article_field_select":
                return await self._handle_query_article_field(session, message, pa.get("entities") or {})
            return {"reply": f"Seleccionado artículo: **{article['descripcion']}** (ID {article['pkey']}).", "state": ARTICLE_CONTEXT_STATE}

        if pa and pa.get("intent") in {"list_contracts", "modify_contract_select", "query_contract_field_select"}:
            contract = {
                "pkey": int(chosen.get("pkey") or 0),
                "referencia": chosen.get("referencia") or "-",
                "codigo_contrato": chosen.get("codigo_contrato") or "-",
                "estado": (chosen.get("raw") or {}).get("ESTADO"),
                "periodicidad": (chosen.get("raw") or {}).get("PERIODICIDAD"),
                "raw": chosen.get("raw") or {},
            }
            session["active_contract"] = contract
            session["active_entity"] = None
            session["active_article"] = None
            session["active_service"] = None
            session["state"] = CONTRACT_CONTEXT_STATE
            if pa.get("intent") == "modify_contract_select":
                return await self._handle_modify_contract(session, pa.get("message") or "", pa.get("entities") or {"pkey_contrato": contract.get("pkey")})
            if pa.get("intent") == "query_contract_field_select":
                merged = dict(pa.get("entities") or {})
                if pa.get("field"):
                    merged["campo_contrato"] = pa.get("field")
                return await self._handle_query_contract_field(session, message, merged)
            return {"reply": f"Seleccionado contrato **{contract['pkey']}**. ¿Qué dato necesitas?", "state": CONTRACT_CONTEXT_STATE}

        if pa and pa.get("intent") in {"list_fact_docs", "modify_fact_doc_select"}:
            fdoc = {
                "pkey": int(chosen.get("pkey") or 0),
                "nivelcontrol": (chosen.get("raw") or {}).get("NIVELCONTROL"),
                "referencia": chosen.get("referencia") or "",
                "entidad": (chosen.get("raw") or {}).get("ENTIDAD"),
                "raw": chosen.get("raw") or {},
            }
            session["active_fact_doc"] = fdoc
            session["active_fact_line"] = None
            session["active_entity"] = None
            session["active_article"] = None
            session["active_contract"] = None
            session["active_service"] = None
            session["state"] = FACT_CONTEXT_STATE
            if pa.get("intent") == "modify_fact_doc_select":
                return await self._handle_modify_factura(
                    session,
                    pa.get("message") or "",
                    pa.get("entities") or {"pkey_factura": fdoc.get("pkey")},
                )
            return {"reply": f"Seleccionado documento **{fdoc['pkey']}**. ¿Qué necesitas?", "state": FACT_CONTEXT_STATE}

        if pa and pa.get("intent") == "list_contracts_pick_entity":
            session["last_resolved_entity"] = chosen
            return await self._handle_list_contracts(session, {"nombre_cliente": chosen.get("nombre")}, pa.get("message") or "")

        if pa and pa.get("intent") == "article_family_select":
            session.setdefault("flow_data", {})["familia"] = int(chosen.get("pkey") or 0)
            session.setdefault("flow_data", {})["familia_name"] = chosen.get("nombre")
            return await self._flow_article(session, "", {"intent": "unknown", "entities": {}})

        if pa and pa.get("intent") == "article_brand_select":
            session.setdefault("flow_data", {})["marca"] = int(chosen.get("pkey") or 0)
            session.setdefault("flow_data", {})["marca_name"] = chosen.get("nombre")
            return await self._flow_article(session, "", {"intent": "unknown", "entities": {}})

        session["last_resolved_entity"] = chosen
        session["active_entity"] = chosen
        session["active_article"] = None
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
        if pa and pa.get("intent") == "list_entities":
            session["state"] = "idle"
            return {"reply": f"Seleccionado: **{chosen['nombre']}** (ID {chosen.get('pkey')}). ¿Qué dato quieres consultar?", "state": "idle"}

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
                session["active_entity"] = res["data"]
                return {"reply": f"He localizado a **{res['data']['nombre']}**. ¿Qué quieres hacer con este cliente?", "state": ENTITY_CONTEXT_STATE}

        ctx_state = self._current_context_state(session)
        if ctx_state:
            return {"reply": "No estoy seguro de qué necesitas en este paso. Si quieres, dime el dato concreto del elemento activo.", "state": ctx_state}
        return {"reply": "No estoy seguro de qué necesitas. Puedo ayudarte con clientes, servicios, contratos, artículos o facturación.", "state": "idle"}

    async def _handle_last_service_followup(self, session: dict, msg_c: str) -> dict:
        svc = session.get("active_service") or {}
        sid = svc.get("pkey")
        if not sid:
            lor = session.get("last_operation_result") or {}
            sid = lor.get("identifier")
        if not sid:
            return {"reply": "No tengo un servicio reciente activo en esta conversación.", "state": SERVICE_CONTEXT_STATE}

        if any(k in msg_c for k in ["comprueba", "comprobar", "verifica", "verificar"]):
            r = await tool_registry.obtener_servicio.execute({"pkey": int(sid)})
            if r.get("success"):
                data = r.get("data") or {}
                session["active_service"] = {
                    "pkey": int(sid),
                    "fecha_hora_text": data.get("FECHA_INICIO") or data.get("FECHA") or (svc.get("fecha_hora_text") if isinstance(svc, dict) else None),
                    "raw": data,
                }
                session["last_operation_result"] = {
                    "domain": "service",
                    "operation": "verify",
                    "identifier": int(sid),
                    "verifiable": True,
                    "verified": True,
                    "reusable_summary": {"service_id": int(sid)},
                }
                return {"reply": f"✅ Servicio {sid} identificado y verificado por lectura.", "state": SERVICE_CONTEXT_STATE}
            return {"reply": f"❌ No he podido verificar por lectura el servicio {sid}: {r.get('error') or 'error de tool/API'}.", "state": SERVICE_CONTEXT_STATE}

        if any(k in msg_c for k in ["numero", "número", "id", "pkey", "se ha creado"]):
            return {"reply": f"El servicio creado es el **{sid}**.", "state": SERVICE_CONTEXT_STATE}

        if any(k in msg_c for k in ["fecha", "quedo", "quedó"]):
            fecha = (svc.get("fecha_hora_text") or "").strip()
            if fecha:
                return {"reply": f"Quedó para: **{fecha}**.", "state": SERVICE_CONTEXT_STATE}
            r = await tool_registry.obtener_servicio.execute({"pkey": int(sid)})
            if r.get("success"):
                data = r.get("data") or {}
                fecha_api = data.get("FECHA_INICIO") or data.get("FECHA") or "(sin fecha)"
                session["active_service"] = {"pkey": int(sid), "fecha_hora_text": fecha_api, "raw": data}
                return {"reply": f"La fecha del servicio {sid} es: **{fecha_api}**.", "state": SERVICE_CONTEXT_STATE}
            return {"reply": f"No he podido recuperar la fecha del servicio {sid}: {r.get('error') or 'error de lectura'}.", "state": SERVICE_CONTEXT_STATE}

        return {"reply": f"Servicio activo: {sid}. Puedo darte número, fecha o verificar creación.", "state": SERVICE_CONTEXT_STATE}

    async def _handle_domain_context_followup(self, session: dict, message: str, msg_c: str, intent: str, entities: dict) -> dict | None:
        """Consume follow-ups cortos cuando hay contexto de dominio sin flujo AWAITING activo."""
        state_u = str(session.get("state", "")).upper()

        if state_u == SERVICE_CONTEXT_STATE and self._looks_like_last_service_followup(session, msg_c):
            return await self._handle_last_service_followup(session, msg_c)

        if state_u == CONTRACT_CONTEXT_STATE:
            if any(k in msg_c for k in ["elige", "primero", "segundo", "tercero", "esa", "ese"]):
                out = await self._handle_list_contracts(session, entities, message)
                if out.get("state") == "idle":
                    out["state"] = CONTRACT_CONTEXT_STATE
                return out
            if any(k in msg_c for k in ["periodicidad", "referencia", "codigo", "código", "estado", "bloque"]):
                out = await self._handle_query_contract_field(session, message, entities)
                if out.get("state") == "idle":
                    out["state"] = CONTRACT_CONTEXT_STATE
                return out

        if state_u == ARTICLE_CONTEXT_STATE and any(k in msg_c for k in ["proveedor", "familia", "marca", "referencia", "estado", "descripcion", "descripción"]):
            out = await self._handle_query_article_field(session, message, entities)
            if out.get("state") == "idle":
                out["state"] = ARTICLE_CONTEXT_STATE
            return out

        if state_u == FACT_CONTEXT_STATE:
            if any(k in msg_c for k in ["abre", "documento", "factura", "id", "pkey"]) and re.search(r"\b\d{1,8}\b", msg_c):
                out = await self._handle_query_factura(session, entities, message)
                if out.get("state") == "idle":
                    out["state"] = FACT_CONTEXT_STATE
                return out
            if any(k in msg_c for k in ["total", "fecha", "referencia", "linea", "línea", "lineas", "líneas"]):
                out = await self._handle_query_factura_field_followup(session, msg_c)
                if out.get("state") == "idle":
                    out["state"] = FACT_CONTEXT_STATE
                return out

        if state_u == ENTITY_CONTEXT_STATE:
            inferred_field = self._infer_entity_field_from_text(msg_c)
            if intent == "consultar_campo" or inferred_field:
                inferred_entities = dict(entities or {})
                if inferred_field and not inferred_entities.get("campo"):
                    inferred_entities["campo"] = inferred_field
                out = await self._handle_query_field(session, inferred_entities, message)
                if out.get("state") == "idle":
                    out["state"] = ENTITY_CONTEXT_STATE
                return out

        return None

    async def _handle_query_factura_field_followup(self, session: dict, msg_c: str) -> dict:
        doc = session.get("active_fact_doc") or {}
        pkey = doc.get("pkey")
        if not pkey:
            return {"reply": "No tengo un documento de facturación activo. Indícame el ID del documento.", "state": FACT_CONTEXT_STATE}

        if any(k in msg_c for k in ["linea", "línea", "lineas", "líneas"]):
            return await self._handle_query_factura_lines(session, f"lineas documento {pkey}", {"pkey_factura": pkey})

        rb = await tool_registry.obtener_facturacion.execute({"pkey": int(pkey)})
        if not rb.get("found"):
            return {"reply": f"No he podido leer el documento {pkey} para ese dato.", "state": FACT_CONTEXT_STATE}

        raw = rb.get("data") or {}
        session["active_fact_doc"] = {
            "pkey": int(raw.get("PKEY") or pkey),
            "nivelcontrol": raw.get("NIVELCONTROL"),
            "referencia": raw.get("REFERENCIA", ""),
            "entidad": raw.get("ENTIDAD"),
            "raw": raw,
        }
        session["active_fact_line"] = None

        if "total" in msg_c:
            total = raw.get("TOTAL")
            if total is None:
                total = raw.get("IMPORTE_TOTAL")
            if total is None:
                total = raw.get("BASEIMPONIBLE")
            return {"reply": f"El total del documento {pkey} es: {total if total is not None else '-'}", "state": FACT_CONTEXT_STATE}
        if "fecha" in msg_c:
            return {"reply": f"La fecha del documento {pkey} es: {raw.get('FECHA', '-')}", "state": FACT_CONTEXT_STATE}
        if "referencia" in msg_c:
            return {"reply": f"La referencia del documento {pkey} es: {raw.get('REFERENCIA', '-')}", "state": FACT_CONTEXT_STATE}
        return {"reply": f"Documento activo {pkey}. Puedo darte total, fecha o líneas.", "state": FACT_CONTEXT_STATE}

    def _current_context_state(self, session: dict) -> str | None:
        st = str(session.get("state", "")).upper()
        if st in {ENTITY_CONTEXT_STATE, SERVICE_CONTEXT_STATE, CONTRACT_CONTEXT_STATE, ARTICLE_CONTEXT_STATE, FACT_CONTEXT_STATE}:
            return st
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # UTILS
    # ─────────────────────────────────────────────────────────────────────────
    def _infer_entity_field_from_text(self, msg_c: str) -> str | None:
        if any(k in msg_c for k in ["telefono", "teléfono", "movil", "móvil"]):
            return "telefono"
        if any(k in msg_c for k in ["email", "correo", "mail"]):
            return "email"
        if any(k in msg_c for k in ["direccion", "dirección", "domicilio"]):
            return "direccion"
        return None

    def _looks_like_last_service_followup(self, session: dict, msg_c: str) -> bool:
        if any(k in msg_c for k in ["borrar", "eliminar", "cancela", "cancelar", "modifica", "actualiza"]):
            return False
        has_active_service = bool(session.get("active_service"))
        lor = session.get("last_operation_result") or {}
        has_active_service = has_active_service or (lor.get("domain") == "service" and lor.get("identifier"))
        has_service_hint = any(
            k in msg_c
            for k in ["numero", "número", "pkey", "fecha", "quedo", "quedó", "comprueba", "verifica", "se ha creado"]
        )
        return bool(msg_c.strip()) and has_active_service and has_service_hint

    def _looks_like_entity_listing_query(self, intent: str, msg_c: str, entities: dict) -> bool:
        if any(k in msg_c for k in ["contrato", "contratos"]):
            return False
        if intent in ("query_entity", "consultar_campo", "modify_entity", "delete_entity"):
            return False
        if intent == "create_entity":
            has_create_signal = any(k in msg_c for k in ["crear", "crea", "alta", "dar de alta", "nuevo", "nueva"])
            if any(h in msg_c for h in LIST_QUERY_HINTS) and not has_create_signal:
                return True
            return False
        if entities.get("nombre_cliente") and any(h in msg_c for h in LIST_QUERY_HINTS):
            return True
        if "clientes" in msg_c and not any(k in msg_c for k in ["crear", "alta", "nuevo", "nueva"]):
            return True
        if "que hay" in msg_c and not any(k in msg_c for k in ["servicio", "contrato", "articulo", "artículo", "factura"]):
            return True
        return False

    def _extract_entity_listing_hint(self, message: str) -> str:
        msg_c = clean_text(message or "")
        for token in ["dime", "los", "las", "que", "hay", "clientes", "cliente", "de", "por", "favor", "busca", "buscar", "lista", "listar", "muestrame", "muéstrame"]:
            msg_c = re.sub(rf"\b{re.escape(token)}\b", " ", msg_c)
        msg_c = re.sub(r"\s+", " ", msg_c).strip()
        return msg_c

    def _extract_entity_name_hint_from_field_query(self, message: str, campo: str | None) -> str | None:
        msg_c = clean_text(message or "")
        if not msg_c:
            return None

        blacklist = {
            "dime", "el", "la", "los", "las", "del", "de", "cliente", "clientes", "su", "y", "que", "quiero",
            "telefono", "teléfono", "email", "correo", "direccion", "dirección", "dato", "por", "favor"
        }
        if campo:
            blacklist.add(clean_text(campo))

        tokens = [t for t in re.findall(r"\b\w+\b", msg_c) if t not in blacklist]
        if not tokens:
            return None
        return " ".join(tokens)

    def _clear_flow(self, session: dict, reply: str) -> dict:
        for k in [
            "flow_mode", "flow_data", "state", "pending_action", "ambiguous_options", "pending_delete",
            "pending_field", "pending_operario_candidate_name", "candidate", "last_prompt_type"
        ]:
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
        else:
            cp_city_inline = re.search(r"\b(\d{5})\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]{2,})\b", m)
            if cp_city_inline:
                out["cp"] = cp_city_inline.group(1).strip()
                if not out.get("poblacion"):
                    city = cp_city_inline.group(2).strip(" ,")
                    if city and city.lower() not in {"es", "la", "de", "en"}:
                        out["poblacion"] = city
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
        m = re.search(
            r"(?:operario|t[eé]cnico|asignar a)\s*[:=]?\s*(?:es\s+)?([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ._-]+?)(?=(?:[\.,;]|\s+debe\b|\s+para\b|\s+que\b|\s+al\s+cliente\b|\s+el\s+lunes\b|$))",
            message or "",
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(" .")
        return None

    def _extract_service_datetime_candidate(self, message: str, entities: dict) -> str | None:
        if entities.get("fecha"):
            return str(entities.get("fecha")).strip()
        m = re.search(
            r"\b((?:lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)(?:\s+a\s+las\s+\d{1,2}(?::\d{2})?)?)\b",
            message or "",
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
        return None

    def _extract_service_context_candidate(self, message: str) -> str | None:
        m = re.search(r"\b(en\s+su\s+domicilio|a\s+domicilio|en\s+domicilio)\b", message or "", flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _extract_service_task_candidate(self, message: str) -> str | None:
        txt = (message or "").strip()
        if not txt:
            return None
        patterns = [
            r"para\s+que\s+(.*?)(?=\s+al\s+cliente\b|\s+para\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ._-]+\b|\s+el\s+lunes\b|\s+el\s+martes\b|\s+a\s+las\b|$)",
            r"tarea\s+(?:de\s+)?(.*?)(?=\s+para\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ._-]+\b|\s+el\s+lunes\b|\s+a\s+las\b|$)",
        ]
        for p in patterns:
            m = re.search(p, txt, flags=re.IGNORECASE)
            if m:
                cand = m.group(1).strip(" .")
                if len(cand) >= 8:
                    return cand
        return None

    def _precheck_entity_create(self, d: dict) -> dict:
        if d.get("entity_type") and d.get("entity_type") not in {"CLIENTE", "PROVEEDOR", "ACREEDOR", "P_LABORAL", "SUCURSAL", "USUARIO", "PREENTIDAD"}:
            return {"ok": False, "reason": "tipo de entidad no permitido"}
        cif = str(d.get("cif") or "").strip()
        if cif and len(re.sub(r"[^A-Za-z0-9]", "", cif)) < 7:
            return {"ok": False, "reason": "CIF/NIF parece incompleto"}
        return {"ok": True}

    def _precheck_service_create(self, d: dict) -> dict:
        if not d.get("client_pk"):
            return {"ok": False, "reason": "cliente no resuelto"}
        if not d.get("operario_pk"):
            return {"ok": False, "reason": "operario no resuelto"}
        task = str(d.get("task") or "").strip()
        if len(task) < 8:
            return {"ok": False, "reason": "descripción de tarea insuficiente"}
        for key in ["tipo_contacto", "estado", "tipo_servicio", "nivelcontrol"]:
            if key in d:
                try:
                    val = int(d.get(key))
                except Exception:
                    return {"ok": False, "reason": f"{key} no numérico"}
                if val < 0:
                    return {"ok": False, "reason": f"{key} inválido"}
        return {"ok": True}

    def _extract_pending_field_value(self, message: str, analysis: dict, field: str) -> str | None:
        if field != "operario":
            return None
        e = (analysis or {}).get("entities", {})
        if e.get("descripcion"):
            return None
        if e.get("operario"):
            return str(e.get("operario")).strip()
        t = (message or "").strip()
        if not t:
            return None
        t_clean = clean_text(t)
        if t_clean in CONFIRM_WORDS or t_clean in CANCEL_WORDS:
            return None
        if looks_like_short_value(t, max_words=4):
            return t.strip(" .")
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
        has_field = any(k in msg_c for k in ["referencia", "codigo", "código", "periodicidad", "estado", "bloque"])
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey_contrato"))
        return has_action and has_domain and has_field and has_ref

    def _looks_like_contract_listing_query(self, intent: str, msg_c: str, entities: dict) -> bool:
        if intent in {"list_contracts"}:
            return True
        if intent in {"create_contract", "modify_contract", "delete_contract", "query_contract"}:
            return False
        has_list_hint = any(k in msg_c for k in ["dime los contratos", "contratos que hay", "listar contratos", "lista contratos", "busca contratos", "buscar contratos", "ver contratos"])
        has_create_signal = any(k in msg_c for k in ["crear", "crea", "alta", "nuevo", "nueva"])
        if has_list_hint and not has_create_signal:
            return True
        if "contratos" in msg_c and entities.get("nombre_cliente") and not has_create_signal:
            return True
        return False

    def _looks_like_factura_modification(self, msg_c: str, entities: dict, session: dict) -> bool:
        has_action = any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "])
        has_domain = any(k in msg_c for k in ["factura", "documento", "prefactura", "albaran", "albarán", "gasto"]) or bool(session.get("active_fact_doc"))
        has_field = any(k in msg_c for k in ["referencia", "observaciones", "fecha"])
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey_factura") or entities.get("pkey") or session.get("active_fact_doc"))
        return has_action and has_domain and has_field and has_ref

    def _looks_like_factura_listing_query(self, intent: str, msg_c: str, entities: dict) -> bool:
        if intent == "list_facturas":
            return True
        if intent in {"create_factura_compra", "create_gasto", "query_factura", "modify_factura", "delete_factura"}:
            return False
        has_list = any(k in msg_c for k in ["dime las facturas", "facturas que hay", "prefacturas que hay", "lista facturas", "listar facturas", "busca facturas", "ver facturas"])
        has_create = any(k in msg_c for k in ["crear", "crea", "alta", "nuevo", "nueva"])
        return has_list and not has_create

    def _looks_like_factura_lines_query(self, msg_c: str, entities: dict, session: dict) -> bool:
        has_line_hint = any(k in msg_c for k in ["lineas", "líneas", "linea", "línea", "detalle"])
        has_doc_hint = any(k in msg_c for k in ["factura", "documento", "prefactura", "albaran", "albarán", "gasto"]) or bool(session.get("active_fact_doc"))
        return has_line_hint and has_doc_hint

    def _looks_like_contract_field_query(self, intent: str, msg_c: str, entities: dict, session: dict) -> bool:
        if any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "]):
            return False
        if intent == "consultar_campo":
            if entities.get("pkey_contrato"):
                return True
            if session.get("active_contract") and any(k in msg_c for k in ["referencia", "codigo", "código", "periodicidad", "estado", "bloque"]):
                return True
        if intent == "query_contract" and any(k in msg_c for k in ["referencia", "codigo", "código", "periodicidad", "estado", "bloque"]):
            return True
        return False

    def _infer_contract_field_from_text(self, msg_c: str) -> str | None:
        if any(k in msg_c for k in ["referencia", "ref"]):
            return "REFERENCIA"
        if any(k in msg_c for k in ["codigo", "código"]):
            return "CODIGO_CONTRATO"
        if "periodicidad" in msg_c:
            return "PERIODICIDAD"
        if "estado" in msg_c:
            return "ESTADO"
        if "bloque" in msg_c:
            return "BLOQUE"
        return None

    def _get_contract_field_value(self, raw: dict, field: str) -> str:
        f = str(field or "").upper()
        return str(raw.get(f) if raw.get(f) is not None else "-")

    def _extract_contract_listing_hint(self, message: str) -> str:
        t = clean_text(message or "")
        for token in ["dime", "los", "las", "que", "hay", "contratos", "de", "por", "favor", "lista", "listar", "busca", "buscar", "ver"]:
            t = re.sub(rf"\b{re.escape(token)}\b", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def _extract_contract_client_hint(self, message: str) -> str | None:
        raw = (message or "").strip()
        if not raw:
            return None

        msg_c = clean_text(raw)
        msg_c = re.sub(r"^(?:si|sí|vale|ok|de acuerdo|perfecto|claro)\s*[,\-:]*\s*", "", msg_c)
        msg_c = re.sub(r"^(?:yo no soy\s+[a-záéíóúüñ\-\s]+,\s*)", "", msg_c)
        msg_c = re.sub(r"^(?:el cliente es|cliente|para el cliente)\s*", "", msg_c)
        msg_c = re.sub(r"\s+", " ", msg_c).strip(" ,.-")

        if not msg_c:
            return None
        if any(k in msg_c for k in ["contrato", "servicio", "factura", "articulo", "artículo"]):
            return None
        if msg_c in {"si", "sí", "vale", "ok", "confirmo"}:
            return None
        if len(msg_c) < 3:
            return None

        return msg_c

    def _looks_like_article_modification(self, msg_c: str, entities: dict, session: dict) -> bool:
        has_action = any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "])
        has_domain = any(k in msg_c for k in ["articulo", "artículo", "referencia", "producto"]) or bool(session.get("active_article"))
        has_field = any(
            k in msg_c
            for k in ["descripcion", "descripción", "referencia", "proveedor", "familia", "marca", "observaciones", "obs"]
        )
        has_ref = bool(re.search(r"\b\d{3,8}\b", msg_c)) or bool(entities.get("pkey") or entities.get("pkey_articulo") or session.get("active_article"))
        return has_action and has_domain and (has_field or has_ref)

    def _looks_like_article_field_query(self, intent: str, msg_c: str, entities: dict, session: dict) -> bool:
        if any(k in msg_c for k in ["modifica", "modificar", "actualiza", "actualizar", "cambia", "cambiar", "pon "]):
            return False
        if intent == "consultar_campo":
            if entities.get("descripcion") and any(k in msg_c for k in ["articulo", "artículo", "producto"]):
                return True
            if session.get("active_article") and not entities.get("nombre_cliente"):
                return any(k in msg_c for k in ["referencia", "proveedor", "familia", "marca", "estado", "descripcion", "descripción"])
        if session.get("active_article") and any(k in msg_c for k in ["referencia", "proveedor", "familia", "marca", "estado"]):
            return True
        return False

    def _infer_article_field_from_text(self, msg_c: str) -> str | None:
        if any(k in msg_c for k in ["referencia", "ref"]):
            return "REFERENCIA"
        if "proveedor" in msg_c:
            return "PROVEEDOR"
        if "familia" in msg_c:
            return "FAMILIA"
        if "marca" in msg_c:
            return "MARCA"
        if "estado" in msg_c:
            return "ESTADO"
        if any(k in msg_c for k in ["descripcion", "descripción", "nombre"]):
            return "DESCRIPCION"
        return None

    def _get_article_field_value(self, raw: dict, field: str) -> str:
        field = str(field or "").upper()
        if field == "PROVEEDOR":
            return str(raw.get("PROVEEDOR_DES") or raw.get("PROVEEDOR") or "-")
        if field == "FAMILIA":
            return str(raw.get("FAMILIA_DES") or raw.get("FAMILIA") or "-")
        if field == "MARCA":
            return str(raw.get("MARCA_DES") or raw.get("MARCA") or "-")
        return str(raw.get(field) or "-")

    async def _resolve_article_target(self, session: dict, message: str, entities: dict) -> dict:
        pkey = entities.get("pkey_articulo") or entities.get("pkey")
        if pkey:
            rb = await tool_registry.obtener_articulo.execute(int(pkey))
            if rb.get("found"):
                a = rb.get("data") or {}
                return {
                    "status": "RESOLVED",
                    "data": {
                        "pkey": int(a.get("PKEY") or pkey),
                        "descripcion": a.get("DESCRIPCION", "-"),
                        "referencia": a.get("REFERENCIA", "-"),
                        "raw": a,
                    },
                }

        if session.get("active_article"):
            return {"status": "RESOLVED", "data": session.get("active_article")}

        hint = entities.get("descripcion") or entities.get("referencia") or self._extract_article_hint(message)
        if not hint:
            return {"status": "NOT_FOUND"}

        rs = await tool_registry.listar_articulos.execute({"DESCRIPCION": f"%{hint}%"})
        data = rs.get("data", []) if rs.get("found") else []
        if not data:
            rs = await tool_registry.listar_articulos.execute({"REFERENCIA": f"%{hint}%"})
            data = rs.get("data", []) if rs.get("found") else []
        if not data:
            return {"status": "NOT_FOUND"}
        if len(data) == 1:
            a = data[0]
            return {
                "status": "RESOLVED",
                "data": {
                    "pkey": int(a.get("PKEY") or 0),
                    "descripcion": a.get("DESCRIPCION", "-"),
                    "referencia": a.get("REFERENCIA", "-"),
                    "raw": a,
                },
            }
        options = [
            {
                "pkey": int(a.get("PKEY") or 0),
                "nombre": a.get("DESCRIPCION", "-"),
                "referencia": a.get("REFERENCIA", "-"),
                "raw": a,
            }
            for a in data[:5]
        ]
        return {"status": "AMBIGUOUS", "options": options}

    def _extract_article_hint(self, message: str) -> str:
        t = clean_text(message or "")
        for token in ["articulo", "artículo", "producto", "modifica", "modificar", "actualiza", "actualizar", "de", "el", "la", "por", "favor", "dime", "consulta"]:
            t = re.sub(rf"\b{re.escape(token)}\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    async def _extract_article_updates(self, message: str, entities: dict) -> dict:
        updates = {}

        desc = entities.get("descripcion")
        if not desc:
            m_desc = re.search(r"(?:descripcion|descripción)\s*(?:a|es|=)?\s+(.+?)(?:\s+y\s+|$)", message or "", flags=re.IGNORECASE)
            if m_desc:
                desc = m_desc.group(1).strip(" .")
        if desc:
            updates["DESCRIPCION"] = str(desc).strip()

        ref = entities.get("referencia")
        if not ref:
            m_ref = re.search(r"(?:referencia|ref)\s*(?:a|es|=)?\s*([A-Za-z0-9._\-/]+)", message or "", flags=re.IGNORECASE)
            if m_ref:
                ref = m_ref.group(1).strip()
        if ref:
            updates["REFERENCIA"] = str(ref).strip()

        prov_name = self._extract_provider_candidate(message, entities)
        if prov_name:
            p_res = await resolver.resolve_entity(name=prov_name, allowed_types=["PROVEEDOR"])
            if p_res.get("status") == "RESOLVED":
                updates["PROVEEDOR"] = int(p_res["data"]["pkey"])

        fam = entities.get("familia")
        if fam is not None:
            fam_res = await self._resolve_article_catalog_id("FAMILIA", str(fam))
            if fam_res.get("status") == "RESOLVED":
                updates["FAMILIA"] = int(fam_res.get("id"))

        brand = entities.get("marca")
        if brand is not None:
            brand_res = await self._resolve_article_catalog_id("MARCA", str(brand))
            if brand_res.get("status") == "RESOLVED":
                updates["MARCA"] = int(brand_res.get("id"))

        obs = entities.get("observaciones")
        if obs:
            updates["OBSERVACIONES"] = str(obs).strip()
        return updates

    def _precheck_article_create(self, d: dict) -> dict:
        desc = str(d.get("descripcion") or "").strip()
        if len(desc) < 3:
            return {"ok": False, "reason": "descripción insuficiente"}
        for k in ["familia", "marca", "proveedor_pk"]:
            if d.get(k) is None:
                continue
            try:
                v = int(d.get(k))
            except Exception:
                return {"ok": False, "reason": f"{k} no numérico"}
            if v < 0:
                return {"ok": False, "reason": f"{k} inválido"}
        return {"ok": True}

    def _precheck_article_modify(self, updates: dict) -> dict:
        for k in ["FAMILIA", "MARCA", "PROVEEDOR"]:
            if k not in updates:
                continue
            try:
                v = int(updates.get(k))
            except Exception:
                return {"ok": False, "reason": f"{k} no numérico"}
            if v < 0:
                return {"ok": False, "reason": f"{k} inválido"}
        return {"ok": True}

    async def _resolve_article_catalog_id(self, kind: str, raw_value: str) -> dict:
        """Intenta resolver IDs de MARCA/FAMILIA a partir de texto usando listado de artículos existente."""
        value = str(raw_value or "").strip()
        if not value:
            return {"status": "NOT_FOUND"}
        if value.isdigit():
            return {"status": "RESOLVED", "id": int(value)}

        key = kind.upper()
        desc_key = f"{key}_DES"
        candidates = []

        for filtro in [{desc_key: f"%{value}%"}, {"DESCRIPCION": f"%{value}%"}]:
            rr = await tool_registry.listar_articulos.execute(filtro)
            if not rr.get("found"):
                continue
            for it in rr.get("data", []):
                cid = it.get(key)
                cdesc = it.get(desc_key) or ""
                if cid is None or not cdesc:
                    continue
                candidates.append({"pkey": int(cid), "nombre": str(cdesc)})

        uniq = {}
        for c in candidates:
            uniq[(c["pkey"], c["nombre"])] = c
        cands = list(uniq.values())
        if not cands:
            return {"status": "NOT_FOUND"}

        norm_v = clean_text(value)
        scored = []
        for c in cands:
            n = clean_text(c.get("nombre", ""))
            if not n:
                continue
            score = 1.0 if n == norm_v else (0.92 if norm_v in n else 0.0)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return {"status": "NOT_FOUND"}
        top = scored[0][1]
        ties = [x[1] for x in scored if x[0] == scored[0][0]][:5]
        if len(ties) > 1:
            return {"status": "AMBIGUOUS", "options": ties}
        return {"status": "RESOLVED", "id": int(top["pkey"]), "name": top.get("nombre")}

    def _verify_article_updates(self, article_data: dict, requested_updates: dict) -> tuple[bool, list[str]]:
        checks = []
        all_ok = True
        for k, v in requested_updates.items():
            current = article_data.get(k)
            if k in {"PROVEEDOR", "FAMILIA", "MARCA"}:
                try:
                    ok = int(current) == int(v)
                except Exception:
                    ok = False
            else:
                ok = str(current or "").strip().lower() == str(v or "").strip().lower()
            all_ok = all_ok and ok
            checks.append(f"{k}={'OK' if ok else 'KO'}")
        return all_ok, checks

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

        referencia = entities.get("referencia")
        if not referencia:
            m_ref = re.search(r"(?:referencia|ref)\s*(?:a|es|=)?\s*([A-Za-z0-9._\-/]+)", message, flags=re.IGNORECASE)
            if m_ref:
                referencia = m_ref.group(1).strip()
        if referencia:
            updates["REFERENCIA"] = str(referencia).strip()

        codigo = entities.get("codigo_contrato")
        if not codigo:
            m_cod = re.search(r"(?:codigo\s+contrato|código\s+contrato|codigo|código)\s*(?:a|es|=)?\s*([A-Za-z0-9._\-/]+)", message or "", flags=re.IGNORECASE)
            if m_cod:
                codigo = m_cod.group(1).strip()
        if codigo:
            updates["CODIGO_CONTRATO"] = str(codigo).strip()

        periodicidad = entities.get("periodicidad")
        if periodicidad is None:
            m_per = re.search(r"(?:periodicidad)\s*(?:a|es|=)?\s*(-?\d+)", clean_text(message or ""))
            if m_per:
                periodicidad = m_per.group(1)
        if periodicidad is not None:
            try:
                updates["PERIODICIDAD"] = int(periodicidad)
            except Exception:
                updates["PERIODICIDAD"] = periodicidad

        estado = entities.get("estado")
        if estado is None:
            m_est = re.search(r"(?:estado)\s*(?:a|es|=)?\s*(-?\d+)", clean_text(message or ""))
            if m_est:
                estado = m_est.group(1)
        if estado is not None:
            try:
                updates["ESTADO"] = int(estado)
            except Exception:
                updates["ESTADO"] = estado

        bloque = entities.get("bloque")
        if bloque is None:
            m_blo = re.search(r"(?:bloque)\s*(?:a|es|=)?\s*(-?\d+)", clean_text(message or ""))
            if m_blo:
                bloque = m_blo.group(1)
        if bloque is not None:
            try:
                updates["BLOQUE"] = int(bloque)
            except Exception:
                updates["BLOQUE"] = bloque

        return updates

    def _precheck_contract_modify_safe(self, updates: dict) -> dict:
        allowed = {"REFERENCIA", "CODIGO_CONTRATO", "PERIODICIDAD", "ESTADO", "BLOQUE"}
        disallowed = sorted([k for k in updates.keys() if k not in allowed])
        if disallowed:
            return {"ok": False, "reason": f"campos fuera de alcance C3: {', '.join(disallowed)}"}
        for key in ["PERIODICIDAD", "ESTADO", "BLOQUE"]:
            if key in updates:
                try:
                    int(updates[key])
                except Exception:
                    return {"ok": False, "reason": f"{key} no numérico"}
        for key in ["REFERENCIA", "CODIGO_CONTRATO"]:
            if key in updates and not str(updates[key]).strip():
                return {"ok": False, "reason": f"{key} vacío"}
        return {"ok": True}

    def _detect_contract_out_of_scope_request(self, message: str, entities: dict) -> list[str]:
        out = set()
        msg_c = clean_text(message or "")

        if entities.get("precio") is not None or "precio" in msg_c or "importe" in msg_c:
            out.add("PRECIO_UNITARIO")
        if entities.get("descripcion"):
            out.add("DESCRIPCION")
        if entities.get("observaciones"):
            out.add("OBSERVACIONES")

        struct_map = {
            "ENTIDAD": ["entidad"],
            "ENTIDAD_PAGADORA": ["entidad pagadora", "pagadora"],
            "ENTIDAD_ENDOSO": ["endoso"],
            "ENTIDAD_ENVIO": ["envio", "envío"],
            "ARTICULO": ["articulo", "artículo"],
            "PROYECTO": ["proyecto"],
            "MODO_ID_ENTIDAD": ["modo_id_entidad"],
            "MODO_ID_ARTICULO": ["modo_id_articulo"],
            "MODO_ID_PROYECTO": ["modo_id_proyecto"],
        }
        for key, hints in struct_map.items():
            if any(h in msg_c for h in hints):
                out.add(key)

        return sorted(list(out))

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

    def _precheck_facturacion_create(self, d: dict) -> dict:
        nc = d.get("nivelcontrol")
        try:
            nc_i = int(nc)
        except Exception:
            return {"ok": False, "reason": "NIVELCONTROL inválido"}

        if nc_i in FACT_NC_BLOCKED:
            return {"ok": False, "reason": f"NIVELCONTROL {nc_i} no permitido por documentación"}
        if nc_i not in FACT_NC_ALLOWED:
            return {"ok": False, "reason": f"NIVELCONTROL {nc_i} fuera de alcance C4"}
        if not d.get("client_pk"):
            return {"ok": False, "reason": "entidad no resuelta"}
        if not str(d.get("descripcion") or "").strip():
            return {"ok": False, "reason": "descripción vacía"}
        if not d.get("total"):
            return {"ok": False, "reason": "importe total ausente"}
        return {"ok": True}

    def _extract_fact_doc_updates(self, message: str, entities: dict) -> dict:
        updates = {}
        msg = message or ""

        referencia = entities.get("referencia")
        if not referencia:
            m_ref = re.search(r"(?:referencia|ref)\s*(?:a|es|=)?\s*([A-Za-z0-9._\-/]+)", msg, flags=re.IGNORECASE)
            if m_ref:
                referencia = m_ref.group(1).strip()
        if referencia:
            updates["REFERENCIA"] = str(referencia).strip()

        observaciones = entities.get("observaciones")
        if not observaciones:
            m_obs = re.search(r"(?:observaciones?|obs)\s*(?:a|es|=|:)?\s+(.+)$", msg, flags=re.IGNORECASE)
            if m_obs:
                observaciones = m_obs.group(1).strip()
        if observaciones:
            updates["OBSERVACIONES"] = str(observaciones).strip()

        fecha = entities.get("fecha")
        if fecha:
            updates["FECHA"] = str(fecha).strip()

        return updates

    def _precheck_facturacion_modify(self, doc: dict, updates: dict) -> dict:
        raw = doc.get("raw") or {}
        nc = raw.get("NIVELCONTROL", doc.get("nivelcontrol"))
        try:
            nc_i = int(nc)
        except Exception:
            return {"ok": False, "reason": "NIVELCONTROL del documento no válido"}

        if nc_i in FACT_NC_BLOCKED:
            return {"ok": False, "reason": f"NIVELCONTROL {nc_i} no permitido"}
        if nc_i not in FACT_NC_ALLOWED:
            return {"ok": False, "reason": f"NIVELCONTROL {nc_i} fuera de alcance C4"}

        allowed = {"REFERENCIA", "OBSERVACIONES", "FECHA"}
        disallowed = sorted([k for k in updates.keys() if k not in allowed])
        if disallowed:
            return {"ok": False, "reason": f"campos fuera de alcance: {', '.join(disallowed)}"}
        if "REFERENCIA" in updates and not str(updates.get("REFERENCIA") or "").strip():
            return {"ok": False, "reason": "REFERENCIA vacía"}
        return {"ok": True}

    def _verify_fact_doc_updates(self, fact_data: dict, requested_updates: dict) -> tuple[bool, list[str]]:
        checks = []
        all_ok = True
        for k, v in requested_updates.items():
            current = fact_data.get(k)
            ok = clean_text(str(current or "")) == clean_text(str(v or ""))
            checks.append(f"{k}={'OK' if ok else 'MISMATCH'}")
            all_ok = all_ok and ok
        return all_ok, checks

    async def _resolve_contract_target(self, session: dict, message: str, entities: dict) -> dict:
        pkey = self._extract_contract_pkey(message, entities)
        if pkey:
            r = await tool_registry.obtener_contrato.execute({"pkey": int(pkey)})
            if r.get("found"):
                c = r.get("data", {}) or {}
                return {
                    "status": "RESOLVED",
                    "data": {
                        "pkey": int(c.get("PKEY") or pkey),
                        "referencia": c.get("REFERENCIA", "-"),
                        "codigo_contrato": c.get("CODIGO_CONTRATO", "-"),
                        "raw": c,
                    },
                }

        if session.get("active_contract"):
            return {"status": "RESOLVED", "data": session.get("active_contract")}

        name = entities.get("nombre_cliente")
        if name:
            res = await resolver.resolve_entity(name=name)
            if res.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                return {"status": res.get("status"), "options": res.get("options", [])}
            if res.get("status") == "RESOLVED":
                rs = await tool_registry.listar_contratos.execute({"pkey_entidad": res["data"]["pkey"]})
                lista = rs.get("data", []) if rs.get("found") else []
                if not lista:
                    return {"status": "NOT_FOUND"}
                if len(lista) == 1:
                    c = lista[0]
                    return {
                        "status": "RESOLVED",
                        "data": {
                            "pkey": int(c.get("PKEY") or 0),
                            "referencia": c.get("REFERENCIA", "-"),
                            "codigo_contrato": c.get("CODIGO_CONTRATO", "-"),
                            "raw": c,
                        },
                    }
                opts = [
                    {
                        "pkey": int(c.get("PKEY") or 0),
                        "referencia": c.get("REFERENCIA", ""),
                        "codigo_contrato": c.get("CODIGO_CONTRATO", ""),
                        "nombre": c.get("DESCRIPCION", "-"),
                        "raw": c,
                    }
                    for c in lista[:5]
                ]
                return {"status": "AMBIGUOUS", "options": opts}
        return {"status": "NOT_FOUND"}

    async def _resolve_fact_doc_target(self, session: dict, message: str, entities: dict) -> dict:
        pkey = entities.get("pkey_factura") or entities.get("pkey")
        if pkey:
            r = await tool_registry.obtener_facturacion.execute({"pkey": int(pkey)})
            if r.get("found"):
                d = r.get("data") or {}
                return {
                    "status": "RESOLVED",
                    "data": {
                        "pkey": int(d.get("PKEY") or pkey),
                        "nivelcontrol": d.get("NIVELCONTROL"),
                        "referencia": d.get("REFERENCIA", ""),
                        "raw": d,
                    },
                }

        if session.get("active_fact_doc"):
            return {"status": "RESOLVED", "data": session.get("active_fact_doc")}

        name = entities.get("nombre_cliente")
        if name:
            res = await resolver.resolve_entity(name=name)
            if res.get("status") in ("AMBIGUOUS", "POSSIBLE_DUPLICATE"):
                return {"status": res.get("status"), "options": res.get("options", [])}
            if res.get("status") == "RESOLVED":
                rr = await tool_registry.listar_facturaciones.execute({"ENTIDAD": res["data"]["pkey"]})
                docs = rr.get("data", []) if rr.get("found") else []
                if not docs:
                    return {"status": "NOT_FOUND"}
                if len(docs) == 1:
                    d = docs[0]
                    return {
                        "status": "RESOLVED",
                        "data": {
                            "pkey": int(d.get("PKEY") or 0),
                            "nivelcontrol": d.get("NIVELCONTROL"),
                            "referencia": d.get("REFERENCIA", ""),
                            "raw": d,
                        },
                    }
                opts = [
                    {
                        "pkey": int(d.get("PKEY") or 0),
                        "referencia": d.get("REFERENCIA", ""),
                        "nombre": NC_LABELS.get(d.get("NIVELCONTROL", "?"), f"NC={d.get('NIVELCONTROL', '?')}"),
                        "raw": d,
                    }
                    for d in docs[:5]
                ]
                return {"status": "AMBIGUOUS", "options": opts}
        return {"status": "NOT_FOUND"}

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
