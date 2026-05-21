
import json
import subprocess

def exec_remote(cmd):
    p = subprocess.run(["python", "tmp_serveria_exec.py", cmd], capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return {"error": p.stderr, "code": p.returncode}
    try:
        return json.loads(p.stdout)
    except:
        return {"raw": p.stdout}

def talk(session, msg):
    escaped_msg = msg.replace('"', '\\"')
    # Usar comillas simples para el cuerpo del JSON y evitar el infierno de los backslashes
    payload = json.dumps({"message": msg})
    escaped_payload = payload.replace('"', '\\"')
    cmd = f'curl -s -X POST http://127.0.0.1:18080/api/ecoflow/chat -H "Content-Type: application/json" -H "X-Session-Id: {session}" -d "{escaped_payload}"'
    res = exec_remote(cmd)
    if "stdout" in res:
        try:
            data = json.loads(res["stdout"])
            return data
        except:
            return {"reply": res["stdout"]}
    return res

if __name__ == "__main__":
    session = "e2e_packet_test"
    turns = [
        "Nuevo servicio para Cristian, operario Maria, instalar aire acondicionado el viernes a las 12",
        "3", # Seleccionar Cristian ecoSoft
        "Si" # Confirmar grabación
    ]
    
    for i, t in enumerate(turns):
        print(f"Turn {i+1}: {t}")
        r = talk(session, t)
        print(f"Bot: {r.get('reply')}")
        print(f"State: {r.get('state')}")
        print("-" * 20)
