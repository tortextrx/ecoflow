import asyncio
from app.security.bearer_context import extract_and_validate_bearer, AuthContext
from app.core.config import settings
from fastapi import HTTPException

# Mock settings for test
settings.ecoflow_security_token = "SEC_TOKEN_123"
settings.ecoflow_internal_chat_allow_demo_erp_token = True
settings.ecoflow_internal_chat_demo_erp_token = "ERP_TOKEN_DEMO"

async def test_logic():
    print("--- Test A: Válido (Security + ERP) ---")
    try:
        ctx = await extract_and_validate_bearer(
            authorization="Bearer SEC_TOKEN_123",
            x_ecosoft_authorization="Bearer ERP_REAL_TOKEN"
        )
        print(f"PASS: {ctx}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n--- Test B: Security Incorrecto ---")
    try:
        await extract_and_validate_bearer(
            authorization="Bearer WRONG",
            x_ecosoft_authorization="Bearer ERP_REAL_TOKEN"
        )
    except HTTPException as e:
        print(f"PASS: 401 expected, got {e.status_code}")

    print("\n--- Test C: Sin ERP (Fallback Activo) ---")
    try:
        ctx = await extract_and_validate_bearer(
            authorization="Bearer SEC_TOKEN_123",
            x_ecosoft_authorization=None
        )
        print(f"PASS: Context using fallback: {ctx.ecosoft_authorization_raw}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n--- Test D: Sin ERP (Fallback Inactivo) ---")
    settings.ecoflow_internal_chat_allow_demo_erp_token = False
    try:
        await extract_and_validate_bearer(
            authorization="Bearer SEC_TOKEN_123",
            x_ecosoft_authorization=None
        )
    except HTTPException as e:
        print(f"PASS: 400 expected, got {e.status_code}")

if __name__ == "__main__":
    asyncio.run(test_logic())
