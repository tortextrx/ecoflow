import logging, hmac
from typing import Optional
from dataclasses import dataclass
from fastapi import Header, HTTPException
import contextvars
from app.core.config import settings

logger = logging.getLogger("ecoflow")

@dataclass
class AuthContext:
    security_token_validated: bool
    ecosoft_authorization_raw: Optional[str]
    ecosoft_token_present: bool

auth_context_var: contextvars.ContextVar[Optional[AuthContext]] = contextvars.ContextVar("ecoflow_auth_context", default=None)

def _verify_security_token(incoming_token: str) -> bool:
    expected = settings.ecoflow_security_token
    if not expected:
        logger.warning("[SECURITY] ecoflow_security_token is EMPTY. Denying access by default.")
        return False
    return hmac.compare_digest(incoming_token.encode('utf-8'), expected.encode('utf-8'))

async def extract_and_validate_bearer(
    authorization: Optional[str] = Header(None),
    x_ecosoft_authorization: Optional[str] = Header(None)
) -> AuthContext:
    # 1. Validar Seguridad de Acceso (ecoFlow)
    if not authorization or not (authorization.lower().startswith("bearer ")):
        logger.warning("[SECURITY] Missing or invalid Authorization header format.")
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid ecoFlow security token.")
    
    security_token = authorization[7:].strip()
    if not _verify_security_token(security_token):
        logger.warning("[SECURITY] Invalid security token attempt.")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid ecoFlow security token.")

    # 2. Capturar Token Operativo (ecoSoftWEB)
    # Se trata como string opaca, conservando el 'Bearer ' si viene o tratándolo como el token crudo.
    raw_ecosoft = x_ecosoft_authorization
    
    # Fallback para Desarrollo Interno (Demo)
    if not raw_ecosoft:
        if settings.ecoflow_internal_chat_allow_demo_erp_token and settings.ecoflow_internal_chat_demo_erp_token:
            raw_ecosoft = settings.ecoflow_internal_chat_demo_erp_token
            logger.info("[AUTH] Using INTERNAL_CHAT demo ERP token fallback.")
        else:
            # En producción, si no hay token operativo, lanzamos 400 (Bad Request) 
            # porque la petición está incompleta para operar.
            logger.warning("[AUTH] Missing X-EcoSoft-Authorization header.")
            raise HTTPException(status_code=400, detail="Missing X-EcoSoft-Authorization header (ERP Context required).")

    ctx = AuthContext(
        security_token_validated=True,
        ecosoft_authorization_raw=raw_ecosoft,
        ecosoft_token_present=True
    )
    
    auth_context_var.set(ctx)
    
    # Safe logging
    safe_erp = f"{raw_ecosoft[:10]}...{raw_ecosoft[-5:]}" if len(raw_ecosoft) > 15 else "***"
    logger.info(f"[AUTH] Context established. ERP Token: {safe_erp}")
    
    return ctx
