from __future__ import annotations

from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import httpx


ALLOWED_INTERNAL_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_INTERNAL_PORT = 18080


def normalize_internal_base_url(base_url: str, require_explicit: bool = True) -> Tuple[bool, str, str]:
    raw = (base_url or "").strip()
    if require_explicit and not raw:
        return False, "", "ECOFLOW_BASE_URL no está definida para modo internal_backend"
    if not raw:
        return False, "", "base_url vacío en modo internal_backend"

    parsed = urlparse(raw)
    if parsed.scheme.lower() != "http":
        return False, "", f"scheme inválido para internal_backend: {parsed.scheme or '(vacío)'}"

    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_INTERNAL_HOSTS:
        return False, "", f"host inválido para internal_backend: {host or '(vacío)'}"

    port = parsed.port or 80
    if port != EXPECTED_INTERNAL_PORT:
        return False, "", f"puerto inválido para internal_backend: {port} (esperado {EXPECTED_INTERNAL_PORT})"

    if parsed.path and parsed.path not in {"", "/"}:
        return False, "", f"base_url no debe incluir path en internal_backend: {parsed.path}"

    if parsed.query or parsed.params or parsed.fragment:
        return False, "", "base_url no debe incluir query/params/fragment en internal_backend"

    normalized = f"http://{host}:{EXPECTED_INTERNAL_PORT}"
    return True, normalized, ""


async def run_internal_backend_preflight(
    client: httpx.AsyncClient,
    base_url: str,
    chat_path: str,
    timeout: float,
    header_test_mode: str,
) -> Dict[str, Any]:
    root_url = f"{base_url.rstrip('/')}/"
    chat_url = f"{base_url.rstrip('/')}{chat_path}"

    result: Dict[str, Any] = {
        "endpoint_mode": "internal_backend",
        "target_base_url": base_url,
        "target_chat_url": chat_url,
        "status": "infra_preflight_fail",
        "ok": False,
        "checks": {
            "root": {"ok": False, "status_code": None, "error": None, "body_preview": ""},
            "chat": {"ok": False, "status_code": None, "error": None, "body_preview": ""},
        },
    }

    try:
        rr = await client.get(root_url, timeout=timeout)
        result["checks"]["root"]["status_code"] = rr.status_code
        result["checks"]["root"]["body_preview"] = (rr.text or "")[:300]
        root_json_ok = False
        try:
            rj = rr.json()
            root_json_ok = isinstance(rj, dict) and rj.get("service") == "ecoFlow"
        except Exception:
            root_json_ok = False
        result["checks"]["root"]["ok"] = rr.status_code == 200 and root_json_ok
        if not result["checks"]["root"]["ok"]:
            result["checks"]["root"]["error"] = "root inválido (status!=200 o payload no ecoFlow)"
    except Exception as exc:
        result["checks"]["root"]["error"] = repr(exc)

    try:
        rc = await client.post(
            chat_url,
            data={"session_id": "preflight_internal_backend", "message": "hola"},
            headers={"x-trace-id": "preflight-internal", "x-ecoflow-test-mode": header_test_mode},
            timeout=timeout,
        )
        result["checks"]["chat"]["status_code"] = rc.status_code
        result["checks"]["chat"]["body_preview"] = (rc.text or "")[:300]

        chat_ok = False
        if rc.status_code == 200:
            try:
                cj = rc.json()
                chat_ok = isinstance(cj, dict) and ("reply" in cj) and ("state" in cj)
            except Exception:
                chat_ok = False
        result["checks"]["chat"]["ok"] = chat_ok
        if not chat_ok:
            result["checks"]["chat"]["error"] = "chat inválido (status!=200 o sin reply/state)"
    except Exception as exc:
        result["checks"]["chat"]["error"] = repr(exc)

    result["ok"] = bool(result["checks"]["root"]["ok"] and result["checks"]["chat"]["ok"])
    result["status"] = "ok" if result["ok"] else "infra_preflight_fail"
    return result

