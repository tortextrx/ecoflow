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
    headers = {"x-trace-id": f"human-stupid-service-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
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
    sid = f"hstsvc-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient() as client:
        m1 = "Ponle una tarea al operario Javier Play para que vaya a instalar el aire acondicionado al cliente Cristian ecoSoft. El lunes a las 10"
        r1 = await post_chat(client, sid, m1)
        assert_true(any(k in r1["state"] for k in ["AWAITING_SERVICE_CONFIRM", "AWAITING_DISAMBIGUATION"]), "Debe abrir flujo servicio")

        r2 = await post_chat(client, sid, "Sí")
        low2 = r2["reply"].lower()
        assert_true("necesito operario" not in low2, "No debe buclear pidiendo operario")

        if "grabo" in low2 or "nuevo servicio" in low2:
            r3 = await post_chat(client, sid, "sí")
        else:
            r3 = r2

        low3 = r3["reply"].lower()
        assert_true(any(k in low3 for k in ["servicio", "creado"]), "Debe crear servicio")
        sid_created = extract_service_id(r3["reply"])
        assert_true(sid_created is not None, "Debe devolver id de servicio")

        r4 = await post_chat(client, sid, f"consulta el servicio {sid_created}")
        low4 = r4["reply"].lower()
        assert_true(str(sid_created) in r4["reply"] or "servicio" in low4, "Roundtrip lectura de servicio")

    print("RESULTADO HUMAN STUPID SERVICE REAL: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO HUMAN STUPID SERVICE REAL: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO HUMAN STUPID SERVICE REAL: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

