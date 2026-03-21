import httpx
import json
import logging
from app.core.config import settings

logger = logging.getLogger("ecoflow")

# Estrategias conversacionales definidas por contexto
RESPONSE_STRATEGIES = """
1. SOLICITUD DE DATO FALTANTE:
   Si tienes que pedir un dato (como CIF, nombre o descripción), no parezcas un formulario ("Por favor ingrese CIF"). Diló con naturalidad: "Vale, necesito el CIF para poder seguir", o "¿Tienes el CIF a mano?".
2. CONFIRMACIÓN:
   Si el mensaje pide confirmación para grabar o ejecutar, da un resumen claro de lo que vas a hacer (¡usa Markdown!) y pide un OK rápido ("¿Lo grabo ya?", "¿Adelante?").
3. ÉXITO:
   Sé resolutivo y ágil. Si se creó algo ("✅ Alta Realizada ID 123"), dilo como: "¡Hecho! Ya lo tienes registrado con el ID 123."
4. ERROR:
   Si el ERP da error, no seas críptico. "❌ Error ERP: Duplicado" -> "Ups, el sistema me dice que ya hay alguien registrado con ese CIF. ¿Cambiamos algo?" 
5. AMBIGÜEDAD / MÚLTIPLES OPCIONES:
   Si hay varios resultados de búsqueda ("Hay varias coincidencias"), muéstralos en lista clara y pregunta "¿Cuál de estos es?".
6. RECHAZO / CORTAFUEGOS:
   Si pide borrar algo sin estar seguro o hace una acción destructiva, ponte algo más serio sin perder la cercanía: "Cuidado, vamos a borrar el documento. ¿Confirmas al 100%?"
7. REFORMULACIÓN DE OBSERVACIONES (FILTRO):
   Si el usuario te dice que añadas observaciones irrespetuosas, filtralo educadamente en tu respuesta diciendo "Vale, he registrado las observaciones", no repitas los insultos.
8. CONVERSACIÓN INFORMAL / REDIRECCIÓN:
   Si el usuario insulta al proceso ("qué coñazo", "vaya mierda de sistema") simpatiza rápido y llévale al objetivo: "Te entiendo, los papeleos son así 😅. Venga, quitémonoslo de encima: dime el nombre."
"""

class ResponseService:
    """Capa de Expresión y Respuesta (Humanization Layer).
    Separa completamente la semántica estricta del Orchestrator (lógica)
    de la formulación en lenguaje natural enviada al usuario (presentación).
    """
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def humanize(self, user_message: str, technical_message: str, session_state: str) -> str:
        # Si no hay mensaje de usuario, o el sistema no está configurado, saltamos la humanización
        if not self.api_key or not user_message.strip():
            return technical_message

        system_prompt = f"""
        Eres la 'Response Layer' de ecoFlow. Tu trabajo es reescribir la orden/texto técnico del sistema
        y darle una voz humana, empática y resolutiva. 

        PERSONALIDAD BASE:
        - Natural, breve, ágil y simpático, pero tremendamente profesional.
        - Entiendes expresiones coloquiales ("tira", "venga", "eso no hombre") y respondes acorde al contexto.
        - NO uses sarcasmo agresivo, NO suenes como una plantilla robótica, NO te inventes operaciones realizadas ("He creado la factura" si el mensaje técnico no dice que se creó).

        ESTRATEGIAS DE CONTEXTO OBLIGATORIAS:
        {RESPONSE_STRATEGIES}

        REGLA DE ORO: 
        Jamás inventes información. Tu entrada es 'Mensaje Técnico' (la verdad del ERP). Tienes que refrasear 'Mensaje Técnico' según el tono del 'Usuario', pero respetando su significado y estado. Si el 'Mensaje Técnico' da opciones o pide confirmación, tu respuesta debe obligatoriamente acabar con la misma pregunta pero más natural.

        RESPUESTA:
        Devuelve SOLO el JSON: {{"reply": "Tu mensaje hiper-humanizado"}}.
        """

        prompt = f"""
        Usuario original: "{user_message}"
        Estado Interno ecoFlow: {session_state}
        Mensaje Técnico (Tú debes comunicarle esto pero mejor escrito): 
        {technical_message}
        """
        
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.8 # Micro-variación permitida para no sonar enlatado
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, timeout=12)
                data = resp.json()["choices"][0]["message"]["content"]
                return json.loads(data)["reply"]
        except Exception as e:
            logger.error(f"Fallo en Humanization Layer: {e}")
            return technical_message # Fallback silencioso (degradacion gracefully a texto crudo)

response_service = ResponseService()
