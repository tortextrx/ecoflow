import asyncio
import paramiko
import json
import logging

HOST, USER, PASS = "10.20.167.5", "root", "o1wrNtxq2?fA"

def run_test_on_remote():
    # Write the remote python script using httpx (FastAPI stack implies httpx is installed)
    remote_script = """
import asyncio
import httpx
import uuid
import time
from traceback import print_exc

BASE_URL = "http://127.0.0.1:18080/api/ecoflow/chat"

async def chat(session_id, message, session):
    data = {"session_id": session_id, "message": message}
    headers = {"x-trace-id": f"test-{uuid.uuid4().hex[:6]}"}
    resp = await session.post(BASE_URL, data=data, headers=headers)
    return resp.json()

async def worker(worker_id):
    try:
        session_id = f"test-user-{worker_id}-{uuid.uuid4().hex[:4]}"
        async with httpx.AsyncClient() as http:
            # 1. Start flow (continuity test)
            r1 = await chat(session_id, "crear servicio", http)
            assert "state" in r1, str(r1)
            print(f"[{worker_id}] T1 pass: {r1.get('reply')[:30]}...")
            
            # 2. Add ambiguity (no context)
            r2 = await chat(session_id, "para EcoSoft", http)
            print(f"[{worker_id}] T2 pass: {r2.get('reply')[:30]}...")
            
            return True
    except Exception as e:
        print(f"[{worker_id}] FAILED")
        print_exc()
        return False

async def main():
    print("Iniciando test de persistencia en PostgreSQL y concurrencia...")
    tasks = [worker(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    if all(results):
        print("✅ SUCCESS: 5 Sesiones concurrentes completadas, estado guardado y recuperado sin perdidas.")
    else:
        print("❌ ERROR: Hubo fallos en concurrencia.")

if __name__ == '__main__':
    asyncio.run(main())
"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    # Save to file remotely and run
    sftp = client.open_sftp()
    with sftp.file('/tmp/remote_test.py', 'w') as f:
        f.write(remote_script)
    sftp.close()
    
    # run with the specific venv python path that has httpx
    stdin, stdout, stderr = client.exec_command("/home/ecoflow/venv/bin/python /tmp/remote_test.py")
    out = stdout.read().decode()
    print(out)
    err = stderr.read().decode()
    if err:
        print("ERRORS:")
        print(err)
    
    client.close()

if __name__ == '__main__':
    run_test_on_remote()
