
import logging
from app.connectors.base import BaseEcoSoftConnector

logger = logging.getLogger("ecoflow")

class EntidadesConnector(BaseEcoSoftConnector):
    """Conector completo para /API_Entidades/"""

    async def grabar_entidad(self, payload: dict) -> dict:
        return await self._post("/API_Entidades/grabarEntidad", payload)

    async def modificar_entidad(self, payload: dict) -> dict:
        return await self._post("/API_Entidades/modificarEntidad", payload)

    async def borrar_entidad(self, pkey: int) -> dict:
        return await self._post("/API_Entidades/borrarEntidad", {"PKEY": pkey})

    async def obtener_entidad(self, pkey: int) -> dict:
        return await self._post("/API_Entidades/ObtenerEntidad", {"PKEY": pkey})

    async def buscar_entidades(self, filtro: dict) -> dict:
        return await self._post("/API_Entidades/ObtenerEntidades", filtro)
