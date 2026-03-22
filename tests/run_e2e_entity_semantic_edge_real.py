import asyncio
import os
import uuid
import httpx


BASE = os.getenv("ECOFLOW_BASE_URL", "https://ecobot.es")
CHAT_URL = f"{BASE.rstrip('/')}/api/ecoflow/chat"


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> dict:
    headers = {
        "x-trace-id": f"entity-semantic-edge-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    r = await client.post(CHAT_URL, data={"session_id": session_id, "message": message}, headers=headers, timeout=45.0)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


async def case_semantic_fields(client: httpx.AsyncClient) -> bool:
    sid = f"semantic-{uuid.uuid4().hex[:8]}"
    name = f"INSTALACIONES_MARTINEZ_{uuid.uuid4().hex[:4]}"
    cif = "78978978A"

    print(f"\n[CASE A] Campos semánticos conversación ({sid})")
    print(await post_chat(client, sid, "dar de alta entidad"))
    print(await post_chat(client, sid, name))
    r3 = await post_chat(client, sid, cif)
    print(r3)
    if "posibles duplicados" in (r3.get("reply", "").lower()):
        r3b = await post_chat(client, sid, "CONFIRMO NUEVA")
        print(r3b)
    print(await post_chat(client, sid, "La dirección es, calle falsa numero 10. En oviedo, asturias. El teléfono es 654654658"))
    r5 = await post_chat(client, sid, "El codigo postal es 33054. No tiene email")
    print(r5)

    if "confirmación" in (r5.get("reply", "").lower()):
        await post_chat(client, sid, "ok")

    qd = await post_chat(client, sid, f"dime la direccion del cliente {name}")
    qp = await post_chat(client, sid, f"dime el telefono del cliente {name}")
    qc = await post_chat(client, sid, f"dime el campo direccion del cliente {name}")
    qe = await post_chat(client, sid, f"dime el email del cliente {name}")
    print(qd)
    print(qp)
    print(qc)
    print(qe)

    d_ok = "calle falsa numero 10" in (qd.get("reply", "").lower())
    t_ok = "654654658" in (qp.get("reply", ""))
    email_not_blocking = "faltan" not in (r5.get("reply", "").lower())

    print(f"CASE_A_RESULT direccion_ok={d_ok} telefono_ok={t_ok} no_email_no_bloquea={email_not_blocking}")
    return d_ok and t_ok and email_not_blocking


async def case_natural_duplicate_confirm(client: httpx.AsyncClient) -> bool:
    sid = f"dup-natural-{uuid.uuid4().hex[:8]}"
    print(f"\n[CASE B] Confirmación natural duplicado ({sid})")

    print(await post_chat(client, sid, "dar de alta entidad"))
    r2 = await post_chat(client, sid, "Instalaciones Martinez")
    print(r2)
    r3 = await post_chat(client, sid, "Efectivamente, ya está dada de alta")
    print(r3)

    ok = ("no la doy de alta" in (r3.get("reply", "").lower())) or (r3.get("state") == "idle")
    print(f"CASE_B_RESULT natural_confirm_ok={ok}")
    return ok


async def run() -> int:
    async with httpx.AsyncClient() as client:
        a = await case_semantic_fields(client)
        b = await case_natural_duplicate_confirm(client)

    print("\nRESULTADO BINARIO GLOBAL:")
    print(f"- CASE A (campos semánticos): {'PASS' if a else 'FAIL'}")
    print(f"- CASE B (confirmación natural duplicado): {'PASS' if b else 'FAIL'}")

    if a and b:
        print("CASE_RESULT=PASS")
        return 0

    print("CASE_RESULT=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

