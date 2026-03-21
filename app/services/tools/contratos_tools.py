import json, logging
from datetime import datetime
from app.connectors.contratos import ContratosConnector

logger = logging.getLogger("ecoflow")
_connector = ContratosConnector()

def _parse_lista(r: dict) -> list:
    raw = r.get("lista", "[]")
    if isinstance(raw, list): return raw
    if isinstance(raw, dict): return [raw]
    try:
        p = json.loads(raw)
        return p if isinstance(p, list) else [p]
    except: return []

def _get_now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def _default_end_date() -> str:
    # Por defecto contratos a 1 año
    from datetime import timedelta
    return (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")

class CrearContratoTool:
    """Crea un contrato vinculado a una entidad. Requiere pkey_entidad, descripcion, precio_unitario.
    Campos opcionales de la API: periodicidad (defaul=1), estado (0=activo), articulo (0=libre).
    """
    async def execute(self, payload: dict) -> dict:
        defaults = {
            "PKEY": 0,
            "MODO_ID_ENTIDAD": 0,       # Por PKEY
            "MODO_ID_ARTICULO": 0,
            "MODO_ID_PROYECTO": 0,
            "ENTIDAD": 0,
            "ENTIDAD_PAGADORA": 0,
            "ENTIDAD_ENDOSO": 0,
            "ENTIDAD_ENVIO": 0,
            "SUCURSAL": 1,
            "COMERCIAL": 0,
            "PROYECTO": 0,
            "ARTICULO": 0,
            "DESCRIPCION": "",
            "PRECIO_UNITARIO": 0.0,
            "UNIDADES": 1,
            "DTO": 0,
            "FECHA_EMISION": _get_now_iso(),
            "FECHA_FIN": _default_end_date(),
            "PERIODICIDAD": 1,           # Mensual por defecto
            "ESTADO": 0,                 # Activo
            "BLOQUE": 1,
            "CODIGO_CONTRATO": "",
            "REFERENCIA": "",
            "OBSERVACIONES": "Alta vía ecoFlow",
            "OBSERVACIONES_PRIVADAS": "",
            "TCOM_LINEA": 0,
            "AUX1": "", "AUX2": "", "AUX3": ""
        }
        full = {**defaults, **payload}
        # Si viene pkey_entidad mapeamos
        if "pkey_entidad" in full:
            full["ENTIDAD"] = full.pop("pkey_entidad")
            full["ENTIDAD_PAGADORA"] = full["ENTIDAD"]
        r = await _connector.grabar_contrato(full)
        success = r.get("mensaje") == "OK"
        return {"success": success, "pkey": r.get("lista") if success else None, "error": r.get("lista") if not success else None}

class ObtenerContratoTool:
    """Obtiene un contrato por su PKEY."""
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey") or payload.get("PKEY")
        r = await _connector.obtener_contrato(pkey)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje") == "OK", "data": lista[0] if lista else {}, "found": bool(lista), "error": r.get("lista") if not lista else None}

class ListarContratosTool:
    """Busca contratos por entidad, referencia, código, o rango de fechas."""
    async def execute(self, filtros: dict) -> dict:
        base = {
            "PKEY": 0, "MODO_ID_ENTIDAD": 0, "MODO_ID_ARTICULO": 0, "MODO_ID_PROYECTO": 0,
            "ENTIDAD": 0, "ENTIDAD_PAGADORA": 0, "ENTIDAD_ENDOSO": 0, "ENTIDAD_ENVIO": 0,
            "SUCURSAL": 1, "COMERCIAL": 0, "PROYECTO": 0, "ARTICULO": 0, "DESCRIPCION": "",
            "PRECIO_UNITARIO_DESDE": 0.0, "PRECIO_UNITARIO_HASTA": 999999999.0,
            "UNIDADES_DESDE": 0, "UNIDADES_HASTA": 999999999, "DTO": 0.0,
            "FECHA_EMISION_DESDE": "2000-01-01T00:00:00", "FECHA_EMISION_HASTA": "2100-12-31T23:59:59",
            "FECHA_FIN_DESDE": "2000-01-01T00:00:00", "FECHA_FIN_HASTA": "2100-12-31T23:59:59",
            "PERIODICIDAD": 0, "ESTADO": 0, "BLOQUE": 0, "CODIGO_CONTRATO": "",
            "REFERENCIA": "", "OBSERVACIONES": "", "OBSERVACIONES_PRIVADAS": "",
            "TCOM_LINEA": 0, "SERIE": "", "AUX1": "", "AUX2": "", "AUX3": ""
        }
        # Mapear pkey_entidad si viene
        if "pkey_entidad" in filtros:
            filtros["ENTIDAD"] = filtros.pop("pkey_entidad")
        payload = {**base, **filtros}
        r = await _connector.obtener_contratos(payload)
        lista = _parse_lista(r)
        return {"success": r.get("mensaje") == "OK", "data": lista, "found": bool(lista), "count": len(lista)}

class ModificarContratoTool:
    """Modifica un contrato existente por PKEY."""
    async def execute(self, payload: dict) -> dict:
        r = await _connector.modificar_contrato(payload)
        success = r.get("mensaje") == "OK"
        return {"success": success, "pkey": r.get("lista"), "error": r.get("lista") if not success else None}

class BorrarContratoTool:
    """Elimina un contrato por PKEY. Operacion IRREVERSIBLE."""
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey") or payload.get("PKEY")
        r = await _connector.borrar_contrato(pkey)
        success = r.get("mensaje") == "OK"
        return {"success": success, "error": r.get("lista") if not success else None}
