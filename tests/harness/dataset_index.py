from __future__ import annotations

import random
import re
import unicodedata
from typing import Any, Dict, List


ENTITY_DATASETS = {
    "clientes": "cliente",
    "proveedores": "proveedor",
    "acreedores": "acreedor",
    "personal_laboral": "personal",
    "preentidades": "preentidad",
}


def normalize_text(v: str | None) -> str:
    s = (v or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def split_emails(v: str | None) -> List[str]:
    if not v:
        return []
    parts = re.split(r"[;,]", v)
    out = []
    for p in parts:
        p = p.strip().lower()
        if p:
            out.append(p)
    return out


def build_entity_fixtures(datasets: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters: Dict[str, Dict[str, Any]] = {}

    for ds_name, role in ENTITY_DATASETS.items():
        ds = datasets.get(ds_name)
        if not ds:
            continue
        for row in ds.rows:
            pkey = (row.get("PKEY") or "").strip()
            cif = normalize_text(row.get("CIF"))
            emails = split_emails(row.get("EMAIL"))
            dencom = row.get("DENCOM")
            denfis = row.get("DENFIS")

            if pkey:
                key = f"pkey:{pkey}"
            elif cif:
                key = f"cif:{cif}"
            elif emails:
                key = f"email:{emails[0]}"
            else:
                key = f"{ds_name}:row:{len(clusters)+1}"

            if key not in clusters:
                clusters[key] = {
                    "cluster_id": key,
                    "pkeys": set(),
                    "cifs": set(),
                    "emails": set(),
                    "names": set(),
                    "roles": set(),
                    "source_records": [],
                }

            c = clusters[key]
            if pkey:
                c["pkeys"].add(pkey)
            if cif:
                c["cifs"].add(cif)
            for em in emails:
                c["emails"].add(em)
            if dencom:
                c["names"].add(dencom)
            if denfis:
                c["names"].add(denfis)
            c["roles"].add(role)
            c["source_records"].append(
                {
                    "dataset": ds_name,
                    "role": role,
                    "pkey": pkey,
                    "dencom": dencom,
                    "denfis": denfis,
                    "row": row,
                }
            )

    out: List[Dict[str, Any]] = []
    for c in clusters.values():
        out.append(
            {
                "cluster_id": c["cluster_id"],
                "pkeys": sorted(c["pkeys"]),
                "cifs": sorted(c["cifs"]),
                "emails": sorted(c["emails"]),
                "names": sorted(c["names"]),
                "roles": sorted(c["roles"]),
                "source_records": c["source_records"],
            }
        )
    return out


def _pick_first(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any] | None:
    for r in rows:
        if r.get(key):
            return r
    return rows[0] if rows else None


def build_fixture_context(datasets: Dict[str, Any], entity_fixtures: List[Dict[str, Any]], seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)

    clients = datasets.get("clientes").rows if datasets.get("clientes") else []
    articles = datasets.get("articulos").rows if datasets.get("articulos") else []
    services = datasets.get("servicios").rows if datasets.get("servicios") else []
    contracts = datasets.get("contratos").rows if datasets.get("contratos") else []
    facts = datasets.get("facturacion").rows if datasets.get("facturacion") else []
    providers = datasets.get("proveedores").rows if datasets.get("proveedores") else []
    acreedores = datasets.get("acreedores").rows if datasets.get("acreedores") else []

    client = _pick_first(clients, "DENCOM") or {}
    article = _pick_first(articles, "DESCRIPCION") or {}
    service = _pick_first(services, "CLIENTE_DESC") or {}
    contract = _pick_first(contracts, "ENTIDAD_DESC") or {}
    fact = _pick_first(facts, "ENTIDAD_NOMBRE") or {}
    provider = _pick_first(providers, "DENCOM") or {}
    acreedor = _pick_first(acreedores, "DENCOM") or {}

    multirol_candidates = [x for x in entity_fixtures if len(x.get("roles", [])) > 1 and x.get("names")]
    multirol = rng.choice(multirol_candidates) if multirol_candidates else None

    return {
        "entity_dencom": client.get("DENCOM") or "ServiPrueba",
        "entity_denfis": client.get("DENFIS") or client.get("DENCOM") or "ServiPrueba",
        "entity_phone": client.get("TFNO1") or "900000000",
        "entity_email": client.get("EMAIL") or "hola@saaddemo.com",
        "entity_partial": (client.get("DENCOM") or "ServiPrueba").split(" ")[0],
        "article_desc": article.get("DESCRIPCION") or "Calzado de seguridad",
        "article_ref": article.get("REFERENCIA") or "BETA-SFP-155M-2KM",
        "service_client_desc": service.get("CLIENTE_DESC") or "CENTRO DE DIA CENTAL",
        "service_pkey": service.get("PKEY") or "32224",
        "contract_entity": contract.get("ENTIDAD_DESC") or "ServiPrueba",
        "contract_pkey": contract.get("PKEY") or "71",
        "fact_entity": fact.get("ENTIDAD_NOMBRE") or "SerAgua",
        "fact_doc": fact.get("PKEY") or "2",
        "provider_name": provider.get("DENCOM") or "ServiPrueba",
        "acreedor_name": acreedor.get("DENCOM") or "Marta",
        "multirol_name": (multirol.get("names") or ["ServiPrueba"])[0] if multirol else "ServiPrueba",
        "multirol_roles": multirol.get("roles", []) if multirol else ["cliente", "proveedor"],
    }

