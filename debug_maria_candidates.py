import asyncio, os
from app.connectors.base import ecoflow_trace_ctx
ecoflow_trace_ctx.set("debug-maria-candidates")

from app.services.tools.registry import tool_registry

async def main():
    # Buscamos todas las Marias
    res = await tool_registry.listar_entidades.execute({"DENCOM": "%Maria%"})
    if not res.get("success"):
        print(f"Error: {res.get('error')}")
        return
        
    data = res.get("data", [])
    print(f"Found {len(data)} candidates for %Maria%")
    for it in data:
        print(f"- {it.get('DENCOM')} (PKEY {it.get('PKEY')}) - CLIENTE:{it.get('CLIENTE')} USUARIO:{it.get('USUARIO')} P_LABORAL:{it.get('P_LABORAL')}")

if __name__ == "__main__":
    asyncio.run(main())
