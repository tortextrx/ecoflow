import json, logging
from app.connectors.articulos import ArticulosConnector

logger = logging.getLogger("ecoflow")
_connector = ArticulosConnector()

def _parse_lista(r: dict) -> list:
    raw = r.get("lista", "[]")
    if isinstance(raw, list): return raw
    if isinstance(raw, dict): return [raw]
    try:
        p = json.loads(raw)
        return p if isinstance(p, list) else [p]
    except: return []

class ListarArticulosTool:
    """Busca articulos por descripcion, referencia, etc."""
    async def execute(self, filtros: dict) -> dict:
        # Filtros comunes: {"DESCRIPCION": "Osito", "REFERENCIA": "ART-001"}
        r = await _connector.obtener_articulos(filtros)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista, "found": bool(lista), "response": r}

class CrearArticuloTool:
    async def execute(self, p: dict) -> dict:
        # Payload quirurgico segun ARTICULOS.md (pag 104)
        defaults = {
            "REFERENCIA": "", "DESCRIPCION": "", "MODELO": "", "COLOR": 0,
            "TALLAJE": 0, "PROVEEDOR": 0, "MARCA": 0, "FAMILIA": 1,
            "ESTADO": 0, "CONTROLSTOCK": 1, "PRECIOSTALLAS": 0,
            "OBSERVACIONES": "Alta ecoFlow", "MULTITALLA": 0, "NIVELCONTROL": 1,
            "STOCKMAXIMO": 0, "STOCKMINIMO": 0, "METAS": "", "MOSTRARWEB": 1,
            "USALOTES": 0, "USANUMSERIE": 0, "DESCRIPCION_CORTA": "",
            "AUX1": "", "AUX2": "", "AUX3": ""
        }
        full_payload = {**defaults, **p}
        r = await _connector.grabar_articulo(full_payload)
        return {"success": r.get("mensaje")=="OK", "pkey": r.get("lista"), "response": r}

class ObtenerArticuloTool:
    async def execute(self, pkey: int) -> dict:
        r = await _connector.obtener_articulo(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje")=="OK", "data": lista[0] if lista else {}, "found": bool(lista)}
