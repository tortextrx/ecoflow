import json, logging, httpx
from app.core.config import settings

logger = logging.getLogger("ecoflow")

class CognitiveService:
    """Motor de Intenciones v3.0 (Multi-Domain ERP).
    Detecta intenciones para todos los módulos: entidades, artículos, servicios, contratos y facturación.
    """
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def parse_intent(self, text: str, context: str = "") -> dict:
        system_prompt = """
        Eres el Clasificador de Intenciones de ecoFlow, un asistente ERP.
        Tu trabajo es traducir lenguaje natural a comandos estructurados JSON.
        
        MÓDULOS Y OPERACIONES DISPONIBLES (use SOLO estos, no inventes):
        
        ENTIDADES:
        - create_entity    : Dar de alta cliente/proveedor/acreedor.
        - query_entity     : Buscar o consultar datos de una entidad.
        - consultar_campo  : Pedir un campo específico (teléfono, email, dirección).
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
        - cif              : CIF o NIF del cliente.
        - pkey_servicio    : ID de servicio (5 dígitos normalmente).
        - pkey_contrato    : ID de contrato.
        - pkey_factura     : ID de factura/documento.
        - descripcion      : Descripción del trabajo, artículo o contrato.
        - campo            : Campo a consultar (telefono, email, direccion).
        - referencia       : Referencia del contrato, presupuesto u artículo.
        - precio           : Precio unitario.
        - total            : Importe total.
        - fecha            : Fecha específica.
        - observaciones    : Observaciones o notas.
        
        REGLAS:
        - Responde SIEMPRE en JSON puro: {"intent": "X", "entities": {"campo": "valor"}}
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
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, headers=headers, timeout=10)
                return json.loads(resp.json()["choices"][0]["message"]["content"])
        except Exception:
            return {"intent": "unknown", "entities": {}}

cognitive_service = CognitiveService()
