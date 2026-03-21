
from app.mappers.base import BaseEcoSoftPayloadMapper

class ArticuloMapper(BaseEcoSoftPayloadMapper):
    def build(
        self,
        referencia: str = "",
        descripcion: str = "",
        nivelcontrol: int = 1,
        estado: int = 0,
        controlstock: int = 0,
        multitalla: int = 0,
        preciostallas: int = 0,
        observaciones: str = "",
        pkey: int = 0,      # Solo para modificaciones
    ) -> dict:
        payload = {
            "REFERENCIA": referencia,
            "DESCRIPCION": descripcion[:200] if descripcion else "",
            "MODELO": "",
            "COLOR": 0,
            "TALLAJE": 0,
            "PROVEEDOR": 0,
            "MARCA": 0,
            "FAMILIA": 0,
            "ESTADO": estado,
            "CONTROLSTOCK": controlstock,
            "PRECIOSTALLAS": preciostallas,
            "OBSERVACIONES": observaciones or "Articulo via ecoFlow",
            "MULTITALLA": multitalla,
            "NIVELCONTROL": nivelcontrol,
            "STOCKMAXIMO": 0,
            "STOCKMINIMO": 0,
            "METAS": "",
            "MOSTRARWEB": 0,
            "USALOTES": 0,
            "USANUMSERIE": 0,
            "DESCRIPCION_CORTA": "",
            "AUX1": "", "AUX2": "", "AUX3": ""
        }
        if pkey:
            payload["PKEY"] = pkey
        return payload
