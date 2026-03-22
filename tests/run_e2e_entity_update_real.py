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
        "x-trace-id": f"entity-update-{uuid.uuid4().hex[:8]}",
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
    session_id = f"srvupd-{uuid.uuid4().hex[:8]}"
    entity_name = f"E2E_UPD_{run_id}"
    entity_cif = f"B8{run_id}66"
    new_email = f"entity.update.{run_id}@example.com"

    print(f"BASE_URL={BASE_URL}")
    print(f"SESSION={session_id}")

    async with httpx.AsyncClient() as client:
        print("\n[STEP] Alta de entidad")
        await post_chat(client, session_id, f"crea un cliente llamado {entity_name} con CIF {entity_cif}")
        r_confirm = await post_chat(client, session_id, "si, grábalo")
        assert_true("alta" in r_confirm["reply"].lower() or "completada" in r_confirm["reply"].lower(), "No se confirma alta")
        entity_id = extract_first_int(r_confirm["reply"])
        assert_true(entity_id is not None, "No se extrajo ID de entidad")
        print(f"[PASS] Entidad creada id={entity_id}")

        print("\n[STEP] Lectura previa de email")
        r_before = await post_chat(client, session_id, f"dime el email del cliente {entity_name}")
        before_email = r_before["reply"]
        print(f"[INFO] Email antes: {before_email}")

        print("\n[STEP] Modificación real de email")
        r_mod = await post_chat(client, session_id, f"modifica el cliente {entity_name} y pon email {new_email}")
        assert_true("error" not in r_mod["reply"].lower(), "Modificación devolvió error")
        assert_true(any(k in r_mod["reply"].lower() for k in ["modific", "actualiz", "entidad"]), "Sin evidencia de modificación")
        print(f"[PASS] Respuesta modificación: {r_mod['reply']}")

        print("\n[STEP] Lectura posterior y comparación")
        r_after = await post_chat(client, session_id, f"dime el email del cliente {entity_name}")
        after_reply = r_after["reply"].lower()
        assert_true(new_email.lower() in after_reply, "Post-condición fallida: email no actualizado en lectura posterior")
        assert_true(before_email.lower() != r_after["reply"].lower(), "No hay diferencia entre estado antes/después")
        print(f"[PASS] Post-condición OK email={new_email}")

        print("\n[STEP] Cleanup")
        await post_chat(client, session_id, f"borra la entidad {entity_id}")
        r_del = await post_chat(client, session_id, "CONFIRMO")
        if "elimin" in r_del["reply"].lower() or "borr" in r_del["reply"].lower():
            print("[PASS] Cleanup OK")
        else:
            print(f"[WARN] Cleanup no confirmado: {r_del['reply']}")

    print("\nRESULTADO GLOBAL ENTITY UPDATE REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(run())
        sys.exit(code)
    except BlockingFailure as bf:
        print(f"\nRESULTADO GLOBAL ENTITY UPDATE REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"\nRESULTADO GLOBAL ENTITY UPDATE REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)
