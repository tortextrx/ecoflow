import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


CASES = {
    "A1": [
        "Necesito el teléfono de un cliente",
        "El cliente se llama Cristian",
        "Quiero el teléfono de Cristian",
        "Si que está, se que está busca los cristian que hay en la base de datos y dimelos, después elegiré uno y me darás el teléfono",
        "Como va la cosa?",
        "El teléfono de Cristian ecoSoft",
        "Por qué antes no me lo dabas? Ves como si que estaba? es posible que haya varios cristian pero deberías haberme dicho las opciones disponibles",
        "Ese no es cristian",
    ],
    "B1": [
        "Dime el pkey del artículo tornillo",
        "Busca todos los artículos que empiecen por tornillo",
        "Dime el codigo del artículo tornillo del 10",
        "Ese es el nombre del artículo con ID 43223",
        "Hay algun artículo dado de alta en la base de datos?",
        "tornillo del 10",
        "La familia es la 3",
        "El proveedor es ferreteria real",
        "El proveedor existe en la base de datos",
    ],
    "C1": [
        "Dime los servicios o tareas asignadas al operario Javier Play",
        "Quiero saber los servicios asignados al operario Javier play",
        "Cristian ecoSoft",
        "Para Javier Play",
    ],
}


def post_form(url: str, fields: dict[str, str], trace_id: str) -> str:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "x-trace-id": trace_id,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def run_case(case_id: str) -> dict:
    turns = CASES[case_id]
    session_id = f"forensic_{case_id.lower()}_{int(time.time())}"
    base = "http://127.0.0.1:18080/api/ecoflow/chat"
    since = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    results = []
    for i, message in enumerate(turns, 1):
        trace_id = f"forensic-{case_id}-{i:02d}"
        item = {"turn": i, "trace_id": trace_id, "message": message}
        try:
            body = post_form(base, {"session_id": session_id, "message": message}, trace_id)
            item["response_raw"] = json.loads(body)
        except Exception as exc:
            item["error"] = str(exc)
        results.append(item)
        time.sleep(1.1)

    journal = subprocess.check_output(
        ["journalctl", "-u", "ecoflow", "--since", since, "--no-pager", "-o", "short-iso"],
        text=True,
        errors="replace",
    )
    return {"case_id": case_id, "session_id": session_id, "turns": results, "journal": journal}


if __name__ == "__main__":
    cid = (sys.argv[1] if len(sys.argv) > 1 else "A1").upper()
    if cid not in CASES:
        raise SystemExit(f"Unknown case: {cid}")
    print(json.dumps(run_case(cid), ensure_ascii=False, indent=2))
