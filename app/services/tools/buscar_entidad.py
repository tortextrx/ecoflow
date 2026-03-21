import logging
from app.connectors.entidades import EntidadesConnector
from app.mappers.buscar_entidades_mapper import BuscarEntidadesMapper

logger = logging.getLogger("ecoflow")

class BuscarEntidadTool:
    def __init__(self):
        self.connector = EntidadesConnector()
        self.mapper = BuscarEntidadesMapper()

    async def execute(self, cif: str = "", email: str = "", dencom: str = "") -> dict:
        filtro = self.mapper.build(cif=cif, email=email, dencom=dencom)
        logger.info(f"buscar_entidad cif={cif} email={email} dencom={dencom}")
        response = await self.connector.buscar_entidades(filtro)

        if response.get("mensaje") == "OK" and response.get("registros", 0) > 0:
            raw_lista = response.get("lista", [])
            import json
            try:
                lista = json.loads(raw_lista) if isinstance(raw_lista, str) else raw_lista
            except Exception:
                lista = []
                
            if isinstance(lista, list) and len(lista) > 0:
                found = lista[0]
                return {"found": True, "pkey": found.get("PKEY"), "data": found}
        return {"found": False, "pkey": None, "data": None}
