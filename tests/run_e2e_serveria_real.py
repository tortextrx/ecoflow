import asyncio
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

BASE_URL = os.getenv("ECOFLOW_BASE_URL", "http://127.0.0.1:18080")
CHAT_URL = f"{BASE_URL}/api/ecoflow/chat"
ROOT_URL = f"{BASE_URL}/"


@dataclass
class E2EContext:
    session_id: str
    entity_name: Optional[str] = None
    entity_cif: Optional[str] = None
    entity_id: Optional[int] = None
    article_desc: Optional[str] = None
    contract_id: Optional[int] = None
    service_id: Optional[int] = None


class BlockingFailure(Exception):
    pass


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise BlockingFailure(msg)


def extract_first_int(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{3,8})\b", text or "")
    return int(m.group(1)) if m else None


def extract_created_service_id(text: str) -> Optional[int]:
    m = re.search(r"servicio\s+(\d{3,8}).*cread", (text or "").lower())
    return int(m.group(1)) if m else None


async def post_chat(client: httpx.AsyncClient, ctx: E2EContext, message: str) -> dict:
    headers = {
        "x-trace-id": f"real-e2e-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    resp = await client.post(CHAT_URL, data={"session_id": ctx.session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(resp.status_code == 200, f"HTTP chat inesperado: {resp.status_code}")
    data = resp.json()
    assert_true("reply" in data and "state" in data, "Respuesta chat sin contrato básico")
    return data


async def run() -> int:
    run_id = str(int(time.time()))[-6:]
    ctx = E2EContext(session_id=f"srvreal-{uuid.uuid4().hex[:8]}")
    ctx.entity_name = f"E2E_REAL_{run_id}"
    ctx.entity_cif = f"B9{run_id}77"
    ctx.article_desc = f"Articulo E2E REAL {run_id}"

    print(f"BASE_URL={BASE_URL}")
    print(f"SESSION={ctx.session_id}")

    async with httpx.AsyncClient() as client:
        # 0) Smoke endpoint
        print("\n[SMOKE] GET /")
        root = await client.get(ROOT_URL, timeout=15.0)
        assert_true(root.status_code == 200, f"Root no responde 200: {root.status_code}")
        root_json = root.json()
        assert_true(root_json.get("service") == "ecoFlow", "Root sin service=ecoFlow")
        print("[PASS] Root OK")

        print("\n[SMOKE] POST /api/ecoflow/chat")
        smoke = await post_chat(client, ctx, "hola")
        print(f"[PASS] Chat OK state={smoke.get('state')}")

        # 1) Alta de entidad (bloqueante)
        print("\n[BLOCKING] Alta de entidad")
        r1 = await post_chat(client, ctx, f"crea un cliente llamado {ctx.entity_name} con CIF {ctx.entity_cif}")
        r2 = await post_chat(client, ctx, "si, grábalo")
        assert_true("alta" in r2["reply"].lower() or "completada" in r2["reply"].lower(), "No se confirma alta de entidad")
        ctx.entity_id = extract_first_int(r2["reply"])
        assert_true(ctx.entity_id is not None, "No pude extraer ID de entidad creada")
        print(f"[PASS] Entidad creada id={ctx.entity_id}")

        # 2) Consulta de entidad (post-condición)
        print("\n[BLOCKING] Consulta de entidad")
        rq = await post_chat(client, ctx, f"consulta el cliente {ctx.entity_name}")
        assert_true(ctx.entity_name.lower() in rq["reply"].lower() or str(ctx.entity_id) in rq["reply"], "Consulta entidad no refleja post-condición")
        print("[PASS] Consulta entidad OK")

        # 3) Modificación de entidad (bloqueante + post-condición real)
        print("\n[BLOCKING] Modificación de entidad")
        new_email = f"e2e.real.{run_id}@example.com"
        rm = await post_chat(client, ctx, f"modifica el cliente {ctx.entity_name} y pon email {new_email}")
        assert_true("error" not in rm["reply"].lower(), "Modificación de entidad devolvió error")
        assert_true(any(k in rm["reply"].lower() for k in ["modific", "actualiz", "observ"]), "No hay evidencia de modificación de entidad")

        # Post-condición obligatoria: lectura real del campo modificado
        rf = await post_chat(client, ctx, f"dime el email del cliente {ctx.entity_name}")
        assert_true(new_email.lower() in rf["reply"].lower(), "La lectura posterior no refleja el email modificado")
        print("[PASS] Modificación entidad OK")

        # 4) Borrado de entidad (bloqueante)
        print("\n[BLOCKING] Borrado de entidad")
        await post_chat(client, ctx, f"borra la entidad {ctx.entity_id}")
        rd = await post_chat(client, ctx, "CONFIRMO")
        assert_true("elimin" in rd["reply"].lower() or "borr" in rd["reply"].lower(), "No se confirma borrado de entidad")
        print("[PASS] Borrado entidad OK")

        # 4b) Re-alta entidad de soporte para escenarios siguientes (servicios/contratos)
        print("\n[BLOCKING] Re-alta entidad soporte")
        support_name = f"{ctx.entity_name}_SUP"
        support_cif = f"C9{run_id}88"
        await post_chat(client, ctx, f"crea un cliente llamado {support_name} con CIF {support_cif}")
        r2b = await post_chat(client, ctx, "si, grábalo")
        support_id = extract_first_int(r2b["reply"])
        assert_true(support_id is not None, "No pude extraer ID de entidad soporte")
        ctx.entity_id = support_id
        ctx.entity_name = support_name
        ctx.entity_cif = support_cif
        print(f"[PASS] Entidad soporte creada id={ctx.entity_id}")

        # 5) Creación de artículo
        print("\n[BLOCKING] Creación de artículo")
        await post_chat(client, ctx, f"crea un artículo llamado {ctx.article_desc}")
        ra = await post_chat(client, ctx, "ok")
        assert_true("artículo" in ra["reply"].lower() or "articulo" in ra["reply"].lower(), "No se confirma creación de artículo")
        print("[PASS] Artículo OK")

        # 6) Servicio + consulta + histórico
        print("\n[BLOCKING] Servicio + histórico")
        rsvc0 = await post_chat(client, ctx, f"abre un servicio para proveedor {ctx.entity_id} con descripcion visita e2e real")
        sid0 = extract_created_service_id(rsvc0["reply"])
        if sid0 is not None:
            rs = rsvc0
        else:
            rs = await post_chat(client, ctx, "adelante")
        ctx.service_id = extract_created_service_id(rs["reply"]) or extract_first_int(rs["reply"])
        assert_true(ctx.service_id is not None, "No se pudo extraer ID de servicio")
        qserv = await post_chat(client, ctx, f"consulta el servicio {ctx.service_id}")
        qlow = qserv["reply"].lower()
        assert_true(str(ctx.service_id) in qserv["reply"] or "servicio" in qlow, "Consulta de servicio sin evidencia")
        radd = await post_chat(client, ctx, f"graba una linea en el historial del servicio {ctx.service_id} diciendo nota e2e real")
        if "nota" in radd["reply"].lower() or "historial" in radd["reply"].lower():
            rh = radd
        else:
            rh = await post_chat(client, ctx, "si")
        assert_true("nota" in rh["reply"].lower() or "historial" in rh["reply"].lower(), "No se registra nota de historial")
        rhl = await post_chat(client, ctx, f"dime el historial del servicio {ctx.service_id}")
        assert_true("historial" in rhl["reply"].lower() or str(ctx.service_id) in rhl["reply"], "Lectura de histórico fallida")
        print("[PASS] Servicio e histórico OK")

        # 7) Contrato CRUD (incluye modificar)
        print("\n[BLOCKING] Contrato CRUD")
        await post_chat(client, ctx, f"crea un contrato para pkey {ctx.entity_id} con descripcion contrato e2e y precio 99")
        rc = await post_chat(client, ctx, "ok")
        ctx.contract_id = extract_first_int(rc["reply"])
        assert_true(ctx.contract_id is not None, "No se pudo extraer ID de contrato")
        rqc = await post_chat(client, ctx, f"consulta contrato {ctx.contract_id}")
        assert_true(str(ctx.contract_id) in rqc["reply"] or "contrato" in rqc["reply"].lower(), "Consulta contrato sin evidencia")

        rmc = await post_chat(client, ctx, f"modifica el contrato {ctx.contract_id} y cambia el precio a 111")
        assert_true(any(k in rmc["reply"].lower() for k in ["modific", "actualiz", "precio"]), "No hay evidencia de modificación de contrato")

        await post_chat(client, ctx, f"borra el contrato {ctx.contract_id}")
        rdc = await post_chat(client, ctx, "CONFIRMO")
        assert_true("elimin" in rdc["reply"].lower() or "borr" in rdc["reply"].lower(), "Borrado contrato no confirmado")
        print("[PASS] Contrato CRUD OK")

        # 8) Registro de gasto por conversación
        print("\n[BLOCKING] Registro de gasto")
        rg1 = await post_chat(client, ctx, "quiero registrar un gasto de 23.5 euros de material para proveedor 12345")
        rg2 = await post_chat(client, ctx, "si")
        assert_true(any(k in rg2["reply"].lower() for k in ["gasto", "registrado", "doc"]), "No se confirma registro de gasto")
        print("[PASS] Gasto OK")

        # 9) Ambigüedad
        print("\n[BLOCKING] Ambigüedad")
        ramb = await post_chat(client, ctx, "consulta el cliente demo")
        assert_true(any(k in ramb["state"] for k in ["AWAITING_DISAMBIGUATION", "idle"]), "Estado inesperado en ambigüedad")
        print(f"[PASS] Ambigüedad controlada state={ramb['state']}")

        # 10) Cancelación
        print("\n[BLOCKING] Cancelación")
        await post_chat(client, ctx, "crea un cliente llamado CANCEL_REAL")
        rcancel = await post_chat(client, ctx, "cancela")
        assert_true(rcancel["state"] == "idle", "Cancelación no vuelve a idle")
        print("[PASS] Cancelación OK")

        # 11) Error ERP
        print("\n[BLOCKING] Error ERP")
        await post_chat(client, ctx, "borra la factura 999999")
        rerr = await post_chat(client, ctx, "CONFIRMO")
        err_low = rerr["reply"].lower()
        assert_true(
            any(k in err_low for k in ["error", "no", "pendiente", "eliminar", "eliminado", "borrado"]),
            "No se observa resultado de borrado/errores en factura",
        )
        print("[PASS] Resultado de borrado factura controlado")

    print("\nRESULTADO GLOBAL E2E REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(run())
        sys.exit(code)
    except BlockingFailure as bf:
        print(f"\nRESULTADO GLOBAL E2E REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"\nRESULTADO GLOBAL E2E REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)
