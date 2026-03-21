
from datetime import datetime
from app.mappers.base import BaseEcoSoftPayloadMapper

# Nombres de los tipos de documento por NIVELCONTROL
NIVELCONTROL_NAMES = {
    1:  "PRESUPUESTO COMPRA",
    2:  "PEDIDO COMPRA",
    4:  "ALBARAN COMPRA",
    5:  "FACTURA COMPRA",
    6:  "FACTURA GASTO",
    10: "PRESUPUESTO VENTA",
    11: "PEDIDO VENTA",
    12: "ALBARAN VENTA",
    17: "PREFACTURA VENTA",
}


class FacturacionMapper(BaseEcoSoftPayloadMapper):
    """
    Mapper universal para /API_Facturacion/grabarFacturacion.
    Soporta todos los NIVELCONTROL documentados en FACTURACION.md.
    """

    def build(
        self,
        nivelcontrol: int,
        cif: str = "",
        pkey_entidad: int = 0,
        fecha: str = "",
        referencia: str = "",
        descripcion: str = "",
        total: float = 0.0,
        base: float = 0.0,
        iva_pct: float = 21.0,
        observaciones: str = "",
    ) -> dict:
        # Normalizar fecha
        try:
            fecha_dt = datetime.fromisoformat(fecha)
        except Exception:
            fecha_dt = datetime.now()
        fecha_iso = fecha_dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Modo de identificacion de entidad
        if pkey_entidad and pkey_entidad > 0:
            modo_id = 0
            entidad_id = str(pkey_entidad)
        else:
            modo_id = 1           # Por CIF
            entidad_id = cif

        precio_unitario = round(base, 2) if base else round(total / (1 + iva_pct / 100), 2)
        doc_tipo = NIVELCONTROL_NAMES.get(nivelcontrol, f"DOCUMENTO NC={nivelcontrol}")

        return {
            "Cabecera": {
                "MODO_ID_ENTIDAD": modo_id,
                "SUCURSAL": "1",
                "SUCURSAL_ENVIO": "0",
                "ENTIDAD": entidad_id,
                "ENTIDAD_ENDOSO": "",
                "ENTIDAD_ENVIO": "",
                "AGENTE": 0,
                "PERIODICIDAD": 0,
                "FORMAPAGO": 0,
                "REFERENCIA": referencia or "",
                "SERIE": "",
                "FECHA": fecha_iso,
                "NIVELCONTROL": nivelcontrol,
                "OBSERVACIONES": observaciones or f"{doc_tipo} via ecoFlow - {descripcion}",
                "AUX1": "",
                "AUX2": "",
                "AUX3": ""
            },
            "Detalle": [
                {
                    "MODO_ID_ARTICULO": 1,
                    "ARTICULO": "",
                    "DESCRIPCION": descripcion[:100] if descripcion else doc_tipo,
                    "PRECIO_UNITARIO": precio_unitario,
                    "UNIDADES": 1,
                    "DTO": 0,
                    "AUX1": "",
                    "AUX2": "",
                    "AUX3": ""
                }
            ]
        }


# Alias de compatibilidad — registrar_gasto.py lo sigue usando
class FacturaGastoMapper(FacturacionMapper):
    def build(self, cif="", pkey_entidad=0, fecha="", referencia="",
              descripcion="", total=0.0, base=0.0, iva_pct=21.0,
              observaciones="") -> dict:
        return super().build(
            nivelcontrol=6, cif=cif, pkey_entidad=pkey_entidad,
            fecha=fecha, referencia=referencia, descripcion=descripcion,
            total=total, base=base, iva_pct=iva_pct, observaciones=observaciones
        )
