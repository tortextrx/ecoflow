import json, logging
from app.connectors.entidades import EntidadesConnector

logger = logging.getLogger("ecoflow")
_connector = EntidadesConnector()

def _parse_lista(r: dict) -> list:
    raw = r.get("lista", "[]")
    if not raw or raw == "[]": return []
    if isinstance(raw, list): return raw
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict): return [data]
        return data if isinstance(data, list) else [data]
    except Exception as e:
        logger.error(f"Error parseando lista: {str(e)}")
        return []

class CrearEntidadTool:
    async def execute(self, payload: dict) -> dict:
        r = await _connector.grabar_entidad(payload)
        success = r.get("mensaje") == "OK"
        # En ecoSoft, si mensaje == ERROR, el error viene en 'lista'
        error = r.get("lista") if not success else None
        return {"success": success, "pkey": r.get("lista") if success else None, "error": error}

class ObtenerEntidadTool:
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey")
        r = await _connector.obtener_entidad(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista[0] if lista else {}, "found": bool(lista), "error": r.get("lista") if r.get("mensaje") != "OK" else None}

class ListarEntidadesTool:
    async def execute(self, payload: dict) -> dict:
        r = await _connector.buscar_entidades(payload)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista, "found": bool(lista), "error": r.get("lista") if r.get("mensaje") != "OK" else None}
