import json, logging
import re
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
        logger.info(f"[SERVICE_TRACE] create_payload={payload}")
        r = await _connector.grabar_servicio(payload)
        success = r.get("mensaje") == "OK"
        pkey = self._extract_pkey(r.get("lista")) if success else None
        logger.info(f"[SERVICE_TRACE] create_response={r} parsed_pkey={pkey}")

        # Fallback real: recuperar PKEY por lectura ERP si la respuesta de alta no lo expone claro
        if success and not pkey:
            pkey = await self._recover_created_service_pkey(payload)
            logger.info(f"[SERVICE_TRACE] recovered_pkey={pkey}")

        return {"success": success, "pkey": pkey, "error": r.get("lista") if not success else None}

    def _extract_pkey(self, raw) -> int | None:
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            t = raw.strip()
            if t.isdigit():
                return int(t)
            m = re.search(r"\b(\d{3,8})\b", t)
            return int(m.group(1)) if m else None
        if isinstance(raw, dict):
            for k in ("PKEY", "pkey", "ID", "id"):
                if k in raw and str(raw[k]).isdigit():
                    return int(raw[k])
        if isinstance(raw, list) and raw:
            # Priorizar mayor PKEY disponible
            cands = []
            for it in raw:
                if isinstance(it, dict):
                    v = it.get("PKEY") or it.get("pkey") or it.get("ID")
                    if str(v).isdigit():
                        cands.append(int(v))
            return max(cands) if cands else None
        return None

    async def _recover_created_service_pkey(self, payload: dict) -> int | None:
        client_pk = payload.get("CLIENTE")
        desc = str(payload.get("SERVICIO_DESCRIPCION") or "").strip().lower()
        if not client_pk:
            return None
        r = await _connector.obtener_servicios({"CLIENTE": client_pk})
        if r.get("mensaje") != "OK":
            return None
        lista = _parse_lista(r)
        if not lista:
            return None

        # Intentar match por descripción primero, luego mayor PKEY del cliente
        matched = []
        for it in lista:
            try:
                p = int(it.get("PKEY"))
            except Exception:
                continue
            d = str(it.get("SERVICIO_DESCRIPCION") or it.get("DESCRIPCION") or "").strip().lower()
            if desc and desc in d:
                matched.append(p)
        if matched:
            return max(matched)

        all_pkeys = []
        for it in lista:
            try:
                all_pkeys.append(int(it.get("PKEY")))
            except Exception:
                pass
        return max(all_pkeys) if all_pkeys else None

class GrabarHistoricoTool:
    """Registra historico de actuacion."""
    async def execute(self, payload: dict) -> dict:
        logger.info(f"[SERVICE_TRACE] historico_payload={payload}")
        r = await _connector.grabar_historico(payload)
        logger.info(f"[SERVICE_TRACE] historico_response={r}")
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
