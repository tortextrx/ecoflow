import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.20.167.5', username='root', password='o1wrNtxq2?fA')

url = "http://127.0.0.1:18080/api/ecoflow/chat"

cmds = [
    ('Caso 1: Válido', f'curl -m 15 -s -w "\\nHTTP %{{http_code}}" -X POST "{url}" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lUpN8au+eneOkQ4IgVup8Q==" -F "session_id=test_1" -F "message=hola"'),
    ('Caso 2: Mal auth', f'curl -m 15 -s -w "\\nHTTP %{{http_code}}" -X POST "{url}" -H "Authorization: Bearer TOKEN_FALSO.lUpN8au+eneOkQ4IgVup8Q==" -F "session_id=test_2" -F "message=hola"'),
    ('Caso 3: Mal formato', f'curl -m 15 -s -w "\\nHTTP %{{http_code}}" -X POST "{url}" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" -F "session_id=test_3" -F "message=hola"'),
    ('Caso 4: Sin header (dev fallback)', f'curl -m 15 -s -w "\\nHTTP %{{http_code}}" -X POST "{url}" -F "session_id=test_4" -F "message=hola"')
]

for name, cmd in cmds:
    print(f'==== {name} ====')
    _, stdout, stderr = client.exec_command(cmd)
    res = stdout.read().decode()
    if res:
        print(res.strip() + "\\n")
    else:
        err = stderr.read().decode()
        print(f"ERR: {err}\\n")

client.close()
