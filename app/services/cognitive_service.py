import json, logging, httpx
from app.core.config import settings

logger = logging.getLogger("ecoflow")

class CognitiveService:
    """Motor de Intenciones v2.4 (Contextual).
    Reestablece el contexto para evitar confusiones entre CIFs y PKEYs.
    Añade capacidad de consulta de campos de entidad.
    """
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def parse_intent(self, text: str, context: str = "") -> dict:
        system_prompt = """
        Eres el Cerebro de ecoFlow. Traduces lenguaje natural a comandos ERP.

        INTENCIONES (intent):
        - create_entity: Iniciar alta de cliente.
        - open_task: Crear un servicio/tarea.
        - query_history: Ver historial de un servicio.
        - add_history: Añadir nota al historial.
        - confirm: Confirmar accion (si, ok, adelante).
        - cancel: Cancelar accion (no, para, anula).
        - consultar_campo: Solicitar direccion, telefono o email de una entidad.

        ENTIDADES (entities):
        - nombre_cliente: cliente o empresa.
        - pkey_servicio: ID servicio (5 dígitos).
        - descripcion: qué hay que hacer.
        - cif: CIF/NIF del cliente.
        - campo: Campo especifico (direccion, telefono, email).
        
        REGLAS DE ORO:
        - Si el usuario da un nombre o responde a "¿A qué nombre...?", es nombre_cliente.
        - Si el usuario da un CIF o responde a "¿Y el CIF...?", es cif.
        - Si pide dirección, teléfono o mail, usa consultar_campo y mapea el campo correspondiente.
        - Responde SIEMPRE en JSON puro: {"intent": "X", "entities": {"campo": "valor"}}
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
