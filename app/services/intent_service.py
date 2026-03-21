import json, logging
from uuid import UUID
from app.providers.llm_provider import LLMProvider
from app.models.schemas.llm import ModelHint
from app.models.schemas.domain import DomainCommand

logger = logging.getLogger("ecoflow")

class IntentService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def _get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "crear_preentidad",
                    "description": "Crea una pre-entidad (prospecto/borrador) en ecoSoftWEB.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "DENCOM": {"type": "string", "description": "Nombre comercial de la entidad"},
                            "CIF": {"type": "string", "description": "CIF/NIF de la entidad"},
                            "TLF1": {"type": "string", "description": "Teléfono de contacto"},
                            "EMAIL": {"type": "string", "description": "Email de contacto"},
                            "PERSONA": {"type": "string", "description": "Nombre de la persona de contacto"}
                        },
                        "required": ["DENCOM"]
                    }
                }
            }
        ]

    async def detect(self, text: str, history: list[dict], operation_id: UUID) -> DomainCommand | None:
        messages = history + [{"role": "user", "content": text}]
        tools = self._get_tools()
        resp = await self.llm.complete(messages, tools, ModelHint.CONVERSATION)
        if not resp.tool_calls:
            return None
        tc = resp.tool_calls[0]
        try:
            args = json.loads(tc["arguments"])
            missing = []
            if not args.get("DENCOM"):
                missing.append("DENCOM")
            return DomainCommand(
                intent_name=tc["name"],
                operation_id=operation_id,
                fields=args,
                missing_required=missing,
                is_complete=len(missing) == 0,
                completion_score=1.0 if len(missing) == 0 else 0.5
            )
        except Exception as e:
            logger.error(f"Error parsing intent tool calls: {e}")
            return None
