import logging
from app.services.tools.base import BaseTool
from app.models.schemas.domain import DomainCommand
from app.models.schemas.tools import ToolResult
from app.connectors.entidades import EntidadesConnector
from app.mappers.entidades_mapper import EntidadesMapper

logger = logging.getLogger("ecoflow")

class CrearPreentidadTool(BaseTool):
    def __init__(self):
        self.connector = EntidadesConnector()
        self.mapper = EntidadesMapper()

    async def execute(self, command: DomainCommand) -> ToolResult:
        try:
            payload = self.mapper.build(command)
            logger.info(f"executing_crear_preentidad payload={payload}")
            
            response = await self.connector.grabar_entidad(payload)
            
            if response.get("mensaje") == "OK":
                pkey = response.get("lista")
                return ToolResult(
                    success=True,
                    data={"pkey": pkey},
                    next_prompt=f"Operación completada. Se ha creado la pre-entidad con identificador {pkey}."
                )
            else:
                return ToolResult(success=False, error_message=response.get("lista", "Error desconocido"))
        except Exception as e:
            logger.exception("tool_execution_failed")
            return ToolResult(success=False, error_message=str(e))
