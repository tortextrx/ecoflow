import asyncio, os, sys
# Mock the trace context if needed
from app.connectors.base import ecoflow_trace_ctx
ecoflow_trace_ctx.set("test-maria")

from app.services.resolver import ResolverService
async def main():
    r = ResolverService()
    res = await r.resolve_entity(name="María", allowed_types=["USUARIO", "P_LABORAL"])
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
