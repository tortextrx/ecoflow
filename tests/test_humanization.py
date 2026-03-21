import asyncio
import httpx
import uuid

BASE_URL = "http://127.0.0.1:18080/api/ecoflow/chat"

async def chat(session_id, message, session):
    data = {"session_id": session_id, "message": message}
    headers = {"x-trace-id": f"human-test-{uuid.uuid4().hex[:6]}"}
    print(f"\n👤 [Usuario]: {message}")
    resp = await session.post(BASE_URL, data=data, headers=headers, timeout=30.0)
    print(f"🤖 [ecoFlow]: {resp.json().get('reply')}")
    return resp.json()

async def test_humanization():
    session_id = f"tester-hum-{uuid.uuid4().hex[:6]}"
    print("🚀 Iniciando Test de Capa Conversacional (Humanization Layer)")
    print(f"Sesion: {session_id}")
    
    async with httpx.AsyncClient() as http:
        # Step 1: Queja + Intención
        await chat(session_id, "Buah, menudo coñazo. Quiero dar de alta a un cliente nuevo.", http)
        
        # Step 2: Saca el nombre pero con coloquialismo
        await chat(session_id, "Se llama Francisco Alegre, venga va apúntalo", http)
        
        # Step 3: Dar el dato pero corrigiendo al bot
        await chat(session_id, "No es un CIF eh, es NIF: 47059872D", http)
        
        # Step 4: Confirmar con exabrupto
        await chat(session_id, "Tira, grábalo ya y también pon en observaciones que es un cliente muy pesao", http)

if __name__ == "__main__":
    asyncio.run(test_humanization())
