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


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {
        "x-trace-id": f"contract-update-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    r = await client.post(
        CHAT_URL,
        data={"session_id": session_id, "message": message},
        headers=headers,
        timeout=40.0,
    )
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    data = r.json()
    assert_true("reply" in data and "state" in data, "Contrato de respuesta inválido")
    return data


async def run() -> int:
    run_id = str(int(time.time()))[-6:]
    session_id = f"srvctupd-{uuid.uuid4().hex[:8]}"
    entity_name = f"E2E_CONTR_{run_id}"
    entity_cif = f"B7{run_id}55"

    print(f"BASE_URL={BASE_URL}")
    print(f"SESSION={session_id}")

    async with httpx.AsyncClient() as client:
        print("\n[STEP] Alta entidad")
        await post_chat(client, session_id, f"crea un cliente llamado {entity_name} con CIF {entity_cif}")
        r_ent = await post_chat(client, session_id, "si, grábalo")
        entity_id = extract_first_int(r_ent["reply"])
        assert_true(entity_id is not None, "No se pudo extraer ID de entidad")
        print(f"[PASS] Entidad creada id={entity_id}")

        print("\n[STEP] Crear contrato")
        await post_chat(client, session_id, f"crea un contrato para pkey {entity_id} con descripcion contrato update e2e y precio 90")
        r_con = await post_chat(client, session_id, "ok")
        contract_id = extract_first_int(r_con["reply"])
        assert_true(contract_id is not None, f"No se pudo extraer ID de contrato. Reply={r_con['reply']}")
        print(f"[PASS] Contrato creado id={contract_id}")

        print("\n[STEP] Modificar contrato (preferencia REFERENCIA)")
        new_ref = f"REF_E2E_{run_id}"
        r_mod = await post_chat(client, session_id, f"modifica el contrato {contract_id} y cambia la referencia a {new_ref}")
        mod_low = r_mod["reply"].lower()
        assert_true("error" not in mod_low, f"Modificación devolvió error: {r_mod['reply']}")
        assert_true(any(k in mod_low for k in ["modific", "actualiz", "contrato"]), "Sin evidencia de modificación de contrato")
        print(f"[PASS] Respuesta modificación: {r_mod['reply']}")

        print("\n[STEP] Post-condición real por lectura")
        r_q = await post_chat(client, session_id, f"consulta contrato {contract_id}")
        q_low = r_q["reply"].lower()
        assert_true(new_ref.lower() in q_low, f"Post-condición fallida: referencia no actualizada. Reply={r_q['reply']}")
        print(f"[PASS] Lectura posterior refleja referencia={new_ref}")

        print("\n[STEP] Cleanup contrato")
        await post_chat(client, session_id, f"borra el contrato {contract_id}")
        r_del = await post_chat(client, session_id, "CONFIRMO")
        assert_true("elimin" in r_del["reply"].lower() or "borr" in r_del["reply"].lower(), "No se confirma borrado de contrato")
        print("[PASS] Cleanup contrato OK")

    print("\nRESULTADO GLOBAL CONTRACT UPDATE REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(run())
        sys.exit(code)
    except BlockingFailure as bf:
        print(f"\nRESULTADO GLOBAL CONTRACT UPDATE REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"\nRESULTADO GLOBAL CONTRACT UPDATE REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)
