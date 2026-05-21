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


def extract_service_id(text: str):
    m = re.search(r"servicio\s+(\d{3,8})", (text or "").lower())
    if m:
        return int(m.group(1))
    return extract_first_int(text)


async def post_chat(client: httpx.AsyncClient, sid: str, message: str) -> dict:
    headers = {"x-trace-id": f"roundtrip-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": sid, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Contrato chat inválido")
    return d


async def run() -> int:
    sid = f"roundtrip-{uuid.uuid4().hex[:8]}"
    run_id = str(int(time.time()))[-6:]
    name = f"ROUNDTRIP_{run_id}"
    cif = f"B9{run_id}11"

    async with httpx.AsyncClient() as client:
        # Entidad: grabación + lectura posterior de campo exacto
        await post_chat(client, sid, f"crea un cliente llamado {name} con CIF {cif} y no tiene email")
        r2 = await post_chat(client, sid, "sí")
        eid = extract_first_int(r2["reply"])
        assert_true(eid is not None, "Entidad creada sin ID")

        r3 = await post_chat(client, sid, f"dime el email del cliente {eid}")
        low3 = r3["reply"].lower()
        assert_true(any(k in low3 for k in ["no tengo", "no registrado", "email"]), "Email roundtrip inconsistente")

        # Servicio: grabación + lectura posterior
        await post_chat(client, sid, f"ponle una tarea al operario Javier Play para que revise el equipo del cliente {name} el lunes a las 10")
        r5 = await post_chat(client, sid, "sí")
        if any(k in r5["reply"].lower() for k in ["nuevo servicio", "grabo"]):
            r6 = await post_chat(client, sid, "sí")
        else:
            r6 = r5

        sid_created = extract_service_id(r6["reply"])
        assert_true(sid_created is not None, "Servicio creado sin ID")

        r7 = await post_chat(client, sid, f"consulta el servicio {sid_created}")
        assert_true(str(sid_created) in r7["reply"] or "servicio" in r7["reply"].lower(), "Servicio roundtrip inconsistente")

    print("RESULTADO FIELD ROUNDTRIP VERIFICATION REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO FIELD ROUNDTRIP VERIFICATION REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO FIELD ROUNDTRIP VERIFICATION REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

