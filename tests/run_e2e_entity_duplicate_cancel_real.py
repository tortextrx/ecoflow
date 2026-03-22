import asyncio
import os
import re
import uuid
import httpx


BASE = os.getenv("ECOFLOW_BASE_URL", "https://ecobot.es")
CHAT_URL = f"{BASE.rstrip('/')}/api/ecoflow/chat"


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {
        "x-trace-id": f"entity-dup-cancel-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    r = await client.post(
        CHAT_URL,
        data={"session_id": session_id, "message": message},
        headers=headers,
        timeout=40.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def extract_first_cif(text: str) -> str | None:
    m = re.search(r"\b([A-Z]?\d{7,9}[A-Z]?)\b", (text or "").upper())
    return m.group(1) if m else None


async def run() -> int:
    session_id = f"dup-cancel-{uuid.uuid4().hex[:10]}"
    print(f"SESSION={session_id}")

    async with httpx.AsyncClient() as client:
        r1 = await post_chat(client, session_id, "dar de alta entidad")
        print(f"1) {r1.get('reply')} | {r1.get('state')}")

        r2 = await post_chat(client, session_id, "Perico Delgado")
        print(f"2) {r2.get('reply')} | {r2.get('state')}")

        dup_name_ok = "posibles coincidencias por nombre" in (r2.get("reply", "").lower())

        r3 = await post_chat(client, session_id, "continuar")
        print(f"3) {r3.get('reply')} | {r3.get('state')}")

        # Intentar CIF existente extraído de la lista de duplicados mostrada
        cif = extract_first_cif(r2.get("reply", "")) or "B12345678"
        r4 = await post_chat(client, session_id, cif)
        print(f"4) {r4.get('reply')} | {r4.get('state')} | CIF={cif}")

        dup_cif_ok = any(
            k in (r4.get("reply", "").lower())
            for k in ["posibles duplicados", "riesgo de duplicado", "coincidencias"]
        )

        r5 = await post_chat(client, session_id, "cancela")
        print(f"5) {r5.get('reply')} | {r5.get('state')}")

        cancel_clean_ok = "operación cancelada" in (r5.get("reply", "").lower()) and "idle" not in (r5.get("reply", "").lower())

        print("\nRESULTADO BINARIO:")
        print(f"- Duplicado por nombre detectado: {'SI' if dup_name_ok else 'NO'}")
        print(f"- Duplicado por CIF bloquea creación directa: {'SI' if dup_cif_ok else 'NO'}")
        print(f"- Cancelación con mensaje limpio: {'SI' if cancel_clean_ok else 'NO'}")

        if dup_name_ok and dup_cif_ok and cancel_clean_ok:
            print("CASE_RESULT=PASS")
            return 0

        print("CASE_RESULT=FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

