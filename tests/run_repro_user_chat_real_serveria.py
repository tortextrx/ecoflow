import asyncio
import os
import uuid

import httpx

BASE_URL = os.getenv("ECOFLOW_BASE_URL", "http://127.0.0.1:18080")
CHAT_URL = f"{BASE_URL}/api/ecoflow/chat"


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {"x-trace-id": f"repro-{uuid.uuid4().hex[:8]}", "x-ecoflow-test-mode": "raw"}
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=40.0)
    d = r.json()
    print(f"USER: {message}")
    print(f"BOT : {d.get('reply')}")
    print("-")
    return d


async def main() -> None:
    sid = f"repro-{uuid.uuid4().hex[:8]}"
    msgs = [
        "Quiero dar de alta un cliente nuevo",
        "Pancho Villa",
        "3443344E",
        "La dirección es Calle Mexico, 7 33011 Oviedo",
        "El teléfono es 65225885",
        "el email es pancho@villa.com",
        "Ya los tienes todos",
        "Quiero dar de alta un contrato",
        "Si, Cristian ecoSoft",
        "Yo no soy Cristian, Cristian es el cliente",
        "Cristian",
        "Cristian ecoSoft",
    ]
    async with httpx.AsyncClient() as client:
        for m in msgs:
            await post_chat(client, sid, m)


if __name__ == "__main__":
    asyncio.run(main())

