import json, logging, re
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
        pkey = self._extract_pkey(r.get("lista")) if success else None
        if success and not pkey:
            pkey = await self._recover_created_entity_pkey(payload)
        return {"success": success, "pkey": pkey, "error": error}

    def _extract_pkey(self, raw) -> int | None:
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            t = raw.strip()
            if t.isdigit():
                return int(t)
            m = re.search(r"\b(\d{3,10})\b", t)
            return int(m.group(1)) if m else None
        if isinstance(raw, dict):
            for k in ("PKEY", "pkey", "ID", "id"):
                v = raw.get(k)
                if str(v).isdigit():
                    return int(v)
        if isinstance(raw, list):
            cands = []
            for it in raw:
                if isinstance(it, dict):
                    v = it.get("PKEY") or it.get("pkey") or it.get("ID")
                    if str(v).isdigit():
                        cands.append(int(v))
            return max(cands) if cands else None
        return None

    async def _recover_created_entity_pkey(self, payload: dict) -> int | None:
        cif = str(payload.get("CIF") or "").strip()
        dencom = str(payload.get("DENCOM") or "").strip()

        if cif:
            by_cif = await _connector.buscar_entidades({"CIF": cif})
            if by_cif.get("mensaje") == "OK":
                lista = _parse_lista(by_cif)
                exact = [x for x in lista if str(x.get("CIF") or "").strip().upper() == cif.upper()]
                if exact:
                    p = self._extract_pkey(exact[-1])
                    if p:
                        return p

        if dencom:
            by_name = await _connector.buscar_entidades({"DENCOM": f"%{dencom}%"})
            if by_name.get("mensaje") == "OK":
                lista = _parse_lista(by_name)
                exact = [x for x in lista if str(x.get("DENCOM") or "").strip().lower() == dencom.lower()]
                target = exact[-1] if exact else (lista[-1] if lista else None)
                p = self._extract_pkey(target)
                if p:
                    return p

        return None

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


class BorrarEntidadTool:
    """Elimina una entidad por PKEY. Operacion IRREVERSIBLE."""
    async def execute(self, payload: dict) -> dict:
        pkey = payload.get("pkey") or payload.get("PKEY")
        r = await _connector.borrar_entidad(pkey)
        success = r.get("mensaje") == "OK"
        return {"success": success, "error": r.get("lista") if not success else None}


class ModificarEntidadTool:
    """Modifica campos de una entidad existente por PKEY."""
    async def execute(self, payload: dict) -> dict:
        if not payload.get("PKEY"):
            return {"success": False, "error": "Falta PKEY para modificar entidad"}
        r = await _connector.modificar_entidad(payload)
        success = r.get("mensaje") == "OK"
        return {"success": success, "error": r.get("lista") if not success else None}
