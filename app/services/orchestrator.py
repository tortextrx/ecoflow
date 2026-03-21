import logging, json, unicodedata, re
from datetime import datetime
from app.services.cognitive_service import cognitive_service
from app.services.resolver import resolver
from app.services.tools.registry import tool_registry

logger = logging.getLogger("ecoflow")

def clean_text(text: str) -> str:
    if not text: return ""
    text = text.lower().strip()
    normalized = unicodedata.normalize('NFD', text)
    return "".join(c for c in normalized if unicodedata.category(c) != 'Mn')

def get_now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

class Orchestrator:
    async def dispatch(self, session: dict, message: str, file_bytes=None, filename=None) -> dict:
        if file_bytes and filename:
            return await self._handle_multimodal(session, file_bytes, filename)

        st = session.get("state", "idle")
        # Pasamos el estado al cerebro para mejor extraccion
        analysis = await cognitive_service.parse_intent(message, f"Estado: {st}")
        intent = str(analysis.get("intent", ""))
        entities = analysis.get("entities", {})
        msg_c = clean_text(message)
        
        # 1. PRIORIDAD ABSOLUTA: FLUJOS EN CURSO (Sticky)
        if st == "AWAITING_ENTITY_CONFIRM" or session.get("flow_mode") == "entity":
            return await self._flow_entity(session, message, analysis)
        if st == "AWAITING_SERVICE_CONFIRM" or session.get("flow_mode") == "service":
            return await self._flow_service(session, message, analysis)
        if st == "AWAITING_EXPENSE_CONFIRM" or session.get("flow_mode") == "expense":
            return await self._flow_expense(session, message, analysis)

        # 2. CONSULTA DE CAMPOS (Feature v11.0)
        if intent == "consultar_campo":
            campo = entities.get("campo")
            target_name = entities.get("nombre_cliente")
            
            # Paso 1: Resolver entidad si se indica nombre, sino usar last_resolved
            last = session.get("last_resolved_entity")
            if target_name:
                res = await resolver.resolve_entity(name=target_name)
                if res["status"] == "RESOLVED":
                    entidad = res["data"]
                    session["last_resolved_entity"] = entidad
                else:
                    return {"reply": f"No encuentro a {target_name} para darte su {campo}.", "state": "idle"}
            elif last:
                entidad = last
            else:
                return {"reply": "¿De qué cliente quieres saber el/la " + (campo or "dato") + "?", "state": "idle"}
            
            # Paso 2: Obtener campo
            if not campo: return {"reply": f"¿Qué dato quieres saber de {entidad['nombre']}? (dirección, teléfono, email)", "state": "idle"}
            
            valor = await resolver.obtener_campo(entidad["pkey"], campo)
            nombre_label = entidad["nombre"]
            return {"reply": f"El/La {campo} de {nombre_label} es: {valor}", "state": "idle"}

        # 3. DETECCION PROACTIVA POR PKEY (Solo si no hay flujo activo)
        found_pkey = None
        if not re.search(r'[a-zA-Z]', message) and len(message.strip()) <= 7:
            pkey_m = re.search(r'\b(\d{5})\b', message)
            if pkey_m: found_pkey = int(pkey_m.group(1))
        
        if not found_pkey: found_pkey = entities.get("pkey_servicio")

        if found_pkey:
            is_history_intent = intent in ["query_history", "add_history"]
            is_history_keyword = any(k in msg_c for k in ["historia", "actuacio", "nota", "ver", "dime"])
            if is_history_intent or is_history_keyword:
                if any(k in msg_c for k in ["meter", "pon", "graba", "linea"]) or intent == "add_history":
                    return await self._handle_add_history(session, found_pkey, entities.get("descripcion") or message)
                return await self._handle_query_history(session, found_pkey)

        # 4. LANZAMIENTO DE NUEVOS FLUJOS
        if intent == "create_entity" or "alta" in msg_c:
            session["flow_mode"] = "entity"; session["flow_data"] = {}
            return await self._flow_entity(session, message, analysis)
        if intent == "open_task" or any(k in msg_c for k in ["servicio", "tarea"]):
            session["flow_mode"] = "service"; session["flow_data"] = {}
            return await self._flow_service(session, message, analysis)

        return await self._process_general(session, analysis, message)

    async def _flow_service(self, session: dict, message: str, analysis: dict) -> dict:
        new_data = analysis.get("entities", {})
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "service"
        if new_data.get("nombre_cliente"): new_data["nombre"] = new_data["nombre_cliente"]
        for k, v in new_data.items():
            if v: session["flow_data"][k] = v
        d = session["flow_data"]
        
        if not d.get("_nombre_entidad") and (d.get("nombre") or d.get("nombre_cliente")):
            res = await resolver.resolve_entity(name=d.get("nombre") or d.get("nombre_cliente"))
            if res["status"]=="RESOLVED": 
                d.update({"_pkey_entidad":res["data"]["pkey"], "_nombre_entidad":res["data"]["nombre"]})
                session["last_resolved_entity"] = res["data"]
        
        if not d.get("_nombre_entidad"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": "¿Para qué cliente es el servicio?", "state": "AWAITING_SERVICE_CONFIRM"}
        if not d.get("descripcion"):
            session["state"] = "AWAITING_SERVICE_CONFIRM"
            return {"reply": f"¿Qué trabajo hacemos para **{d['_nombre_entidad']}**?", "state": "AWAITING_SERVICE_CONFIRM"}

        if analysis.get("intent") == "confirm" or clean_text(message) in ["si", "venga", "adelante", "ok"]:
            payload = {"MODO_ID": 0, "CLIENTE": d["_pkey_entidad"], "CLIENTE_DELEGACION": 1, "ESTADO": 0, "SUCURSAL": "1", "NIVELCONTROL": 1, "TIPOCONTACTO": 1, "TIPO_SERVICIO": 1, "SERVICIO_DESCRIPCION": d["descripcion"], "FECHA_INICIO": get_now_iso()}
            r = await tool_registry.crear_servicio.execute(payload)
            return self._clear_flow(session, f"✅ Creado servicio {r['pkey']} para {d['_nombre_entidad']}.") if r.get("success") else {"reply": "Error ERP.", "state": "idle"}
        
        session["state"] = "AWAITING_SERVICE_CONFIRM"
        return {"reply": f"Servicio para **{d['_nombre_entidad']}**: {d['descripcion']}. ¿Grabo?", "state": "AWAITING_SERVICE_CONFIRM"}

    async def _flow_entity(self, session: dict, message: str, analysis: dict) -> dict:
        new_data = analysis.get("entities", {})
        if "flow_data" not in session: session["flow_data"] = {}; session["flow_mode"] = "entity"
        if new_data.get("nombre_cliente"): new_data["nombre"] = new_data["nombre_cliente"]
        for k, v in new_data.items():
            if v: session["flow_data"][k] = v
        d = session["flow_data"]
        
        if not d.get("nombre"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": "¿A qué nombre damos el alta?", "state": "AWAITING_ENTITY_CONFIRM"}
        if not d.get("cif"):
            session["state"] = "AWAITING_ENTITY_CONFIRM"
            return {"reply": f"¿Y el CIF de **{d['nombre']}**?", "state": "AWAITING_ENTITY_CONFIRM"}
        
        if analysis.get("intent") == "confirm" or clean_text(message) in ["si", "ok", "adelante", "graba"]:
            p = {"DENCOM": d["nombre"], "CIF": d["cif"], "SUCURSAL": 1, "CLIENTE": 1, "ESTADO": 0}
            r = await tool_registry.crear_entidad.execute(p)
            if r.get("success"):
                session["last_resolved_entity"] = {"pkey": r.get("pkey"), "nombre": d["nombre"]}
                return self._clear_flow(session, f"✅ Alta Realizada (ID {r.get('pkey')})")
            return {"reply": "Error ERP.", "state": "idle"}
        
        session["state"] = "AWAITING_ENTITY_CONFIRM"
        return {"reply": f"Ficha Cliente: **{d['nombre']}** (CIF {d['cif']}). ¿Grabo?", "state": "AWAITING_ENTITY_CONFIRM"}

    async def _handle_add_history(self, session: dict, pkey: int, nota: str) -> dict:
        res_s = await tool_registry.obtener_servicio.execute({"pkey": pkey})
        if not res_s.get("success"): return {"reply": f"Error al leer servicio {pkey}.", "state": "idle"}
        op = res_s.get("data", {}).get("OPERARIO") or -1
        payload = {"PKEY": pkey, "MODO_ID": 0, "DESCRIPCION": nota, "OBSERVACIONES": "", "OPERARIO": op, "FECHA": get_now_iso()}
        await tool_registry.grabar_historico.execute(payload)
        return {"reply": f"✅ Historial grabado en {pkey}.", "state": "idle"}

    async def _handle_query_history(self, session: dict, pkey: int) -> dict:
        res = await tool_registry.obtener_historico_servicio.execute({"pkey": pkey})
        if not res.get("success") or not res.get("found"): return {"reply": f"Sin notas en {pkey}.", "state": "idle"}
        reply = [f"📋 Historial {pkey}:"]
        for it in res.get("data", []): reply.append(f"- {it.get('TEXTO_HISTORIAL')}")
        return {"reply": "\n".join(reply), "state": "idle"}

    async def _process_general(self, session: dict, analysis: dict, message: str) -> dict:
        # Si no hay intencion clara pero hay un nombre de cliente, intentamos resolver y mostrar ficha
        target_name = analysis.get("entities", {}).get("nombre_cliente")
        if target_name:
            res = await resolver.resolve_entity(name=target_name)
            if res["status"] == "RESOLVED":
                entidad = res["data"]
                session["last_resolved_entity"] = entidad
                return {"reply": f"He encontrado a **{entidad['nombre']}** (ID {entidad['pkey']}). ¿Qué quieres consultar?", "state": "idle"}
        
        return {"reply": "Dime qué gestión hacemos.", "state": "idle"}

    async def _handle_multimodal(self, session: dict, file_bytes, filename) -> dict:
        data = await tool_registry.extractor.extract(file_bytes, filename)
        if not data or not data.get("total"):
            return {"reply": "No he podido extraer datos válidos del documento.", "state": "idle"}
        
        # Limpiar datos para el flujo
        session["flow_mode"] = "expense"
        def parse_float(v):
            if not v: return 0.0
            if isinstance(v, (int, float)): return float(v)
            return float(str(v).replace(",", "."))

        session["flow_data"] = {
            "cif": data.get("cif", ""),
            "fecha": data.get("fecha", ""),
            "total": parse_float(data.get("total", 0.0)),
            "base": parse_float(data.get("base") or 0.0),
            "referencia": data.get("referencia", ""),
            "descripcion": data.get("descripcion", ""),
            "proveedor_nombre": data.get("proveedor", "Desconocido")
        }
        session["state"] = "AWAITING_EXPENSE_CONFIRM"
        
        summary = (
            f"📄 **Datos extraídos:**\n"
            f"- Proveedor: {session['flow_data']['proveedor_nombre']}\n"
            f"- CIF: {session['flow_data']['cif']}\n"
            f"- Total: **{session['flow_data']['total']}€**\n"
            f"- Fecha: {session['flow_data']['fecha']}\n\n"
            f"¿Quieres que registre este gasto en ecoSoft?"
        )
        return {"reply": summary, "state": "AWAITING_EXPENSE_CONFIRM"}

    async def _flow_expense(self, session: dict, message: str, analysis: dict) -> dict:
        d = session.get("flow_data", {})
        msg_c = clean_text(message)
        
        if analysis.get("intent") == "confirm" or msg_c in ["si", "ok", "adelante", "graba", "venga"]:
            # 1. Asegurar existencia de la entidad (Acreedor)
            cif = d.get("cif")
            nombre = d.get("proveedor_nombre")
            pkey_entidad = 0
            
            res_ent = await tool_registry.buscar_entidad.execute(cif=cif, dencom=nombre)
            if res_ent.get("found"):
                pkey_entidad = int(res_ent.get("pkey"))
            else:
                # Crear acreedor si no existe
                from app.models.schemas.domain import DomainCommand
                from uuid import uuid4
                create_cmd = DomainCommand(
                    intent_name="crear_entidad",
                    operation_id=uuid4(),
                    fields={
                        "DENCOM": nombre,
                        "CIF": cif,
                        "TIPO_ENTIDAD": "ACREEDOR",
                        "OBSERVACIONES": "Creado automáticamente vía ecoFlow (Gasto)"
                    }
                )
                from app.mappers.entidades_mapper import EntidadesMapper
                mapper_ent = EntidadesMapper()
                payload_ent = mapper_ent.build(create_cmd)
                res_create = await tool_registry.crear_entidad.execute(payload_ent)
                if res_create.get("success"):
                    pkey_entidad = int(res_create.get("pkey"))
                    logger.info(f"Creado acreedor {nombre} con PKEY {pkey_entidad}")
                else:
                    logger.warning(f"No se pudo crear acreedor {nombre}: {res_create.get('error')}")

            # 2. Ejecutar registro de gasto
            r = await tool_registry.registrar_gasto.execute(
                cif=cif,
                pkey_entidad=pkey_entidad,
                fecha=d.get("fecha"),
                total=d.get("total"),
                base=d.get("base"),
                referencia=d.get("referencia"),
                descripcion=d.get("descripcion") or f"Gasto {nombre}"
            )
            
            if r.get("success"):
                return self._clear_flow(session, f"✅ Gasto registrado correctamente (Documento ID {r.get('pkey')})")
            else:
                return self._clear_flow(session, f"❌ Error al registrar en el ERP: {r.get('error')}")

        
        if analysis.get("intent") == "cancel" or msg_c in ["no", "cancela", "nada", "descarta"]:
            return self._clear_flow(session, "Gasto descartado.")
            
        return {"reply": f"¿Registro el gasto de **{d.get('total')}€** de {d.get('proveedor_nombre')}? (si/no)", "state": "AWAITING_EXPENSE_CONFIRM"}

    def _clear_flow(self, session: dict, reply: str) -> dict:
        for k in ["flow_mode", "flow_data", "state"]: session.pop(k, None)
        return {"reply": reply, "state": "idle"}

orchestrator = Orchestrator()
