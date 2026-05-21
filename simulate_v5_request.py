import paramiko
import json

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

# El contrato V5 desplegado requiere:
# Authorization: Bearer <ECOFLOW_SECURITY_TOKEN>
# X-EcoSoft-Authorization: Bearer <TOKEN_ECOSOFTWEB_PRUEBA>

SEC_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" # El configurado en .env
ERP_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.bKnh3ir8/zFu51pIXe1gyA=="

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# URL Interna (para evitar problemas de NAT/Hairpin en el servidor)
URL = "http://127.0.0.1:18080/api/ecoflow/chat"

print("--- Simulación de Petición Real (Contrato V5) ---")
print(f"URL: {URL}")

headers = {
    "Authorization": f"Bearer {SEC_TOKEN}",
    "X-EcoSoft-Authorization": f"Bearer {ERP_TOKEN}"
}

h_str = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
payload = "session_id=test_token_demo_002&message=hola"

cmd = f'curl -s -i -X POST "{URL}" {h_str} -d "{payload}"'

_, stdout, _ = client.exec_command(cmd)
full_res = stdout.read().decode().strip()

print("\n--- Respuesta del Servidor ---")
print(full_res)

print("\n--- Logs de Auditoría (serverIA) ---")
_, stdout, _ = client.exec_command('tail -n 10 /var/log/ecoflow/app.jsonl')
logs = stdout.read().decode().strip()
for line in logs.splitlines():
    if "[AUTH]" in line or "Context established" in line:
        print(line)

client.close()
