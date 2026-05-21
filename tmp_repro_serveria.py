
import httpx
import json
import secrets

URL = "http://127.0.0.1:18080/api/ecoflow/chat"
session_id = f"repro_{secrets.token_hex(4)}"

TURNS = [
    "Da de alta una tarea para Maria, cliente Cristian, el viernes a las 12. Tarea: Instalar aire",
    "3",
    "5",
    "Si"
]

def talk():
    print(f"Reproduction Session: {session_id}")
    for i, msg in enumerate(TURNS, 1):
        print(f"\n--- Turn {i} ---")
        print(f"Message: {msg}")
        resp = httpx.post(URL, json={"message": msg}, headers={"X-Session-Id": session_id}, timeout=30.0)
        print(f"Status: {resp.status_code}")
        try:
            data = resp.json()
            print(f"Reply: {data.get('reply', 'No reply')}")
            print(f"State: {data.get('state', 'No state')}")
        except:
            print(f"Raw: {resp.text}")

if __name__ == "__main__":
    talk()
