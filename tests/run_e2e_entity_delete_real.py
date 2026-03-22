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
        "x-trace-id": f"entity-delete-{uuid.uuid4().hex[:8]}",
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
    session_id = f"srvdel-{uuid.uuid4().hex[:8]}"
    entity_name = f"E2E_DEL_{run_id}"
    entity_cif = f"B7{run_id}55"

    print(f"BASE_URL={BASE_URL}")
    print(f"SESSION={session_id}")

    async with httpx.AsyncClient() as client:
        print("\n[STEP] Alta entidad")
        await post_chat(client, session_id, f"crea un cliente llamado {entity_name} con CIF {entity_cif}")
        r_confirm = await post_chat(client, session_id, "si, grábalo")
        entity_id = extract_first_int(r_confirm["reply"])
        assert_true(entity_id is not None, "No se extrajo ID de entidad")
        print(f"[PASS] Alta entidad id={entity_id}")

        print("\n[STEP] Consulta previa")
        r_pre = await post_chat(client, session_id, f"consulta el cliente {entity_name}")
        assert_true(entity_name.lower() in r_pre["reply"].lower() or str(entity_id) in r_pre["reply"], "No se confirma existencia previa")
        print("[PASS] Entidad existe antes de borrar")

        print("\n[STEP] Solicitud de borrado")
        r_init = await post_chat(client, session_id, f"borra la entidad {entity_id}")
        assert_true(r_init["state"] == "AWAITING_DELETE_CONFIRM", "No entró en AWAITING_DELETE_CONFIRM")
        assert_true("confirmo" in r_init["reply"].lower(), "No pidió confirmación estricta")
        print("[PASS] Borrado pendiente con confirmación")

        print("\n[STEP] CONFIRMO")
        r_conf = await post_chat(client, session_id, "CONFIRMO")
        assert_true(any(k in r_conf["reply"].lower() for k in ["elimin", "borr"]), "No se confirmó borrado")
        print(f"[PASS] Confirmación borrado: {r_conf['reply']}")

        print("\n[STEP] Lectura posterior")
        # Validación robusta: por nombre y por pkey
        r_post_name = await post_chat(client, session_id, f"consulta el cliente {entity_name}")
        r_post_id = await post_chat(client, session_id, f"consulta el cliente {entity_id}")
        post_text = (r_post_name["reply"] + "\n" + r_post_id["reply"]).lower()
        assert_true(
            any(k in post_text for k in ["no he encontrado", "no encuentro", "no existe", "ninguna entidad"]),
            "Post-condición fallida: entidad sigue siendo resoluble tras borrado",
        )
        print("[PASS] Post-condición de borrado OK")

    print("\nRESULTADO GLOBAL ENTITY DELETE REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(run())
        sys.exit(code)
    except BlockingFailure as bf:
        print(f"\nRESULTADO GLOBAL ENTITY DELETE REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"\nRESULTADO GLOBAL ENTITY DELETE REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)
