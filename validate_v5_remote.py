import paramiko

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

VALID_SEC = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
VALID_ERP = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lUpN8au+eneOkQ4IgVup8Q=="

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

def run_curl(name, headers, payload="session_id=v5_test&message=hola"):
    h_str = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
    cmd = f'curl -s -o /dev/null -w "%{{http_code}}" -X POST "http://127.0.0.1:18080/api/ecoflow/chat" {h_str} -d "{payload}"'
    _, stdout, _ = client.exec_command(cmd)
    res = stdout.read().decode().strip()
    print(f"[{name}] HTTP {res}")

print("--- Validando Contrato V5 en serverIA ---")

run_curl("Caso A: Todo Correcto", {
    "Authorization": f"Bearer {VALID_SEC}",
    "X-EcoSoft-Authorization": VALID_ERP
})

run_curl("Caso B: Security Token Incorrecto", {
    "Authorization": "Bearer TOKEN_MALO",
    "X-EcoSoft-Authorization": VALID_ERP
})

run_curl("Caso C: Sin ERP Token (Fallback Active)", {
    "Authorization": f"Bearer {VALID_SEC}"
})

print("\n--- Desactivando Fallback para Test D ---")
client.exec_command("sed -i 's/ALLOW_DEMO_ERP_TOKEN=true/ALLOW_DEMO_ERP_TOKEN=false/' /home/ecoflow/.env && systemctl restart ecoflow")
import time; time.sleep(2)

run_curl("Caso D: Sin ERP Token (Fallback Disabled)", {
    "Authorization": f"Bearer {VALID_SEC}"
})

print("\n--- Restaurando Fallback para Desarrollo ---")
client.exec_command("sed -i 's/ALLOW_DEMO_ERP_TOKEN=false/ALLOW_DEMO_ERP_TOKEN=true/' /home/ecoflow/.env && systemctl restart ecoflow")

client.close()
