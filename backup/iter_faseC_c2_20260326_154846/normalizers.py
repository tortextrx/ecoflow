import re
import unicodedata
from datetime import datetime
from typing import Optional


CONFIRM_WORDS = {"si", "sí", "ok", "vale", "correcto", "adelante", "graba", "hazlo", "esa", "esa misma"}
DENY_WORDS = {"no", "negativo", "incorrecto", "nope"}
CANCEL_WORDS = {"cancela", "cancelar", "olvida", "para", "deten", "detente", "aborta", "salir"}


def normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    nfd = unicodedata.normalize("NFD", t)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def normalize_cif_nif(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "").upper())


def normalize_phone(value: str) -> str:
    raw = str(value or "")
    has_plus = raw.strip().startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return f"+{digits}" if has_plus else digits


def normalize_cp(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) >= 5:
        return digits[:5]
    return digits


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def is_explicit_no_email(text: str) -> bool:
    t = normalize_text(text)
    patterns = [
        r"\bno\s+tiene\s+email\b",
        r"\bsin\s+email\b",
        r"\bno\s+tiene\s+correo\b",
        r"\bsin\s+correo\b",
        r"\bemail\s*:\s*ninguno\b",
    ]
    return any(re.search(p, t) for p in patterns)


def classify_short_user_act(text: str) -> str:
    t = normalize_text(text)
    if t in CONFIRM_WORDS:
        return "confirm"
    if t in DENY_WORDS:
        return "deny"
    if t in CANCEL_WORDS:
        return "cancel"
    return "unknown"


def looks_like_short_value(text: str, max_words: int = 4) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t.split()) > max_words:
        return False
    return bool(re.match(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,_\-]{2,}$", t))


def extract_service_datetime_text(message: str, fallback_entity_fecha: Optional[str] = None) -> str:
    if fallback_entity_fecha:
        return str(fallback_entity_fecha).strip()
    t = message or ""
    m = re.search(
        r"\b((?:lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)(?:\s+a\s+las\s+\d{1,2}(?::\d{2})?)?)\b",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return ""


def now_iso_local() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

