import paramiko
import hashlib
import os

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

FILES_TO_CHECK = [
    'app/services/orchestrator.py',
    'app/services/cognitive_service.py',
    'app/services/chat_service.py',
    'app/services/resolver.py',
    'app/api/routes_chat.py',
    'app/security/bearer_context.py'
]

def get_md5(path):
    if not os.path.exists(path):
        return "MISSING"
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

print("--- AUDITORIA LOCAL ---")
local_hashes = {}
for f in FILES_TO_CHECK:
    h = get_md5(f)
    local_hashes[f] = h
    print(f"{f}: {h}")

print("\n--- AUDITORIA REMOTA (serverIA) ---")
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    # 1. Identity & Service
    _, stdout, _ = client.exec_command("hostname")
    print(f"Hostname: {stdout.read().decode().strip()}")
    
    _, stdout, _ = client.exec_command("pwd")
    print(f"Working Dir (SSH root): {stdout.read().decode().strip()}")
    
    _, stdout, _ = client.exec_command("systemctl is-active ecoflow")
    print(f"Service status: {stdout.read().decode().strip()}")
    
    _, stdout, _ = client.exec_command("ss -tuln | grep 18080")
    print(f"Port 18080 status: {stdout.read().decode().strip()}")
    
    # 2. Files and Hashes
    print("\nHashes remotos (MD5):")
    for f in FILES_TO_CHECK:
        remote_path = f"/home/ecoflow/{f}"
        _, stdout, _ = client.exec_command(f"md5sum {remote_path} || echo 'MISSING'")
        out = stdout.read().decode().strip()
        print(f"{f}: {out}")
        
    # 3. Environment Variables
    print("\nVariables de Entorno (.env remota):")
    _, stdout, _ = client.exec_command("grep -E 'ECOSOFT_TOKEN_AUTH|ECOFLOW_DEV_BEARER|ECOFLOW_ALLOW_DEV_BEARER_FALLBACK' /home/ecoflow/.env")
    env_out = stdout.read().decode().strip()
    # Masking for safety in output but checking if they exist
    for line in env_out.split('\n'):
        if '=' in line:
            key, val = line.split('=', 1)
            masked = val[:3] + "..." + val[-3:] if len(val) > 6 else "***"
            print(f"{key}: {masked if val else 'EMPTY'}")
        else:
            print(f"Line: {line}")

    client.close()
except Exception as e:
    print(f"Error en auditoria remota: {e}")
