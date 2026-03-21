import asyncio
import httpx
import uuid
from traceback import print_exc

BASE_URL = "http://10.20.167.5:18080/api/ecoflow/chat"

async def chat(session_id, message, session):
    data = {"session_id": session_id, "message": message}
    headers = {"x-trace-id": f"test-multi-{uuid.uuid4().hex[:6]}"}
    resp = await session.post(BASE_URL, data=data, headers=headers, timeout=20.0)
    return resp.json()

async def test_multiturn():
    session_id = f"tester-{uuid.uuid4().hex[:6]}"
    print(f"🚀 Iniciando Test Multi-Turno en Session: {session_id}")
    
    async with httpx.AsyncClient() as http:
        # Step 1: Iniciar alta cliente
        print("1. Intención de alta...")
        r1 = await chat(session_id, "Quiero dar de alta a un cliente nuevo", http)
        print(f"R1: {r1.get('reply')}")
        assert "nombre" in r1.get("reply").lower()

        # Step 2: Dar nombre con ambigüedad
        print("2. Dando nombre EcoSoft (debe fallar la ambigüedad si hay varios o pedir CIF)...")
        r2 = await chat(session_id, "Se llama EcoSoft", http)
        print(f"R2: {r2.get('reply')}")
        assert "cif" in r2.get("reply").lower()

        # Step 3: Dar CIF
        print("3. Dando CIF y confirmando...")
        r3 = await chat(session_id, "CIF B12345678", http)
        print(f"R3: {r3.get('reply')}")
        
        # Step 4: Confirmar (Sí)
        r4 = await chat(session_id, "si, graba", http)
        print(f"R4: {r4.get('reply')}")
        assert "✅" in r4.get("reply") or "ID" in r4.get("reply")

        # Step 5: Crear Servicio usando contexto (last_resolved_entity)
        print("5. Crear servicio para este mismo cliente (contextual)...")
        r5 = await chat(session_id, "ahora crea un servicio para el", http)
        print(f"R5: {r5.get('reply')}")
        assert "trabajo" in r5.get("reply").lower() or "hacer" in r5.get("reply").lower()

        # Step 6: Dar descripción corta (debe rebotar)
        print("6. Descripción genérica (debe fallar)...")
        r6 = await chat(session_id, "revisar", http)
        print(f"R6: {r6.get('reply')}")
        assert "especifica" in r6.get("reply").lower() or "detalle" in r6.get("reply").lower()

        # Step 7: Dar descripción real
        print("7. Descripción real...")
        r7 = await chat(session_id, "Reparar fuga de agua en el baño principal de la oficina", http)
        print(f"R7: {r7.get('reply')}")
        assert "📋" in r7.get("reply")

        # Step 8: Finalizar
        print("8. Finalizar...")
        r8 = await chat(session_id, "adelante", http)
        print(f"R8: {r8.get('reply')}")
        assert "✅" in r8.get("reply")

if __name__ == "__main__":
    asyncio.run(test_multiturn())
