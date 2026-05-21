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
    headers = {"x-trace-id": f"human-smart-entity-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Contrato chat inválido")
    return d


def extract_first_int(text: str):
    m = re.search(r"\b(\d{3,8})\b", text or "")
    return int(m.group(1)) if m else None


async def run() -> int:
    sid = f"hsmartent-{uuid.uuid4().hex[:8]}"
    msg = (
        "Da de alta la entidad ALBERTO GONZALEZ GONZALEZ SOCIEDAD ANONIMA, "
        "NIF 10905530B, Castilla y León, teléfono 981340300, email albertogonzalezgijon@hotmail.com"
    )
    async with httpx.AsyncClient() as client:
        r1 = await post_chat(client, sid, msg)
        assert_true(any(k in r1["reply"].lower() for k in ["confirm", "grabo", "alta", "cif"]), "Debe avanzar en flujo")

        r2 = await post_chat(client, sid, "sí")
        assert_true(any(k in r2["reply"].lower() for k in ["alta", "completada", "id"]), "Debe completar alta")
        eid = extract_first_int(r2["reply"])
        assert_true(eid is not None, "Debe devolver id")

        r3 = await post_chat(client, sid, f"dime el email del cliente {eid}")
        assert_true("albertogonzalezgijon@hotmail.com" in r3["reply"].lower(), "Roundtrip email exacto")

    print("RESULTADO HUMAN SMART ENTITY REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO HUMAN SMART ENTITY REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO HUMAN SMART ENTITY REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

