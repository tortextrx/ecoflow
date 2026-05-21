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
    headers = {"x-trace-id": f"c4-real-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    assert_true(r.status_code == 200, f"HTTP inesperado: {r.status_code}")
    d = r.json()
    assert_true("reply" in d and "state" in d, "Respuesta inválida")
    print(f"USER: {message}")
    print(f"BOT : {d.get('reply')}")
    return d


async def run() -> int:
    sid = f"c4real-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient() as client:
        # SAFE MODE: solo lectura + selección de contexto
        r1 = await post_chat(client, sid, "Dime las facturas de Demo")
        low1 = (r1.get("reply") or "").lower()
        assert_true(any(k in low1 for k in ["factura", "documento", "elige", "cliente", "no hay"]), "Debe enrutar a facturación")

        if r1.get("state") == "AWAITING_DISAMBIGUATION":
            r2 = await post_chat(client, sid, "1")
            low2 = (r2.get("reply") or "").lower()
            assert_true("seleccionado documento" in low2 or "documento" in low2, "Debe fijar documento activo")

        r3 = await post_chat(client, sid, "Dime las líneas de la factura activa")
        low3 = (r3.get("reply") or "").lower()
        assert_true(any(k in low3 for k in ["líneas", "lineas", "linea", "no hay líneas", "indica el documento"]), "Debe responder por ruta de líneas en solo lectura")

    print("RESULTADO C4 FACT REAL SERVERIA (SAFE MODE): PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except BlockingFailure as bf:
        print(f"RESULTADO C4 FACT REAL SERVERIA (SAFE MODE): FAIL (BLOCKING) -> {bf}")
        sys.exit(1)
    except Exception as e:
        print(f"RESULTADO C4 FACT REAL SERVERIA (SAFE MODE): FAIL (EXCEPTION) -> {e}")
        sys.exit(1)

