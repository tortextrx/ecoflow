import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.20.167.5', username='root', password='o1wrNtxq2?fA')

url_internal = "http://127.0.0.1:18080/api/ecoflow/chat"
url_public = "https://ecobot.es/api/ecoflow/chat"

valid_bearer = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lUpN8au+eneOkQ4IgVup8Q=="

tests = [
    ("Caso A: Bearer válido", f'curl -s -w "\\nHTTP %{{http_code}}" -X POST "{url_internal}" -H "Authorization: Bearer {valid_bearer}" -F "session_id=audit_test_a" -F "message=hola"'),
    ("Caso B: token_auth incorrecto", f'curl -s -w "\\nHTTP %{{http_code}}" -X POST "{url_internal}" -H "Authorization: Bearer WRONG_TOKEN.lUpN8au+eneOkQ4IgVup8Q==" -F "session_id=audit_test_b" -F "message=hola"'),
    ("Caso C: Bearer mal formado", f'curl -s -w "\\nHTTP %{{http_code}}" -X POST "{url_internal}" -H "Authorization: Bearer malformedtoken" -F "session_id=audit_test_c" -F "message=hola"'),
    ("Caso D: Sin Authorization (Fallback activo)", f'curl -s -w "\\nHTTP %{{http_code}}" -X POST "{url_internal}" -F "session_id=audit_test_d" -F "message=hola"'),
    ("Caso E: Prueba pública", f'curl -s -k -w "\\nHTTP %{{http_code}}" -X POST "{url_public}" -H "Authorization: Bearer {valid_bearer}" -F "session_id=audit_test_e" -F "message=hola"')
]

for name, cmd in tests:
    print(f"--- {name} ---")
    _, stdout, stderr = client.exec_command(cmd)
    res = stdout.read().decode().strip()
    print(res)
    print("-" * 20)

client.close()
