import json, logging
from app.connectors.servicios import ServiciosConnector

logger = logging.getLogger("ecoflow")
_connector = ServiciosConnector()

def _parse_lista(r: dict) -> list:
    raw = r.get("lista", "[]")
    if isinstance(raw, list): return raw
    try: return json.loads(raw) if isinstance(raw, str) else [raw]
    except: return []

class CrearServicioTool:
    """Crea una tarea o cita de servicio."""
    async def execute(self, payload: dict) -> dict:
        r = await _connector.grabar_servicio(payload)
        return {"success": r.get("mensaje")=="OK", "pkey": r.get("lista")}

class GrabarHistoricoTool:
    """Registra historico de actuacion."""
    async def execute(self, payload: dict) -> dict:
        r = await _connector.grabar_historico(payload)
        return {"success": r.get("mensaje")=="OK"}

class ObtenerServicioTool:
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey")
        r = await _connector.obtener_servicio(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista[0] if lista else {}, "found": bool(lista)}

class ObtenerHistoricoServicioTool:
    """Obtiene el historial de actuaciones de un servicio."""
    async def execute(self, payload: dict) -> dict:
        # payload: {pkey}
        pkey = payload.get("pkey")
        r = await _connector.obtener_historico_servicio(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista, "found": bool(lista)}

class BorrarServicioTool:
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey")
        r = await _connector.borrar_servicio(pkey)
        return {"success": r.get("mensaje")=="OK"}
