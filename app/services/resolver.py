import logging, re, asyncio
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional
from app.services.tools.registry import tool_registry

logger = logging.getLogger("ecoflow")

class ResolverService:
    """Capa de resolucion obligatoria: traduce lenguaje humano a objetos PKEY del ERP."""

    def normalize_entidad(self, raw: dict) -> dict:
        """Normaliza el objeto del ERP a un formato interno estandar."""
        if not raw: return {}
        # Mantenemos las claves en mayúsculas para acceso uniforme
        r = {str(k).upper(): v for k, v in raw.items()}
        
        def to_int_bool(val):
            try:
                if not val: return 0
                if str(val).lower() in ("si", "yes", "true", "1", "-1"): return 1
                return int(float(val)) if str(val).replace('.','',1).replace('-','',1).isdigit() else 0
            except: return 0

        normalized = {
            "pkey": r.get("PKEY") or r.get("ID"),
            "nombre": r.get("DENCOM") or r.get("NOMBRE"),
            "cif": r.get("CIF") or r.get("NIF"),
            "email": r.get("EMAIL"),
            "telefono": r.get("TLF1") or r.get("TELEFONO"),
            "direccion": r.get("DIRECCION") or r.get("DIR"),
            "cp": r.get("CP"),
            "poblacion": r.get("POBLACION"),
            "provincia": r.get("PROVINCIA"),
            "cliente": to_int_bool(r.get("CLIENTE")),
            "proveedor": to_int_bool(r.get("PROVEEDOR")),
            "acreedor": to_int_bool(r.get("ACREEDOR")),
            "usuario": to_int_bool(r.get("USUARIO")),
            "p_laboral": to_int_bool(r.get("P_LABORAL")),
            "sucursales": to_int_bool(r.get("SUCURSALES")),
        }
        logger.info(f"Normalizando Entidad: '{normalized['nombre']}' (PKEY {normalized['pkey']})")
        return normalized

    def parse_selection(self, text: str, max_options: int) -> Optional[int]:
        t = text.lower().strip()
        m = re.search(r'(\d+)', t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= max_options: return n
        return None

    def _normalize_string(self, text: str) -> str:
        """Normalización ligera para SQL: conserva acentos, quita puntuación y sufijos sociedades."""
        if not text: return ""
        text = text.lower().strip()
        # Eliminar sufijos societarios comunes para búsqueda limpia
        text = re.sub(r'\b(s\.l\.u\.|s\.a\.u\.|s\.l\.|s\.a\.|sl|sa|slu|sau)\b', '', text)
        # Quitar puntuación
        return re.sub(r'[^\w\s]', ' ', text).strip()

    def _normalize_for_score(self, text: str) -> str:
        """Normalización fuerte para ranking: sin acentos, sin puntuación."""
        if not text: return ""
        import unicodedata
        t = text.lower().strip()
        normalized = unicodedata.normalize('NFD', t)
        clean = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
        return re.sub(r'[^\w\s]', ' ', clean).strip()

    def _get_strong_tokens(self, text: str) -> List[str]:
        # Usamos normalización ligera para no perder acentos en la búsqueda SQL
        tokens = [t for t in re.findall(r"\b\w{4,}\b", self._normalize_string(text)) ]
        stopwords = {"factura", "cliente", "proveedor", "acreedor", "ecosoft", "empresa", "grupo", "sociedad"}
        return [t for t in tokens if t not in stopwords]

    def _normalize_cif(self, cif: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", str(cif or "").upper())

    def _entity_matches_allowed_types(self, raw: dict, allowed_types: Optional[List[str]]) -> bool:
        if not allowed_types:
            return True
        # Acceso insensible a mayúsculas
        r = {str(k).upper(): v for k, v in raw.items()}
        
        def is_true(val):
            if not val: return False
            v_str = str(val).lower()
            return v_str in ("1", "-1", "si", "yes", "true")

        return any(is_true(r.get(t)) for t in allowed_types)

    async def detect_entity_duplicates(self, name: str = None, cif: str = None, allowed_types: Optional[List[str]] = None) -> dict:
        """Chequeo preventivo para altas: utiliza el nuevo motor de ranking para detectar conflictos."""
        res = await self.resolve_entity(name=name, cif=cif, allowed_types=allowed_types)
        if res["status"] in ("RESOLVED", "AMBIGUOUS"):
            opts = [res["data"]] if res["status"] == "RESOLVED" else res["options"]
            return {"status": "POSSIBLE_DUPLICATE", "options": opts}
        return {"status": "NOT_FOUND", "options": []}

    def _rank_and_evaluate(self, target: str, candidates: List[dict], allowed_types: Optional[List[str]]) -> dict:
        """Aplica ranking local y decide RESOLVED, AMBIGUOUS o NOT_FOUND."""
        if not candidates:
            return {"status": "NOT_FOUND", "reason": "NO_CANDIDATES"}

        q_norm = self._normalize_for_score(target)
        if not q_norm:
            return {"status": "NOT_FOUND", "reason": "EMPTY_TARGET"}

        ranked = []
        seen_pkeys = set()
        
        def get_hybrid_score(q: str, cand: str) -> float:
            if not q or not cand: return 0.0
            if q == cand: return 1.0
            
            # Prefijo o Contiene (Ej. "Cristian" en "Cristian ecoSoft")
            if cand.startswith(q) or q in cand:
                return 0.95 if len(q) >= 4 else 0.90
            
            # Token Overlap
            q_toks = set(q.split())
            cand_toks = set(cand.split())
            intersection = q_toks.intersection(cand_toks)
            if intersection:
                match_ratio = len(intersection) / len(q_toks)
                if match_ratio == 1.0: return 0.92
                return 0.65 + (0.20 * match_ratio)

            # Fuzzy Ratio
            return SequenceMatcher(None, q, cand).ratio()

        for raw in candidates:
            pkey = raw.get("PKEY") or raw.get("ID")
            if not pkey or pkey in seen_pkeys: continue
            if not self._entity_matches_allowed_types(raw, allowed_types): continue
            
            d_com = self._normalize_for_score(raw.get("DENCOM") or "")
            d_fis = self._normalize_for_score(raw.get("DENFIS") or "")
            
            best_score = max(get_hybrid_score(q_norm, d_com), get_hybrid_score(q_norm, d_fis))
            source = "DENCOM" if get_hybrid_score(q_norm, d_com) >= get_hybrid_score(q_norm, d_fis) else "DENFIS"
            
            ranked.append({"score": best_score, "source": source, "data": self.normalize_entidad(raw)})
            seen_pkeys.add(pkey)

        ranked.sort(key=lambda x: x["score"], reverse=True)
        if not ranked:
            return {"status": "NOT_FOUND", "reason": "NO_VALID_TYPES_MATCHED"}

        top = ranked[0]
        top_name = top["data"]["nombre"]
        second_score = ranked[1]["score"] if len(ranked) > 1 else 0
        gap = top["score"] - second_score
        
        status = "NOT_FOUND"
        reason = "LOW_SCORE"

        if top["score"] >= 0.90 and (gap >= 0.15 or len(ranked) == 1):
            status = "RESOLVED"
            reason = "RESOLVED_CLEAR_WIN"
        elif top["score"] >= 0.40:
            status = "AMBIGUOUS"
            reason = "AMBIGUOUS_PARTIAL"
        
        logger.info(f"[ENTITY_RANK] Result: {status} | Query(Norm): '{q_norm}' | Top: '{top_name}' ({top['score']}) | Gap: {gap} | Reason: {reason}")
        
        if status == "RESOLVED":
            return {"status": "RESOLVED", "data": top["data"], "reason": reason}
        if status == "AMBIGUOUS":
            return {"status": "AMBIGUOUS", "options": [x["data"] for x in ranked[:5]], "reason": reason}
        return {"status": "NOT_FOUND", "reason": reason}

    async def resolve_entity(self, name: str = None, cif: str = None, context_pk: int = None, allowed_types: Optional[List[str]] = None) -> dict:
        """Resuelve entidad mediante flujo determinista de 4 etapas (A-D)."""
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
            logger.info(f"[ENTITY_RESOLVE] Query: '{name_clean}' (Norm: '{name_norm}') Types: {allowed_types}")

            # ETAPA A: Búsqueda DENCOM Masiva (Paralela y Robusta)
            try:
                words = [w for w in name_norm.split() if len(w) > 2]
                queries = {f"%{name_norm}%", f"%{self._normalize_for_score(name_norm)}%"}
                if len(words) > 1:
                    for w in words: queries.add(f"%{w}%")
                
                tasks = [tool_registry.listar_entidades.execute({"DENCOM": q}) for q in queries]
                responses = await asyncio.gather(*tasks)
                
                # Unificar resultados por PKEY
                all_raw_a = {}
                for resp in responses:
                    for item in resp.get("data", []):
                        pk = item.get("PKEY") or item.get("ID")
                        if pk: all_raw_a[pk] = item
                
                data_a = list(all_raw_a.values())
                logger.info(f"[RESOLVER] Stage A cobertura: {len(data_a)} candidatos para '{name_clean}'")
            except Exception as e:
                logger.error(f"Error en ETAPA A: {e}")
                data_a = []

            out_a = self._rank_and_evaluate(name_clean, data_a, allowed_types)
            if out_a["status"] == "RESOLVED":
                logger.info("[ENTITY_RESOLVE] RESOLVED Stage A")
                return out_a

            # ETAPA B: Búsqueda DENCOM por Tokens
            tokens = self._get_strong_tokens(name_clean)
            res_b_data = []
            if tokens:
                for t in tokens[:2]:
                    r_b = await tool_registry.listar_entidades.execute({"DENCOM": f"%{t}%"})
                    res_hits = r_b.get("data", [])
                    
                    # Fallback de prefijo: si no hay hits, probamos con prefijo truncado (por si hay acentos o sufijos)
                    if not res_hits and len(t) >= 5:
                        r_b_prefix = await tool_registry.listar_entidades.execute({"DENCOM": f"%{t[:5]}%"})
                        res_hits.extend(r_b_prefix.get("data", []))
                    
                    if res_hits: res_b_data.extend(res_hits)
                    
                    # Variante SIN acentos si el token TIENE (por si SQL es estricto)
                    t_clean = self._normalize_for_score(t)
                    if t_clean != t.lower():
                        r_b2 = await tool_registry.listar_entidades.execute({"DENCOM": f"%{t_clean}%"})
                        if r_b2.get("data"): res_b_data.extend(r_b2["data"])

                out_b = self._rank_and_evaluate(name_clean, res_b_data, allowed_types)
                if out_b["status"] == "RESOLVED":
                    logger.info(f"[ENTITY_RESOLVE] RESOLVED Stage B: {out_b['data']['nombre']}")
                    return out_b

            # ETAPA C: Búsqueda en nombre FISCAL (DENFIS) 
            res_c_data = []
            res_c = await tool_registry.listar_entidades.execute({"DENFIS": f"%{name_norm}%"})
            if res_c.get("data"): res_c_data.extend(res_c["data"])
            
            if tokens and not res_c_data:
                for t in tokens[:2]:
                    r_c = await tool_registry.listar_entidades.execute({"DENFIS": f"%{t}%"})
                    hits_c = r_c.get("data", [])
                    if not hits_c and len(t) >= 5:
                         r_c_prefix = await tool_registry.listar_entidades.execute({"DENFIS": f"%{t[:5]}%"})
                         hits_c.extend(r_c_prefix.get("data", []))
                    if hits_c: res_c_data.extend(hits_c)

            out_c = self._rank_and_evaluate(name_clean, res_c_data, allowed_types)
            if out_c["status"] == "RESOLVED":
                logger.info(f"[ENTITY_RESOLVE] RESOLVED Stage C: {out_c['data']['nombre']}")
                return out_c
            
            # ETAPA D: Fallback acumulativo
            all_raw = data_a + res_b_data + res_c_data
            final_out = self._rank_and_evaluate(name_clean, all_raw, allowed_types)
            return final_out

        return {"status": "NOT_FOUND"}

    async def obtener_campo(self, pkey: int, campo: str) -> str:
        """Obtiene un campo específico de una entidad por su PKEY."""
        res = await tool_registry.obtener_entidad.execute({"pkey": pkey})
        if not res["found"]:
            return "Entidad no encontrada."
        
        entidad = self.normalize_entidad(res["data"])
        c_low = campo.lower().strip()
        
        # Lógica especial para roles/tipos
        if c_low in ("tipo", "rol", "roles"):
            roles = []
            if entidad.get("cliente"): roles.append("Cliente")
            if entidad.get("proveedor"): roles.append("Proveedor")
            if entidad.get("acreedor"): roles.append("Acreedor")
            if entidad.get("usuario"): roles.append("Usuario")
            if entidad.get("p_laboral"): roles.append("Personal Laboral")
            if entidad.get("sucursales"): roles.append("Sucursal")
            if not roles: return "No tiene roles definidos."
            return f"{entidad.get('nombre')} es: " + ", ".join(roles)

        # Mapeo campos semánticos
        mapeo = {
            "direccion": entidad.get("direccion"),
            "telefono": entidad.get("telefono"),
            "email": entidad.get("email"),
            "cif": entidad.get("cif"),
            "nif": entidad.get("cif"),
            "cp": entidad.get("cp"),
            "codigo postal": entidad.get("cp"),
            "poblacion": entidad.get("poblacion"),
            "provincia": entidad.get("provincia"),
        }
        
        valor = mapeo.get(c_low)
        if valor:
            return str(valor)
        return f"No tengo registrado el campo '{campo}' para esta entidad."

    async def resolve_facturacion(self, entity_pk: int, filters: dict = None) -> dict:
        payload = {"ENTIDAD": entity_pk}
        if filters: payload.update(filters)
        res = await tool_registry.listar_facturaciones.execute(payload)
        return {"status": "RESOLVED", "data": res["data"]} if res["success"] else {"status": "ERROR"}

resolver = ResolverService()
