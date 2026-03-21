
import logging
from app.connectors.base import BaseEcoSoftConnector

logger = logging.getLogger("ecoflow")

class FacturacionConnector(BaseEcoSoftConnector):
    """Conector completo para /API_Facturacion/"""

    async def grabar_facturacion(self, payload: dict) -> dict:
        return await self._post("/API_Facturacion/grabarFacturacion", payload)

    # Alias semántico para compatibilidad con registrar_gasto.py
    async def grabar_factura_gasto(self, payload: dict) -> dict:
        return await self.grabar_facturacion(payload)

    async def modificar_facturacion(self, payload: dict) -> dict:
        return await self._post("/API_Facturacion/modificarFacturacion", payload)

    async def borrar_facturacion(self, pkey: int) -> dict:
        return await self._post("/API_Facturacion/borrarFacturacion", {"PKEY": pkey})

    async def obtener_facturacion(self, pkey: int) -> dict:
        return await self._post("/API_Facturacion/ObtenerFacturacion", {"PKEY": pkey})

    async def obtener_facturaciones(self, filtro: dict) -> dict:
        return await self._post("/API_Facturacion/ObtenerFacturaciones", filtro)

    async def grabar_linea(self, payload: dict) -> dict:
        return await self._post("/API_Facturacion/grabarFacturacionLinea", payload)
