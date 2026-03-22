import asyncio
import os
import uuid
import httpx


BASE = os.getenv("ECOFLOW_BASE_URL", "https://ecobot.es")
CANDIDATE_CHAT_URLS = [
    f"{BASE.rstrip('/')}/api/ecoflow/chat",
    f"{BASE.rstrip('/')}/ecoflow-chat/api/ecoflow/chat",
]


async def try_post(client: httpx.AsyncClient, url: str, session_id: str, message: str) -> httpx.Response:
    headers = {
        "x-trace-id": f"entity-guided-real-{uuid.uuid4().hex[:8]}",
        "x-ecoflow-test-mode": "raw",
    }
    return await client.post(
        url,
        data={"session_id": session_id, "message": message},
        headers=headers,
        timeout=40.0,
    )


async def post_chat(client: httpx.AsyncClient, session_id: str, message: str) -> tuple[str, dict]:
    last_error = None
    for url in CANDIDATE_CHAT_URLS:
        try:
            r = await try_post(client, url, session_id, message)
            if r.status_code == 200:
                return url, r.json()
            last_error = f"{url} -> HTTP {r.status_code}"
        except Exception as ex:
            last_error = f"{url} -> {ex}"
    raise RuntimeError(f"No se pudo invocar chat real: {last_error}")


def looks_like_created(reply: str) -> bool:
    low = (reply or "").lower()
    return any(k in low for k in ["alta completada", "creado", "creada", "id ", "✅ alta"])


async def run() -> int:
    session_id = f"guided-{uuid.uuid4().hex[:10]}"
    unique = uuid.uuid4().hex[:6]
    unique_digits = "".join(ch for ch in uuid.uuid4().hex if ch.isdigit())[:6]
    name = f"GUIDED_REAL_{unique}"
    cif = f"B9{unique_digits[:4]}77"
    email = f"guided.{unique}@example.com"
    telefono = "600123123"
    direccion = "calle real 1"
    poblacion = "oviedo"
    provincia = "asturias"
    cp = "33001"

    print(f"SESSION={session_id}")
    print("Objetivo: verificar que tras nombre + CIF NO se crea automáticamente y entra en guiado/confirmación fuerte")

    async with httpx.AsyncClient() as client:
        url, r1 = await post_chat(client, session_id, "quiero dar de alta una entidad")
        print(f"URL={url}")
        print(f"1) reply={r1.get('reply')} | state={r1.get('state')}")

        _, r2 = await post_chat(client, session_id, name)
        print(f"2) reply={r2.get('reply')} | state={r2.get('state')}")

        _, r3 = await post_chat(client, session_id, cif)
        print(f"3) reply={r3.get('reply')} | state={r3.get('state')}")

        created_after_cif = looks_like_created(r3.get("reply", ""))

        # Camino esperado tras fix: sugerencia guiada o confirmación fuerte explícita
        guided_keywords = ["recomendado completar", "faltan", "confirmo incompleta"]
        guided_detected = any(k in (r3.get("reply", "").lower()) for k in guided_keywords)

        # Aportar datos recomendados para verificar que viajan a payload final
        _, r4 = await post_chat(
            client,
            session_id,
            f"direccion {direccion}, poblacion {poblacion}, provincia {provincia}, cp {cp}, telefono {telefono}, email {email}",
        )
        print(f"4) reply={r4.get('reply')} | state={r4.get('state')}")

        # Puede cerrar directamente o pedir confirmación final
        if looks_like_created(r4.get("reply", "")):
            r5 = r4
        else:
            _, r5 = await post_chat(client, session_id, "ok")
            print(f"5) reply={r5.get('reply')} | state={r5.get('state')}")

        # Verificación de persistencia de campos aportados
        _, rq_email = await post_chat(client, session_id, f"dime el email del cliente {name}")
        _, rq_tel = await post_chat(client, session_id, f"dime el telefono del cliente {name}")
        _, rq_dir = await post_chat(client, session_id, f"dime la direccion del cliente {name}")
        print(f"6) query email => {rq_email.get('reply')}")
        print(f"7) query telefono => {rq_tel.get('reply')}")
        print(f"8) query direccion => {rq_dir.get('reply')}")

        fields_saved = (
            email.lower() in (rq_email.get("reply", "").lower())
            and telefono in (rq_tel.get("reply", ""))
            and "calle" in (rq_dir.get("reply", "").lower())
        )

        # Flujo mínimo explícito en sesión independiente
        session_min = f"guided-min-{uuid.uuid4().hex[:8]}"
        name_min = f"GUIDED_MIN_{unique}"
        cif_min = f"C9{unique_digits[:4]}66"
        await post_chat(client, session_min, "quiero dar de alta una entidad")
        await post_chat(client, session_min, name_min)
        rmin3_url, rmin3 = await post_chat(client, session_min, cif_min)
        print(f"9) min-step3 reply={rmin3.get('reply')} | state={rmin3.get('state')} | url={rmin3_url}")
        _, rmin4 = await post_chat(client, session_min, "CONFIRMO INCOMPLETA")
        _, rmin5 = await post_chat(client, session_min, "ok")
        minimal_created = looks_like_created(rmin4.get("reply", "")) or looks_like_created(rmin5.get("reply", ""))
        print(f"10) min-step4 reply={rmin4.get('reply')} | state={rmin4.get('state')}")
        print(f"11) min-step5 reply={rmin5.get('reply')} | state={rmin5.get('state')}")

        print("\nRESULTADO BINARIO DEL CASO:")
        print(f"- Crea automáticamente tras CIF: {'SI' if created_after_cif else 'NO'}")
        print(f"- Entra en guiado/confirmación fuerte tras CIF: {'SI' if guided_detected else 'NO'}")
        print(f"- Guarda teléfono/email/dirección aportados: {'SI' if fields_saved else 'NO'}")
        print(f"- Alta mínima solo tras confirmación explícita: {'SI' if minimal_created else 'NO'}")

        if created_after_cif:
            print("CASE_RESULT=FAIL")
            return 1

        if not guided_detected:
            print("CASE_RESULT=FAIL")
            return 1

        if not fields_saved:
            print("CASE_RESULT=FAIL")
            return 1

        if not minimal_created:
            print("CASE_RESULT=FAIL")
            return 1

        print("CASE_RESULT=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

