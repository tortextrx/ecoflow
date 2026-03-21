
import logging
from app.connectors.base import BaseEcoSoftConnector

logger = logging.getLogger("ecoflow")

class ArticulosConnector(BaseEcoSoftConnector):
    """Conector completo para /API_Articulos/"""

    async def grabar_articulo(self, payload: dict) -> dict:
        return await self._post("/API_Articulos/grabarArticulo", payload)

    async def modificar_articulo(self, payload: dict) -> dict:
        return await self._post("/API_Articulos/modificarArticulo", payload)

    async def borrar_articulo(self, pkey: int) -> dict:
        return await self._post("/API_Articulos/borrarArticulo", {"PKEY": pkey})

    async def obtener_articulo(self, pkey: int) -> dict:
        return await self._post("/API_Articulos/ObtenerArticulo", {"PKEY": pkey})

    async def obtener_articulos(self, filtro: dict) -> dict:
        return await self._post("/API_Articulos/ObtenerArticulos", filtro)
