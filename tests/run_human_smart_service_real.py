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
    headers = {"x-trace-id": f"human-smart-service-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Contrato chat inválido")
    return d


def extract_service_id(text: str):
    m = re.search(r"servicio\s+(\d{3,8})", (text or "").lower())
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{3,8})\b", text or "")
    return int(m.group(1)) if m else None


async def run() -> int:
    sid = f"hsmartsvc-{uuid.uuid4().hex[:8]}"
    msg = "Ponle una tarea al operario Javier Play para que vaya a instalar el aire acondicionado al cliente Cristian ecoSoft el lunes a las 10"
    async with httpx.AsyncClient() as client:
        r1 = await post_chat(client, sid, msg)
        low1 = r1["reply"].lower()
        assert_true(any(k in low1 for k in ["grabo", "nuevo servicio", "operario", "servicio"]), "Debe entender frase completa")

        r2 = await post_chat(client, sid, "sí")
        low2 = r2["reply"].lower()
        assert_true("necesito operario" not in low2, "No debe volver a pedir operario")

        if "nuevo servicio" in low2 or "grabo" in low2:
            r3 = await post_chat(client, sid, "sí")
        else:
            r3 = r2

        sid_created = extract_service_id(r3["reply"])
        assert_true(sid_created is not None, "Debe devolver pkey de servicio")

        r4 = await post_chat(client, sid, f"consulta el servicio {sid_created}")
        assert_true(str(sid_created) in r4["reply"] or "servicio" in r4["reply"].lower(), "Roundtrip servicio")

    print("RESULTADO HUMAN SMART SERVICE REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO HUMAN SMART SERVICE REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO HUMAN SMART SERVICE REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

