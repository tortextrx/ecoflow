
import logging
from app.connectors.facturacion import FacturacionConnector
from app.mappers.facturacion_mapper import FacturaGastoMapper

logger = logging.getLogger("ecoflow")

class RegistrarGastoTool:
    def __init__(self):
        self.connector = FacturacionConnector()
        self.mapper    = FacturaGastoMapper()

    async def execute(
        self,
        cif: str = "",
        pkey_entidad: int = 0,
        fecha: str = "",
        referencia: str = "",
        descripcion: str = "",
        total: float = 0.0,
        base: float = 0.0,
        iva_pct: float = 21.0,
        observaciones: str = ""
    ) -> dict:
        payload = self.mapper.build(
            cif=cif, pkey_entidad=pkey_entidad,
            fecha=fecha, referencia=referencia,
            descripcion=descripcion, total=total,
            base=base, iva_pct=iva_pct,
            observaciones=observaciones
        )
        logger.info(f"registrar_gasto cif={cif} pkey={pkey_entidad} total={total} ref={referencia}")
        response = await self.connector.grabar_factura_gasto(payload)

        if response.get("mensaje") == "OK":
            pkey_doc = response.get("lista", "")
            return {"success": True, "pkey": pkey_doc, "response": response}
        else:
            error = response.get("lista", response.get("body", "Error desconocido"))
            logger.error(f"registrar_gasto error: {error}")
            return {"success": False, "error": error, "response": response}
