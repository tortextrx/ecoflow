import asyncio
import httpx
import uuid

async def test_error_path(url, sid, msg, desc, expected_status=200):
    try:
        data = {'session_id': sid, 'message': msg}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, timeout=15.0)
            
            status = resp.status_code
            if status == expected_status:
                print(f"[PASS] {desc} -> HTTP {status}")
            else:
                print(f"[FAIL] {desc} -> HTTP {status} (Expected {expected_status})")
                print("       Body:", resp.text[:200])
    except httpx.TimeoutException:
        print(f"[FAIL] {desc} -> Timeout")
    except Exception as e:
        print(f"[FAIL] {desc} -> Exception: {e}")

async def test_oversized_file(url, sid):
    desc = "Upload oversizd file (> 10MB)"
    try:
        data = {'session_id': sid, 'message': "Aquí va el doc"}
        # 11MB random data
        file_content = b"0" * (11 * 1024 * 1024)
        files = {'file': ('big.pdf', file_content, 'application/pdf')}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, files=files, timeout=15.0)
            jr = resp.json()
            if resp.status_code == 200 and "grande" in jr.get("reply", ""):
                print(f"[PASS] {desc} -> Rejected perfectly by FastAPI route")
            else:
                print(f"[FAIL] {desc} -> Unexpected: HTTP {resp.status_code} Body: {resp.text[:200]}")
    except Exception as e:
        print(f"[FAIL] {desc} -> Exception: {e}")

async def test_invalid_mime(url, sid):
    desc = "Upload invalid MIME (text/plain)"
    try:
        data = {'session_id': sid, 'message': "Lee esto"}
        files = {'file': ('script.sh', b"echo hack", 'text/plain')}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, files=files, timeout=15.0)
            jr = resp.json()
            if resp.status_code == 200 and "no soportado" in jr.get("reply", ""):
                print(f"[PASS] {desc} -> Rejected cleanly")
            else:
                print(f"[FAIL] {desc} -> HTTP {resp.status_code}")
    except Exception as e:
        print(f"[FAIL] {desc} -> Exception: {e}")


async def run_hardening_tests():
    url = 'http://127.0.0.1:18080/api/ecoflow/chat'
    # Generamos un ID seguro y uno malicioso
    safe_sid = 'test-' + uuid.uuid4().hex[:6]
    bad_sid = 'hack_123/../../etc/passwd'

    print("--- INICIANDO TESTS DE HARDENING ---\n")
    
    # 1. Test Session ID inválido (debe dar HTTP 422 por regex)
    await test_error_path(url, bad_sid, "hola", "Session ID inválido (Path traversal attempt)", expected_status=422)

    # 2. Test Mensaje gigante (>1000 chars)
    giant_msg = "A" * 1500
    await test_error_path(url, safe_sid, giant_msg, "Message len > 1000", expected_status=422)

    # 3. Test de archivos adjuntos prohibidos o gigantes
    await test_oversized_file(url, safe_sid)
    await test_invalid_mime(url, safe_sid)
    
    print("\n--- TESTS FINALIZADOS ---")

if __name__ == "__main__":
    asyncio.run(run_hardening_tests())
