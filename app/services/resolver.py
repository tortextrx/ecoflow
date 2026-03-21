import logging, re
from typing import Dict, Any, List, Optional
from app.services.tools.registry import tool_registry

logger = logging.getLogger("ecoflow")

class ResolverService:
    """Capa de resolucion obligatoria: traduce lenguaje humano a objetos PKEY del ERP."""

    def normalize_entidad(self, raw: dict) -> dict:
        """Normaliza el objeto del ERP a un formato interno estandar."""
        if not raw: return {}
        # Mapeo de campos ERP -> ecoFlow
        normalized = {
            "pkey": raw.get("PKEY") or raw.get("ID"),
            "nombre": raw.get("DENCOM") or raw.get("NOMBRE"),
            "cif": raw.get("CIF") or raw.get("NIF"),
            "email": raw.get("EMAIL"),
            "telefono": raw.get("TLF1") or raw.get("TELEFONO"),
            "direccion": raw.get("DIRECCION") or raw.get("DIR")
        }
        logger.info(f"Normalizando Entidad: {raw} -> {normalized}")
        return normalized

    def parse_selection(self, text: str, max_options: int) -> Optional[int]:
        t = text.lower().strip()
        m = re.search(r'(\d+)', t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= max_options: return n
        return None

    async def resolve_entity(self, name: str = None, cif: str = None, context_pk: int = None) -> dict:
        """Resuelve y devuelve una entidad normalizada (Prioriza Exacto)."""
        if context_pk:
            res = await tool_registry.obtener_entidad.execute({"pkey": context_pk})
            if res["found"]: return {"status": "RESOLVED", "data": self.normalize_entidad(res["data"])}

        if cif:
            res = await tool_registry.listar_entidades.execute({"CIF": cif})
            lista = res.get("data", [])
            if lista: return {"status": "RESOLVED", "data": self.normalize_entidad(lista[0])}

        if name:
            name_clean = name.strip()
            # 1. Intento Exacto
            res = await tool_registry.listar_entidades.execute({"DENCOM": name_clean})
            lista = res.get("data", [])
            
            if len(lista) == 1:
                return {"status": "RESOLVED", "data": self.normalize_entidad(lista[0])}
            
            # 2. Intento con comodines (solo si no hay exacto)
            if not lista:
                res = await tool_registry.listar_entidades.execute({"DENCOM": f"%{name_clean}%"})
                lista = res.get("data", [])
                if len(lista) == 1:
                    return {"status": "RESOLVED", "data": self.normalize_entidad(lista[0])}

            if len(lista) > 1:
                return {"status": "AMBIGUOUS", "options": lista[:5]}
            
            if not lista: return {"status": "NOT_FOUND"}

        return {"status": "NOT_FOUND"}

    async def obtener_campo(self, pkey: int, campo: str) -> str:
        """Obtiene un campo específico de una entidad por su PKEY."""
        res = await tool_registry.obtener_entidad.execute({"pkey": pkey})
        if not res["found"]:
            return "Entidad no encontrada."
        
        entidad = self.normalize_entidad(res["data"])
        
        # Mapeo campos semánticos
        mapeo = {
            "direccion": entidad.get("direccion"),
            "telefono": entidad.get("telefono"),
            "email": entidad.get("email")
        }
        
        valor = mapeo.get(campo.lower())
        if valor:
            return str(valor)
        return f"No tengo registrado el campo '{campo}' para esta entidad."

    async def resolve_facturacion(self, entity_pk: int, filters: dict = None) -> dict:
        payload = {"ENTIDAD": entity_pk}
        if filters: payload.update(filters)
        res = await tool_registry.listar_facturaciones.execute(payload)
        return {"status": "RESOLVED", "data": res["data"]} if res["success"] else {"status": "ERROR"}

resolver = ResolverService()
