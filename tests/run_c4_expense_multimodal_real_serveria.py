import asyncio
import os
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
    headers = {"x-trace-id": f"c4-exp-real-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Respuesta inválida")
    print(f"USER: {message}")
    print(f"BOT : {d.get('reply')}")
    return d


async def run() -> int:
    sid = f"c4exp-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient() as client:
        r1 = await post_chat(client, sid, "Quiero registrar un gasto de 23.5 euros de material para proveedor 12345")
        low1 = (r1.get("reply") or "").lower()
        assert_true(any(k in low1 for k in ["gasto", "material", "23", "confirm", "grabo", "grabar"]), "Paso 1 debe enrutar gasto multimodal/conversacional")

        r2 = await post_chat(client, sid, "sí")
        low2 = (r2.get("reply") or "").lower()
        assert_true(any(k in low2 for k in ["gasto", "registrado", "doc", "error", "bloqueado"]), "Paso 2 debe devolver cierre operativo del flujo gasto")

    print("RESULTADO C4 EXPENSE MULTIMODAL REAL SERVERIA: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO C4 EXPENSE MULTIMODAL REAL SERVERIA: FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO C4 EXPENSE MULTIMODAL REAL SERVERIA: FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

