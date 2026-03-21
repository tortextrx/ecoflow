import json, logging
from app.connectors.facturacion import FacturacionConnector

logger = logging.getLogger("ecoflow")
_connector = FacturacionConnector()

def _parse_lista(r: dict) -> list:
    raw = r.get("lista", "[]")
    if isinstance(raw, list): return raw
    try: return json.loads(raw) if isinstance(raw, str) else [raw]
    except: return []

class GrabarFacturacionTool:
    """Registra una operacion de facturacion (Compra, Venta, Gasto)."""
    async def execute(self, payload: dict) -> dict:
        # payload: {nivelcontrol, pkey_entidad, total, referencia, descripcion, observaciones}
        r = await _connector.grabar_facturacion(payload)
        return {"success": r.get("mensaje")=="OK", "pkey": r.get("lista"), "response": r}

class ObtenerFacturacionTool:
    """Busca un documento por su PKEY."""
    async def execute(self, payload: dict) -> dict:
        # payload: {pkey}
        pkey = payload.get("pkey")
        r = await _connector.obtener_documento(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista[0] if lista else {}, "found": bool(lista)}

class ListarFacturacionesTool:
    """Busca facturas segun filtros (ENTIDAD, FECHA_DESDE, etc)."""
    async def execute(self, payload: dict) -> dict:
        r = await _connector.obtener_documentos(payload)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista, "found": bool(lista)}

class BorrarFacturacionTool:
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey")
        r = await _connector.borrar_documento(pkey)
        return {"success": r.get("mensaje")=="OK"}
