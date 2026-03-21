import asyncio, httpx, uuid, json

async def chat(url, sid, msg):
    try:
        data = {'session_id': sid, 'message': msg}
        async with httpx.AsyncClient() as client:
            # La API usa multipart/form-data (Form(...))
            resp = await client.post(url, data=data, timeout=45.0)
            if resp.status_code != 200:
                return f"Error {resp.status_code}: {resp.text}"
            return resp.json().get('reply', 'No reply field')
    except Exception as e:
        return f"Exception: {str(e)}"

async def run():
    url = 'http://127.0.0.1:18080/api/ecoflow/chat'
    sid = 'test-' + uuid.uuid4().hex[:6]
    print(f'STARTING REAL FUNCTIONAL TEST (MULTIPART): {sid}\n')
    
    # 1. Crear Contrato
    print('--- 1. Intent: Create Contract (Collecting) ---')
    r = await chat(url, sid, 'Crea un contrato para EcoSoft S.L. por 120 euros de mantenimiento')
    print('BOT:', r, '\n')
    
    # 2. Confirmar
    print('--- 2. Intent: Confirm Execution ---')
    r = await chat(url, sid, 'si, adelante, grábalo')
    print('BOT:', r, '\n')
    
    # 3. Borrar (con doble confirmacion)
    print('--- 3. Intent: Delete Initiation (Safety Check) ---')
    r = await chat(url, sid, 'mira, mejor bórralo que este no era')
    print('BOT:', r, '\n')
    
    # 4. Confirmar borrado estricto
    print('--- 4. Intent: Double Confirm (Strict "CONFIRMO") ---')
    r = await chat(url, sid, 'CONFIRMO')
    print('BOT:', r, '\n')

if __name__ == "__main__":
    asyncio.run(run())
