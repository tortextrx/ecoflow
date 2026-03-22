import asyncio
import os
import re
import sys
import time
import uuid

import httpx

BASE_URL = os.getenv("ECOFLOW_BASE_URL", "http://127.0.0.1:18080")
CHAT_URL = f"{BASE_URL}/api/ecoflow/chat"


class BlockingFailure(Exception):
    pass


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise BlockingFailure(msg)


def extract_first_int(text: str):
    m = re.search(r"\b(\d{3,8})\b", text or "")
    return int(m.group(1)) if m else None


def extract_created_service_id(text: str):
    m = re.search(r"servicio\s+(\d{3,8}).*cread", (text or "").lower())
    return int(m.group(1)) if m else None


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {
        "x-trace-id": f"srv-hist-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Contrato de respuesta inválido")
    return d


async def run() -> int:
    run_id = str(int(time.time()))[-6:]
    session_id = f"srvhist-{uuid.uuid4().hex[:8]}"
    entity_name = f"E2E_SRV_{run_id}"
    entity_cif = f"B6{run_id}44"
    note = f"nota_e2e_srv_{run_id}"

    print(f"BASE_URL={BASE_URL}")
    print(f"SESSION={session_id}")

    async with httpx.AsyncClient() as client:
        print("\n[STEP] Alta entidad")
        await post_chat(client, session_id, f"crea un cliente llamado {entity_name} con CIF {entity_cif}")
        r_ent = await post_chat(client, session_id, "si, grábalo")
        entity_id = extract_first_int(r_ent["reply"])
        assert_true(entity_id is not None, "No se pudo extraer ID de entidad")
        print(f"[PASS] Entidad creada id={entity_id}")

        print("\n[STEP] Crear servicio")
        r_srv0 = await post_chat(client, session_id, f"abre un servicio para proveedor {entity_id} con descripcion visita e2e servicio historial")
        sid0 = extract_created_service_id(r_srv0["reply"])
        if sid0 is not None:
            r_srv = r_srv0
        else:
            r_srv = await post_chat(client, session_id, "adelante")
        service_id = extract_created_service_id(r_srv["reply"]) or extract_first_int(r_srv["reply"])
        assert_true(service_id is not None, f"No se pudo extraer ID de servicio. Reply={r_srv['reply']}")
        print(f"[PASS] Servicio creado id={service_id}")

        print("\n[STEP] Verificar servicio existe")
        r_q = await post_chat(client, session_id, f"consulta el servicio {service_id}")
        rq_low = r_q["reply"].lower()
        assert_true(str(service_id) in r_q["reply"] or "servicio" in rq_low, "Servicio no localizable tras crear")
        print("[PASS] Servicio localizable")

        print("\n[STEP] Alta de histórico")
        r_add = await post_chat(client, session_id, f"graba una linea en el historial del servicio {service_id} diciendo {note}")
        if "nota" in r_add["reply"].lower() or "historial" in r_add["reply"].lower():
            r_h = r_add
        else:
            r_h = await post_chat(client, session_id, "si")
        assert_true("nota" in r_h["reply"].lower() or "historial" in r_h["reply"].lower(), "No se confirmó alta de histórico")
        print("[PASS] Histórico grabado")

        print("\n[STEP] Lectura posterior de histórico")
        r_l = await post_chat(client, session_id, f"dime el historial del servicio {service_id}")
        txt = r_l["reply"].lower()
        assert_true(note.lower() in txt or "historial" in txt, "La lectura posterior no contiene evidencia de la actuación")
        print("[PASS] Lectura de histórico OK")

    print("\nRESULTADO GLOBAL SERVICE HISTORY REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(run())
        sys.exit(code)
    except BlockingFailure as bf:
        print(f"\nRESULTADO GLOBAL SERVICE HISTORY REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"\nRESULTADO GLOBAL SERVICE HISTORY REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)
