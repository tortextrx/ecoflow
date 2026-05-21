
import httpx
import json

URL = "http://127.0.0.1:18080/api/ecoflow/chat"
session = "e2e_final_v4"

def talk(msg):
    data = {
        "session_id": session,
        "message": msg
    }
    resp = httpx.post(URL, data=data, headers={"X-Ecoflow-Test-Mode": "raw"}, timeout=30.0)
    print(f"\nU: {msg}")
    try:
        data = resp.json()
        print(f"B: {data.get('reply')}")
        print(f"S: {data.get('state')}")
        return data
    except:
        print(f"Error: {resp.text}")
        return None

if __name__ == "__main__":
    talk("Nuevo servicio para 'Maria Cuesta', cliente 'Cristian ecoSoft', instalar aire el viernes a las 12")
    # Si Cristian ecoSoft es único y Maria Cuesta es única (o si usamos IDs), no debería haber ambigüedad.
    # Pero si la hay, ajustamos los turnos.
    # Usemos nombres que suelen ser únicos en este ERP de prueba.
    talk("Si") # Confirmación final
