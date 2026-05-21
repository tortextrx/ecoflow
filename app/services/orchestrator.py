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
CANCEL_WORDS = {"no", "para", "cancela", "olvida", "nada", "atras", "descarta"}


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
        if intent in ("delete_entity", "delete_service", "delete_contract", "delete_factura"):
            return await self._initiate_delete(session, intent, entities)

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

        if not d.get("name"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": "¿A qué nombre damos el alta?", "state": "AWAITING_ENTITY_CONFIRM"}
        if not d.get("cif"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": f"¿Y el CIF de **{d['name']}**?", "state": "AWAITING_ENTITY_CONFIRM"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            p = {"DENCOM": d["name"], "CIF": d["cif"], "SUCURSAL": 1, "CLIENTE": 1, "ESTADO": 0, "OBSERVACIONES": d.get("obs", "Alta vía ecoFlow")}
            r = await tool_registry.crear_entidad.execute(p)
            if r.get("success"):
                session["last_resolved_entity"] = {"pkey": r.get("pkey"), "nombre": d["name"], "cif": d["cif"]}
                return self._clear_flow(session, f"✅ Alta completada (ID {r.get('pkey')})")
            return {"reply": f"❌ Error ERP: {r.get('error')}", "state": "idle"}

        session["state"] = "AWAITING_ENTITY_CONFIRM"
        obs_txt = f"\n- Obs: {d['obs']}" if d.get("obs") else ""
        return {"reply": f"📋 **Confirmación de Alta**\n- Cliente: **{d['name']}**\n- CIF: {d['cif']}{obs_txt}\n\n¿Lo grabo ya?", "state": "AWAITING_ENTITY_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: SERVICIOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_service(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "service"
        d = session["flow_data"]
        e = analysis.get("entities", {})

        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] == "AMBIGUOUS":
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

        if len(clean_text(d["task"])) < 8:
            d.pop("task", None)
            return {"reply": "La descripción es muy corta. ¿Puedes darme un poco más de detalle?", "state": "AWAITING_SERVICE_CONFIRM"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {"MODO_ID": 0, "CLIENTE": d["client_pk"], "CLIENTE_DELEGACION": 1, "ESTADO": 0, "SUCURSAL": "1", "NIVELCONTROL": 1, "SERVICIO_DESCRIPCION": d["task"], "FECHA_INICIO": get_now_iso()}
            r = await tool_registry.crear_servicio.execute(payload)
            if r.get("success"):
                return self._clear_flow(session, f"✅ Servicio {r['pkey']} creado para {d['client_name']}.")
            return {"reply": "❌ Error al grabar el servicio.", "state": "idle"}

        session["state"] = "AWAITING_SERVICE_CONFIRM"
        task_short = d['task'][:60] + "..." if len(d['task']) > 60 else d['task']
        return {"reply": f"📋 **Nuevo Servicio**\n- **Cliente**: {d['client_name']}\n- **Tarea**: {task_short}\n\n¿Grabo?", "state": "AWAITING_SERVICE_CONFIRM"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: CONTRATOS
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_contract(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "contract"
        d = session["flow_data"]
        e = analysis.get("entities", {})

        # Resolver cliente
        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] == "AMBIGUOUS":
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

        target_name = e.get("nombre_cliente") or d.get("client_name")
        if target_name and not d.get("client_pk"):
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                d["client_pk"], d["client_name"] = res["data"]["pkey"], res["data"]["nombre"]
                session["last_resolved_entity"] = res["data"]
            elif res["status"] == "AMBIGUOUS":
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
        if e.get("referencia"): d["referencia"] = e["referencia"]

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
            r = await tool_registry.grabar_facturacion.execute({"payload": payload})
            # grabar_facturacion tool usa payload directamente
            from app.connectors.facturacion import FacturacionConnector
            conn = FacturacionConnector()
            resp = await conn.grabar_facturacion(payload)
            if resp.get("mensaje") == "OK":
                return self._clear_flow(session, f"✅ {label} {resp.get('lista')} registrado para {d['client_name']}.")
            return {"reply": f"❌ Error ERP: {resp.get('lista')}", "state": "idle"}

        session["state"] = "AWAITING_FACTURA_COLLECT"
        return {"reply": f"📋 **{label}**\n- **Cliente**: {d['client_name']}\n- **Concepto**: {d['descripcion']}\n- **Importe**: {d['total']}€\n\n¿Grabo?", "state": "AWAITING_FACTURA_COLLECT"}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO: ARTÍCULOS (crear)
    # ─────────────────────────────────────────────────────────────────────────
    async def _flow_article(self, session: dict, message: str, analysis: dict) -> dict:
        if "flow_data" not in session: session["flow_data"] = {}
        d = session["flow_data"]
        e = analysis.get("entities", {})
        if e.get("descripcion"): d["descripcion"] = e["descripcion"]
        if e.get("referencia"): d["referencia"] = e["referencia"]

        if not d.get("descripcion"):
            session["state"] = "AWAITING_ARTICULO_COLLECT"
            return {"reply": "¿Cómo se llama o describe el artículo?", "state": "AWAITING_ARTICULO_COLLECT"}

        if analysis.get("intent") == "confirm" or clean_text(message) in CONFIRM_WORDS:
            payload = {"DESCRIPCION": d["descripcion"], "REFERENCIA": d.get("referencia", "")}
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
    async def _initiate_delete(self, session: dict, intent: str, entities: dict) -> dict:
        """Primera confirmación de borrado — instancia el estado de espera."""
        pkey = entities.get("pkey_servicio") or entities.get("pkey_contrato") or entities.get("pkey_factura")
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

        return {
            "reply": f"⚠️ Estás a punto de **eliminar** el {kind} ID `{pkey}`. Esta acción es **irreversible**.\n\nEscribe **CONFIRMO** para proceder.",
            "state": "AWAITING_DELETE_CONFIRM"
        }

    async def _handle_delete_confirm(self, session: dict, message: str, msg_c: str, intent: str) -> dict:
        """Segunda confirmación estricta de borrado."""
        pd = session.pop("pending_delete", {})
        if not pd:
            session["state"] = "idle"
            return {"reply": "No había ninguna operación de borrado pendiente.", "state": "idle"}

        # Exige "confirmo" literal para operaciones destructivas
        if "confirmo" not in message.lower():
            session["state"] = "idle"
            return {"reply": "Borrado cancelado. No has escrito CONFIRMO.", "state": "idle"}

        kind, pkey, intent_name = pd["kind"], pd["pkey"], pd["intent"]

        tool_map = {
            "delete_service": tool_registry.borrar_servicio,
            "delete_contract": tool_registry.borrar_contrato,
            "delete_factura": tool_registry.borrar_facturacion,
        }
        tool = tool_map.get(intent_name)
        if tool:
            r = await tool.execute({"pkey": pkey})
            session["state"] = "idle"
            if r.get("success"): return {"reply": f"✅ {kind.capitalize()} `{pkey}` eliminado.", "state": "idle"}
            return {"reply": f"❌ Error al eliminar: {r.get('error')}", "state": "idle"}

        session["state"] = "idle"
        return {"reply": "No tengo forma de ejecutar ese borrado.", "state": "idle"}

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
        if res["status"] == "AMBIGUOUS":
            session.update({"state": "AWAITING_DISAMBIGUATION", "ambiguous_options": res.get("options", [])})
            opts = "\n".join([f"{i+1}. {x.get('nombre')} (CIF: {x.get('cif')})" for i, x in enumerate(session["ambiguous_options"])])
            return {"reply": f"Hay varias coincidencias:\n{opts}", "state": "AWAITING_DISAMBIGUATION"}
        return {"reply": "No he encontrado ninguna entidad con esos datos.", "state": "idle"}

    async def _handle_query_contract(self, session: dict, entities: dict) -> dict:
        pkey = entities.get("pkey_contrato")
        if pkey:
            r = await tool_registry.obtener_contrato.execute({"pkey": pkey})
            if r.get("found"):
                c = r["data"]
                return {"reply": f"📄 **Contrato {pkey}**\n- Cliente: {c.get('ENTIDAD_DES', '-')}\n- Descripción: {c.get('DESCRIPCION', '-')}\n- Precio: {c.get('PRECIO_UNITARIO', '-')}€\n- Estado: {c.get('ESTADO', '-')}", "state": "idle"}
        return {"reply": f"No encuentro el contrato `{pkey}`.", "state": "idle"}

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
        res_s = await tool_registry.obtener_servicio.execute({"pkey": pkey})
        if not res_s.get("success"):
            return {"reply": f"No encuentro el servicio con ID {pkey}.", "state": "idle"}
        op = res_s.get("data", {}).get("OPERARIO") or -1
        payload = {"PKEY": pkey, "MODO_ID": 0, "DESCRIPCION": nota, "OBSERVACIONES": "", "OPERARIO": op, "FECHA": get_now_iso()}
        await tool_registry.grabar_historico.execute(payload)
        return {"reply": f"✅ Nota añadida al historial del servicio {pkey}.", "state": "idle"}

    async def _handle_query_history(self, session: dict, pkey: int) -> dict:
        res = await tool_registry.obtener_historico_servicio.execute({"pkey": pkey})
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
            elif res["status"] == "AMBIGUOUS":
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


orchestrator = UnifiedOrchestrator()
