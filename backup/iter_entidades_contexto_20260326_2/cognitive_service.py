import json, logging, httpx, contextvars
from pydantic import ValidationError
from app.core.config import settings
from app.models.schemas.cognitive_contracts import CognitiveIntentOutput
from app.services.normalizers import classify_short_user_act

logger = logging.getLogger("ecoflow")
ecoflow_trace_ctx = contextvars.ContextVar("ecoflow_trace_id", default="no-trace")

class CognitiveService:
    """Motor de Intenciones v3.0 (Multi-Domain ERP).
    Detecta intenciones para todos los módulos: entidades, artículos, servicios, contratos y facturación.
    """
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def _safe_unknown(self) -> dict:
        return CognitiveIntentOutput(intent="unknown", entities={}).model_dump()

    def _validate_contract(self, candidate: dict, trace_id: str) -> dict:
        try:
            return CognitiveIntentOutput.model_validate(candidate or {}).model_dump()
        except ValidationError as ve:
            logger.warning({"action": "llm_contract_invalid", "trace_id": trace_id, "layer": "cognitive", "error": str(ve)})
            return self._safe_unknown()

    def _extract_structured(self, response_json: dict) -> dict:
        choice = (response_json.get("choices") or [{}])[0] if isinstance(response_json, dict) else {}
        message = choice.get("message") or {}

        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            fn = (tool_calls[0] or {}).get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                parsed = json.loads(args_raw)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        content = message.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    async def parse_intent(self, text: str, context: str = "") -> dict:
        system_prompt = """
        Eres el Clasificador de Intenciones de ecoFlow, un asistente ERP.
        Tu trabajo es traducir lenguaje natural a comandos estructurados JSON.
        
        MÓDULOS Y OPERACIONES DISPONIBLES (use SOLO estos, no inventes):
        
        ENTIDADES:
        - create_entity    : Dar de alta cliente/proveedor/acreedor.
        - query_entity     : Buscar o consultar datos de una entidad.
        - consultar_campo  : Pedir un campo específico (teléfono, email, dirección).
        - modify_entity    : Modificar datos de entidad (email, teléfono, dirección, observaciones).
        - delete_entity    : Borrar entidad. RIESGO ALTO.
        
        SERVICIOS:
        - open_task        : Crear servicio/tarea para un cliente.
        - query_history    : Ver historial de actuaciones de un servicio (por PKEY).
        - add_history      : Añadir nota/actuación al historial de un servicio.
        - delete_service   : Borrar servicio. RIESGO ALTO.
        
        ARTÍCULOS:
        - query_article    : Buscar artículo por descripción o referencia.
        - create_article   : Dar de alta un artículo nuevo.
        
        CONTRATOS:
        - create_contract  : Crear un contrato para un cliente.
        - modify_contract  : Modificar un contrato existente por PKEY (precio, referencia, descripción, observaciones).
        - query_contract   : Consultar un contrato por PKEY o cliente.
        - list_contracts   : Listar contratos de un cliente.
        - delete_contract  : Borrar un contrato. RIESGO ALTO.
        
        FACTURACIÓN (⚠️ Restricciones reales de la API):
        - query_factura    : Consultar documento de facturación por PKEY.
        - list_facturas    : Buscar documentos de facturación filtrados.
        - create_presupuesto_compra : NC=1. Presupuesto de compra.
        - create_pedido_compra      : NC=2. Pedido de compra.
        - create_albaran_compra     : NC=4. Albarán de compra.
        - create_factura_compra     : NC=5. Factura de compra.
        - create_gasto              : NC=6. Factura de gasto (documento de gasto libre).
        - create_presupuesto_venta  : NC=10. Presupuesto de venta.
        - create_pedido_venta       : NC=11. Pedido de venta.
        - create_albaran_venta      : NC=12. Albarán de venta.
        - create_prefactura         : NC=17. Prefactura de venta (NO factura directa).
        - delete_factura            : Borrar documento. RIESGO ALTO. NO permite borrar NC=13 ni NC=20.

        CONVERSACION GENERAL:
        - confirm          : Usuario confirma ("si", "venga", "adelante", "ok", "dale").
        - cancel           : Usuario cancela ("no", "para", "cancela", "olvídalo").
        - unknown          : Nada de lo anterior encaja.
        
        ENTIDADES EXTRAÍDAS (entities):
        - nombre_cliente   : Nombre comercial del cliente/empresa.
        - tipo_entidad     : cliente, proveedor, acreedor, personal laboral, sucursal, usuario del sistema.
        - cif              : CIF o NIF del cliente.
        - direccion        : Dirección postal.
        - poblacion        : Población / ciudad.
        - provincia        : Provincia.
        - cp               : Código postal.
        - telefono         : Teléfono.
        - email            : Email.
        - pkey_servicio    : ID de servicio (5 dígitos normalmente).
        - pkey_contrato    : ID de contrato.
        - pkey_factura     : ID de factura/documento.
        - descripcion      : Descripción del trabajo, artículo o contrato.
        - operario         : Nombre o referencia del operario.
        - nombre_proveedor : Nombre del proveedor para compras/artículos.
        - familia          : ID de familia de artículo si se indica.
        - campo            : Campo a consultar (telefono, email, direccion).
        - referencia       : Referencia del contrato, presupuesto u artículo.
        - precio           : Precio unitario.
        - total            : Importe total.
        - fecha            : Fecha específica.
        - observaciones    : Observaciones o notas.
        
        REGLAS:
        - Responde SIEMPRE en JSON puro con este esquema mínimo:
          {
            "intent": "X",
            "entities": {"campo": "valor"},
            "pending_field_guess": "operario|cliente|descripcion|cif|none",
            "confirm_signal": true|false,
            "deny_signal": true|false,
            "confidence_hint": "high|medium|low"
          }
        - NIF y CIF son lo mismo a efectos del sistema, mapea ambos a "cif".
        - Si el usuario dice "menudo coñazo", "venga va", "tira", "hazlo" → intent=confirm si hay flujo activo.
        - Si hay ambigüedad entre intent, elige el más probable dado el contexto.
        """

        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CONTEXTO: {context}\nMENSAJE: {text}"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "emit_intent",
                        "description": "Emitir intención y entidades ERP en formato estructurado",
                        "parameters": CognitiveIntentOutput.model_json_schema(),
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "emit_intent"}},
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        trace_id = ecoflow_trace_ctx.get()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, headers=headers, timeout=12.0)
                resp.raise_for_status()
                raw = resp.json()
                parsed = self._validate_contract(self._extract_structured(raw), trace_id)

                short_act = classify_short_user_act(text or "")
                if short_act == "confirm":
                    parsed["confirm_signal"] = True
                    if parsed.get("intent") in ("unknown", ""):
                        parsed["intent"] = "confirm"
                elif short_act in ("deny", "cancel"):
                    parsed["deny_signal"] = True

                # Revalidación final tras heurísticas cortas para garantizar contrato.
                return self._validate_contract(parsed, trace_id)
        except httpx.TimeoutException as te:
            logger.error({"action": "llm_timeout", "trace_id": trace_id, "layer": "cognitive", "error": str(te)})
            fallback = self._safe_unknown()
            fallback["error"] = "timeout"
            return fallback
        except Exception as e:
            logger.error({"action": "llm_error", "trace_id": trace_id, "layer": "cognitive", "error": str(e)}, exc_info=True)
            fallback = self._safe_unknown()
            fallback["error"] = "system_error"
            return fallback

cognitive_service = CognitiveService()
