"""
Auditoría READ-ONLY de serverIA para análisis de ecoFlow.

Garantías:
- Solo lecturas. Ningún comando modifica estado (no systemctl restart, no sed -i,
  no tar -c, no chmod, no kill).
- Acotado a paths /home/ecoflow + lectura de topología general (systemd, nginx, puertos).
- ecoBot y ecoFast solo se identifican, nunca se inspeccionan a fondo.
- Secretos del .env se enmascaran antes de imprimir.

Ejecución:
    python audit_serveria_readonly.py > audit_output.txt 2>&1

Después: pegarme audit_output.txt (o subirlo a la conversación).
"""

import paramiko
import hashlib
import os
import sys
import json
from datetime import datetime

# Forzar UTF-8 en stdout/stderr para que los caracteres unicode de systemctl
# (●, ✓, etc.) no revienten en Windows con cp1252.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'

# Ficheros clave para comparar local vs remoto (md5)
FILES_TO_CHECK = [
    'app/services/orchestrator.py',
    'app/services/orchestrator_routing.py',
    'app/services/cognitive_service.py',
    'app/services/response_service.py',
    'app/services/chat_service.py',
    'app/services/resolver.py',
    'app/services/normalizers.py',
    'app/services/conversational_logic.py',
    'app/api/routes_chat.py',
    'app/security/bearer_context.py',
    'app/core/config.py',
    'app/main.py',
    'requirements.txt',
]

# Claves .env cuyos valores enmascararemos
ENV_KEYS_SAFE_TO_PRINT = {
    "APP_NAME", "APP_VERSION", "DEBUG", "HOST", "PORT",
    "ECOSOFT_BASE_URL", "ECOSOFT_DEFAULT_SUCURSAL",
    "ECOSOFT_DEFAULT_GASTO_ARTICULO_REF",
    "MEDIA_BASE_PATH", "LOG_PATH",
    "AUTO_APPROVE_MAX_AMOUNT", "JOB_MAX_ATTEMPTS", "JOB_STALE_MINUTES",
    "ECOFLOW_ALLOW_DEV_BEARER_FALLBACK",
    "ECOFLOW_INTERNAL_CHAT_ALLOW_DEMO_ERP_TOKEN",
}


def header(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def get_md5_local(path):
    if not os.path.exists(path):
        return "MISSING_LOCAL"
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def run(client, cmd, timeout=15):
    """Ejecuta cmd remoto. Devuelve (stdout, stderr) como strings."""
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').rstrip()
    err = stderr.read().decode(errors='replace').rstrip()
    return out, err


def mask_env_value(key, value):
    if key in ENV_KEYS_SAFE_TO_PRINT:
        return value
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-3:]} (len={len(value)})"


