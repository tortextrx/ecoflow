
import logging
from app.connectors.base import BaseEcoSoftConnector

logger = logging.getLogger("ecoflow")

class ServiciosConnector(BaseEcoSoftConnector):
    """Conector completo para /API_Servicios/"""

    async def grabar_servicio(self, payload: dict) -> dict:
        return await self._post("/API_Servicios/grabarServicio", payload)

    async def modificar_servicio(self, payload: dict) -> dict:
        return await self._post("/API_Servicios/modificarServicio", payload)

    async def borrar_servicio(self, pkey: int) -> dict:
        return await self._post("/API_Servicios/borrarServicio", {"PKEY": pkey})

    async def obtener_servicio(self, pkey: int) -> dict:
        return await self._post("/API_Servicios/ObtenerServicio", {"PKEY": pkey})

    async def obtener_servicios(self, filtro: dict) -> dict:
        return await self._post("/API_Servicios/ObtenerServicios", filtro)

    async def grabar_historico(self, payload: dict) -> dict:
        return await self._post("/API_Servicios/grabarHistorico", payload)

    async def obtener_historico(self, pkey: int, linea: int) -> dict:
        return await self._post("/API_Servicios/ObtenerHistorico", {"PKEY": pkey, "LINEA": linea})

    async def obtener_historico_servicio(self, pkey: int) -> dict:
        return await self._post("/API_Servicios/ObtenerHistorico_Servicio", {"PKEY": pkey})

    async def modificar_historico(self, payload: dict) -> dict:
        return await self._post("/API_Servicios/modificarHistorico", payload)

    async def borrar_historico(self, pkey: int, linea: int) -> dict:
        return await self._post("/API_Servicios/borrarHistorico", {"PKEY": pkey, "LINEA": linea})
