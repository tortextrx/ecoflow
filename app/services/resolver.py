import logging, re
from difflib import SequenceMatcher
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
            "direccion": raw.get("DIRECCION") or raw.get("DIR"),
            "cliente": int(raw.get("CLIENTE") or 0),
            "proveedor": int(raw.get("PROVEEDOR") or 0),
            "acreedor": int(raw.get("ACREEDOR") or 0),
            "usuario": int(raw.get("USUARIO") or 0),
            "p_laboral": int(raw.get("P_LABORAL") or 0),
            "sucursales": int(raw.get("SUCURSALES") or 0),
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

    def _normalize_string(self, text: str) -> str:
        if not text: return ""
        import unicodedata, re
        text = text.lower().strip()
        normalized = unicodedata.normalize('NFD', text)
        clean = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
        return re.sub(r'[^\w\s]', '', clean)

    def _normalize_cif(self, cif: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", str(cif or "").upper())

    def _entity_matches_allowed_types(self, raw: dict, allowed_types: Optional[List[str]]) -> bool:
        if not allowed_types:
            return True
        flags = {
            "CLIENTE": int(raw.get("CLIENTE") or 0),
            "PROVEEDOR": int(raw.get("PROVEEDOR") or 0),
            "ACREEDOR": int(raw.get("ACREEDOR") or 0),
            "USUARIO": int(raw.get("USUARIO") or 0),
            "P_LABORAL": int(raw.get("P_LABORAL") or 0),
            "SUCURSALES": int(raw.get("SUCURSALES") or 0),
        }
        return any(flags.get(t, 0) == 1 for t in allowed_types)

    def _rank_similar_names(self, name: str, candidates: List[dict], threshold: float = 0.84) -> List[dict]:
        target = self._normalize_string(name)
        ranked = []
        for it in candidates:
            cand_name = self._normalize_string(it.get("DENCOM") or it.get("NOMBRE") or "")
            if not cand_name:
                continue
            score = SequenceMatcher(None, target, cand_name).ratio()
            if score >= threshold:
                ranked.append((score, it))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [{**self.normalize_entidad(x[1]), "score": round(x[0], 3)} for x in ranked[:5]]

    async def detect_entity_duplicates(self, name: str = None, cif: str = None, allowed_types: Optional[List[str]] = None) -> dict:
        """Chequeo preventivo para altas: CIF exacto + nombre normalizado + similitud razonable."""
        options: List[dict] = []
        seen = set()

        if cif:
            cif_norm = self._normalize_cif(cif)
            res_cif = await tool_registry.listar_entidades.execute({"CIF": cif})
            for raw in res_cif.get("data", []):
                if self._normalize_cif(raw.get("CIF") or "") != cif_norm:
                    continue
                if not self._entity_matches_allowed_types(raw, allowed_types):
                    continue
                n = self.normalize_entidad(raw)
                if n.get("pkey") not in seen:
                    seen.add(n.get("pkey"))
                    options.append(n)

        if name:
            name_clean = name.strip()
            name_norm = self._normalize_string(name_clean)
            res_name = await tool_registry.listar_entidades.execute({"DENCOM": f"%{name_clean}%"})
            lista = [x for x in res_name.get("data", []) if self._entity_matches_allowed_types(x, allowed_types)]
            exact = [x for x in lista if self._normalize_string(x.get("DENCOM", "")) == name_norm]
            similar = self._rank_similar_names(name_clean, lista, threshold=0.82)

            for raw in exact:
                n = self.normalize_entidad(raw)
                if n.get("pkey") not in seen:
                    seen.add(n.get("pkey"))
                    options.append(n)
            for n in similar:
                if n.get("pkey") not in seen:
                    seen.add(n.get("pkey"))
                    options.append(n)

        if options:
            return {"status": "POSSIBLE_DUPLICATE", "options": options[:5]}
        return {"status": "NOT_FOUND", "options": []}

    async def resolve_entity(self, name: str = None, cif: str = None, context_pk: int = None, allowed_types: Optional[List[str]] = None) -> dict:
        """Resuelve y devuelve una entidad normalizada (Prioriza Exacto)."""
        if context_pk:
            res = await tool_registry.obtener_entidad.execute({"pkey": context_pk})
            if res["found"] and self._entity_matches_allowed_types(res["data"], allowed_types):
                return {"status": "RESOLVED", "data": self.normalize_entidad(res["data"])}

        if cif:
            res = await tool_registry.listar_entidades.execute({"CIF": cif})
            lista = [x for x in res.get("data", []) if self._entity_matches_allowed_types(x, allowed_types)]
            cif_norm = self._normalize_cif(cif)
            exact_cif = [x for x in lista if self._normalize_cif(x.get("CIF") or "") == cif_norm]
            if len(exact_cif) == 1:
                return {"status": "RESOLVED", "data": self.normalize_entidad(exact_cif[0])}
            if len(exact_cif) > 1:
                return {"status": "AMBIGUOUS", "options": [self.normalize_entidad(x) for x in exact_cif[:5]]}

        if name:
            name_clean = name.strip()
            name_norm = self._normalize_string(name_clean)
            
            # Busqueda amplia inicial por comodin
            res = await tool_registry.listar_entidades.execute({"DENCOM": f"%{name_clean}%"})
            lista = res.get("data", [])
            
            if not lista:
                # Fallback: Quitar palabras sueltas cortas o intentar busqueda muy abierta
                res = await tool_registry.listar_entidades.execute({"DENCOM": f"%{name_clean.split()[0]}%"})
                lista = res.get("data", [])

            lista = [x for x in lista if self._entity_matches_allowed_types(x, allowed_types)]

            if lista:
                # 1. Filtro exacto (normalizado)
                exact_matches = [x for x in lista if self._normalize_string(x.get("DENCOM", "")) == name_norm]
                if len(exact_matches) == 1:
                    return {"status": "RESOLVED", "data": self.normalize_entidad(exact_matches[0])}
                
                # 2. Filtro contains (normalizado)
                contains_matches = exact_matches or [x for x in lista if name_norm in self._normalize_string(x.get("DENCOM", ""))]
                if len(contains_matches) == 1:
                    return {"status": "RESOLVED", "data": self.normalize_entidad(contains_matches[0])}
                
                candidatos = contains_matches if contains_matches else lista
                
                if len(candidatos) > 0:
                    options = [self.normalize_entidad(x) for x in candidatos[:5]]
                    # Si solo quedó uno tras todo
                    if len(options) == 1:
                        return {"status": "RESOLVED", "data": options[0]}
                    return {"status": "AMBIGUOUS", "options": options}

                similar = self._rank_similar_names(name_clean, lista, threshold=0.84)
                if similar:
                    return {"status": "POSSIBLE_DUPLICATE", "options": similar}

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