def main():
    print(f"# Auditoría READ-ONLY de serverIA")
    print(f"# Generada: {datetime.now().isoformat()}")
    print(f"# Host: {HOST}  User: {USER}")

    # -------- LOCAL FIRST --------
    header("HASHES LOCALES (referencia)")
    local_hashes = {}
    for f in FILES_TO_CHECK:
        h = get_md5_local(f)
        local_hashes[f] = h
        print(f"  {h}  {f}")

    # -------- CONNECT --------
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"\n[Conectando a {HOST} ...]")
        client.connect(HOST, username=USER, password=PASS, timeout=20,
                       banner_timeout=20, auth_timeout=20)
    except Exception as e:
        print(f"!! ERROR de conexión: {e}")
        print("   Verifica que la VPN esté activa.")
        sys.exit(1)
    print("[Conexión OK]")

    # -------- 1. IDENTIDAD Y SALUD --------
    header("1. Identidad del servidor")
    for cmd, label in [
        ("hostname", "hostname"),
        ("hostname -I 2>/dev/null", "IPs"),
        ("uname -a", "kernel"),
        ("lsb_release -d 2>/dev/null || cat /etc/os-release | head -3", "OS"),
        ("uptime", "uptime"),
        ("date", "fecha servidor"),
        ("whoami", "usuario actual"),
    ]:
        out, _ = run(client, cmd)
        print(f"  [{label}] {out}")

    # -------- 2. RECURSOS --------
    header("2. Recursos")
    for cmd, label in [
        ("free -h", "memoria"),
        ("df -h /home / /var 2>/dev/null", "disco"),
        ("nproc", "cores"),
        ("loadavg=$(cat /proc/loadavg); echo $loadavg", "loadavg"),
    ]:
        out, _ = run(client, cmd)
        print(f"\n--- {label} ---\n{out}")

    # -------- 3. SERVICIOS systemd RELEVANTES --------
    header("3. Servicios systemd (ecoflow, ecobot, ecofast)")
    out, _ = run(client, "systemctl list-units --type=service --all --no-pager "
                         "| grep -Ei 'eco|nginx|postgres' || true")
    print(out)

    print("\n--- ecoflow status (sin tocar) ---")
    out, _ = run(client, "systemctl status ecoflow --no-pager -l 2>&1 | head -40")
    print(out)

    print("\n--- ecoflow.service file (read-only) ---")
    out, _ = run(client, "cat /etc/systemd/system/ecoflow.service 2>/dev/null "
                         "|| systemctl cat ecoflow --no-pager 2>/dev/null | head -50")
    print(out)

    # -------- 4. PUERTOS --------
    header("4. Puertos en escucha")
    out, _ = run(client, "ss -tlnp 2>/dev/null | head -40 || netstat -tlnp 2>/dev/null | head -40")
    print(out)

    # -------- 5. NGINX --------
    header("5. Nginx (configs sin modificar)")
    out, _ = run(client, "nginx -v 2>&1; echo '---'; "
                         "ls -la /etc/nginx/sites-enabled/ 2>/dev/null; echo '---'; "
                         "ls -la /etc/nginx/conf.d/ 2>/dev/null")
    print(out)
    print("\n--- vhost que contenga ecoflow ---")
    out, _ = run(client, "grep -lri 'ecoflow' /etc/nginx/ 2>/dev/null | head -10")
    print(out or "(ninguno encontrado)")
    out, _ = run(client, "for f in $(grep -lri 'ecoflow' /etc/nginx/ 2>/dev/null); "
                         "do echo \"### $f ###\"; cat \"$f\"; done | head -120")
    print(out)

    # -------- 6. ESTRUCTURA /home/ecoflow --------
    header("6. Estructura de /home/ecoflow")
    out, _ = run(client, "ls -la /home/ecoflow/ 2>/dev/null")
    print(out)
    print("\n--- /home/ecoflow/app (1 nivel) ---")
    out, _ = run(client, "ls -la /home/ecoflow/app/ 2>/dev/null")
    print(out)
    print("\n--- backups *.bak* y *.tar.gz en /home/ecoflow ---")
    out, _ = run(client, "find /home/ecoflow -maxdepth 3 -name '*.bak*' -o -name '*.tar.gz' 2>/dev/null | head -20")
    print(out or "(ninguno)")

    # -------- 7. VENV Y PYTHON --------
    header("7. Entorno Python de ecoflow")
    out, _ = run(client, "ls -la /home/ecoflow/venv/bin/python* 2>/dev/null; echo '---'; "
                         "/home/ecoflow/venv/bin/python --version 2>/dev/null; echo '---'; "
                         "/home/ecoflow/venv/bin/pip freeze 2>/dev/null | grep -Ei "
                         "'fastapi|httpx|openai|paramiko|sqlalchemy|asyncpg|pydantic|tenacity'")
    print(out)

    # -------- 8. .env REMOTO (enmascarado) --------
    header("8. .env de producción (enmascarado)")
    out, _ = run(client, "cat /home/ecoflow/.env 2>/dev/null")
    if not out:
        print("(no se pudo leer /home/ecoflow/.env)")
    else:
        for line in out.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                print(line)
                continue
            k, v = line.split("=", 1)
            print(f"{k}={mask_env_value(k.strip(), v.strip())}")

    # -------- 9. MODELO LLM EN CÓDIGO VIVO --------
    header("9. Modelo LLM configurado en código de producción")
    out, _ = run(client, "grep -nE '\"model\"\\s*:\\s*\"' "
                         "/home/ecoflow/app/services/cognitive_service.py "
                         "/home/ecoflow/app/services/response_service.py "
                         "/home/ecoflow/app/providers/openai_responses.py "
                         "/home/ecoflow/app/services/tools/extraer_documento.py 2>/dev/null")
    print(out)

    print("\n--- ¿se llama v4_analyze con contexto? ---")
    out, _ = run(client, "grep -n 'v4_analyze\\|parse_intent' "
                         "/home/ecoflow/app/services/orchestrator.py 2>/dev/null | head -10")
    print(out)

    print("\n--- ¿is_probable_listing está en el código vivo? ---")
    out, _ = run(client, "grep -n 'is_probable_listing\\|is_probable_query' "
                         "/home/ecoflow/app/services/orchestrator_routing.py 2>/dev/null")
    print(out)

    # -------- 10. HASHES REMOTOS vs LOCALES --------
    header("10. Diff código local vs producción (MD5)")
    print(f"  {'STATUS':<10} {'REMOTO':<34} {'LOCAL':<34} FICHERO")
    for f in FILES_TO_CHECK:
        remote_path = f"/home/ecoflow/{f}"
        out, _ = run(client, f"md5sum {remote_path} 2>/dev/null || echo 'MISSING_REMOTE'")
        remote_hash = out.split()[0] if out and out != "MISSING_REMOTE" else "MISSING_REMOTE"
        local_hash = local_hashes.get(f, "MISSING_LOCAL")
        if remote_hash == "MISSING_REMOTE":
            status = "REM-MISS"
        elif local_hash == "MISSING_LOCAL":
            status = "LOC-MISS"
        elif remote_hash == local_hash:
            status = "MATCH"
        else:
            status = "DIFF"
        print(f"  {status:<10} {remote_hash:<34} {local_hash:<34} {f}")

    # -------- 11. LOGS RECIENTES --------
    header("11. Logs recientes de ecoflow (últimas 80 líneas)")
    out, _ = run(client, "journalctl -u ecoflow --no-pager -n 80 2>/dev/null | tail -80")
    print(out)

    print("\n--- conteo de errores LLM en últimas 24h ---")
    out, _ = run(client, "journalctl -u ecoflow --since '24 hours ago' --no-pager 2>/dev/null "
                         "| grep -cE '404 Not Found|llm_error|llm_timeout|v4_packet: domain=unknown'")
    print(f"matches: {out}")

    print("\n--- últimos 3 errores 404/llm ---")
    out, _ = run(client, "journalctl -u ecoflow --since '24 hours ago' --no-pager 2>/dev/null "
                         "| grep -E '404 Not Found|llm_error|llm_timeout' | tail -3")
    print(out)

    # -------- 12. PROCESO Y CONSUMO --------
    header("12. Proceso ecoflow corriendo")
    out, _ = run(client, "ps -eo pid,etime,%cpu,%mem,cmd --sort=-%mem 2>/dev/null "
                         "| grep -iE 'ecoflow|uvicorn|gunicorn' | grep -v grep")
    print(out)

    # -------- 13. ÚLTIMA MODIFICACIÓN --------
    header("13. Fechas de modificación de ficheros clave en producción")
    out, _ = run(client, "stat -c '%y  %n' "
                         "/home/ecoflow/app/services/cognitive_service.py "
                         "/home/ecoflow/app/services/orchestrator.py "
                         "/home/ecoflow/app/services/orchestrator_routing.py "
                         "/home/ecoflow/.env 2>/dev/null")
    print(out)

    # -------- 14. ECOBOT / ECOFAST (solo identificar) --------
    header("14. ecoBot y ecoFast (solo identificación, sin inspeccionar a fondo)")
    out, _ = run(client, "systemctl status ecobot --no-pager -l 2>&1 | head -8")
    print("--- ecobot status ---")
    print(out)
    out, _ = run(client, "systemctl status ecofast --no-pager -l 2>&1 | head -8")
    print("\n--- ecofast status ---")
    print(out)
    out, _ = run(client, "ls -d /home/ecobot /home/ecofast 2>/dev/null; "
                         "ls -d /opt/ecobot /opt/ecofast 2>/dev/null")
    print("\n--- directorios ---")
    print(out)

    client.close()
    print(f"\n[Auditoría completada — {datetime.now().isoformat()}]")


if __name__ == "__main__":
    main()
