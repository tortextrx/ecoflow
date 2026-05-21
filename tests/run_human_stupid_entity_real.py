import asyncio
import os
import re
import sys
import uuid

import httpx

BASE_URL = os.getenv("ECOFLOW_BASE_URL", "http://127.0.0.1:18080")
CHAT_URL = f"{BASE_URL}/api/ecoflow/chat"


class BlockingFailure(Exception):
    pass


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise BlockingFailure(msg)


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {"x-trace-id": f"human-stupid-entity-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Contrato chat inválido")
    return d


def extract_first_int(text: str):
    m = re.search(r"\b(\d{3,8})\b", text or "")
    return int(m.group(1)) if m else None


async def run() -> int:
    sid = f"hstent-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient() as client:
        r1 = await post_chat(client, sid, "da de alta un cliente")
        assert_true("nombre" in r1["reply"].lower() or "cliente" in r1["reply"].lower(), "Debe iniciar recogida")

        r2 = await post_chat(client, sid, "Ecosoft Torpe SL")
        assert_true(any(k in r2["reply"].lower() for k in ["cif", "nif", "tipo"]), "Debe pedir datos faltantes")

        r3 = await post_chat(client, sid, "CIF B12345678 y no tiene email")
        assert_true(any(k in r3["reply"].lower() for k in ["confirm", "grabo", "alta"]), "Debe preparar confirmación")

        r4 = await post_chat(client, sid, "sí")
        assert_true(any(k in r4["reply"].lower() for k in ["alta", "completada", "id"]), "Debe completar alta")
        eid = extract_first_int(r4["reply"])
        assert_true(eid is not None, "Debe devolver id de entidad")

        r5 = await post_chat(client, sid, f"dime el email del cliente {eid}")
        low = r5["reply"].lower()
        assert_true(any(k in low for k in ["no tengo", "no registrado", "", "none", "vac"]), "Roundtrip email nulo/ausente esperado")

    print("RESULTADO HUMAN STUPID ENTITY REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO HUMAN STUPID ENTITY REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO HUMAN STUPID ENTITY REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

