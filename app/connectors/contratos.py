
import logging
from app.connectors.base import BaseEcoSoftConnector

logger = logging.getLogger("ecoflow")

class ContratosConnector(BaseEcoSoftConnector):
    """Conector completo para /API_Contratos/"""

    async def grabar_contrato(self, payload: dict) -> dict:
        return await self._post("/API_Contratos/grabarContrato", payload)

    async def modificar_contrato(self, payload: dict) -> dict:
        return await self._post("/API_Contratos/modificarContrato", payload)

    async def borrar_contrato(self, pkey: int) -> dict:
        return await self._post("/API_Contratos/borrarContrato", {"PKEY": pkey})

    async def obtener_contrato(self, pkey: int) -> dict:
        return await self._post("/API_Contratos/ObtenerContrato", {"PKEY": pkey})

    async def obtener_contratos(self, filtro: dict) -> dict:
        return await self._post("/API_Contratos/ObtenerContratos", filtro)
