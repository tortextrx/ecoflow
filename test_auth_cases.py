import logging
import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

# Disable cognitive/orchestrator deeper calls by mocking ChatService during tests, 
# or just allow the error to bubble up if we only care about HTTP 400/401 vs 200 before those hit.
# Actually Auth is validated BEFORE ChatService, so we'll see 401/400. 
# If it passes auth, it might return 500 or 200 depending on downstream, 
# but Auth success means it reaches the body.
# We will intercept the route using a small trick or just observe status codes.

client = TestClient(app)

def run_tests():
    print("=== Corriendo Tests de Autenticación ecoFlow ===\n")
    
    # SETUP
    settings.ecoflow_allow_dev_bearer_fallback = False
    settings.ecoflow_dev_bearer = ""
    
    form_data = {"session_id": "test_auth_123", "message": "Hola"}

    # Caso A: Bearer válido
    print("▶ Caso A: Bearer Válido")
    h_a = {"Authorization": "Bearer MI_EMPRESA_123.USUARIO_OPE"}
    r_a = client.post("/api/ecoflow/chat", data=form_data, headers=h_a)
    # Auth pasa, podría llegar a 200 (o 500 porque no hay llm keys en local etc) pero seguro NO 400/401
    if r_a.status_code not in (401, 400):
        print(f"  [PASS] Request aceptada ({r_a.status_code})")
    else:
        print(f"  [FAIL] Retornó {r_a.status_code} - {r_a.text}")

    # Caso B: Header ausente (Producción)
    print("\n▶ Caso B: Header Ausente (Sin Fallback)")
    r_b = client.post("/api/ecoflow/chat", data=form_data)
    if r_b.status_code == 401:
        print(f"  [PASS] Bloqueo correcto ({r_b.status_code}) - {r_b.json()}")
    else:
        print(f"  [FAIL] Retornó {r_b.status_code} - no bloqueó")

    # Caso C: Bearer mal formado
    print("\n▶ Caso C: Bearer Mal Formado")
    bad_headers = [
        ("Bearer SIN_PUNTO", 400),
        ("SoloElToken.123", 401),
        ("Bearer .UsuarioSinDB", 400),
        ("Bearer DBSinUsuario.", 400),
        ("", 401)
    ]
    for auth_val, exp_status in bad_headers:
        r_c = client.post("/api/ecoflow/chat", data=form_data, headers={"Authorization": auth_val})
        if r_c.status_code == exp_status:
            print(f"  [PASS] '{auth_val}' -> {r_c.status_code} ({r_c.json()['detail']})")
        else:
            print(f"  [FAIL] '{auth_val}' retornó {r_c.status_code} en vez de {exp_status}")

    # Caso D: Fallback de desarrollo
    print("\n▶ Caso D: Fallback Dev Activado")
    settings.ecoflow_allow_dev_bearer_fallback = True
    settings.ecoflow_dev_bearer = "Bearer DEV_DB.DEV_USR"
    r_d = client.post("/api/ecoflow/chat", data=form_data)
    if r_d.status_code not in (401, 400):
        print(f"  [PASS] Pass por Fallback ({r_d.status_code})")
    else:
        print(f"  [FAIL] Fallback rechazado: {r_d.status_code} - {r_d.text}")

if __name__ == "__main__":
    run_tests()
