import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.db import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_path=settings.log_path, debug=settings.debug)
    log = logging.getLogger("ecoflow")
    log.info(f"ecoflow_starting version={settings.app_version} port={settings.port}")
    
    # Init DB models (creates tables if missing)
    async with engine.begin() as conn:
        from app.models.db import (RawMessage, Actor, Conversation, Operation,
                                    ConversationEvent, MediaAsset, MediaExtractionCache,
                                    IdempotencyRecord, Job)
        await conn.run_sync(Base.metadata.create_all)
        
    log.info("ecoflow_ready (unified architecture)")
    yield
    await engine.dispose()
    log.info("ecoflow_shutdown")

app = FastAPI(title="ecoFlow", version=settings.app_version, lifespan=lifespan)

# Only active frontend route
from app.api.routes_chat import router as chat_router
app.include_router(chat_router)

_linux_static = Path("/home/ecoflow/app/static")
_local_static = Path(__file__).resolve().parent / "static"
_static_dir = _linux_static if _linux_static.exists() else _local_static
app.mount("/ecoflow-chat", StaticFiles(directory=str(_static_dir), html=True), name="chat")
app.mount("/api/ecoflow/static", StaticFiles(directory=str(_static_dir)), name="static_proxy")

@app.get("/")
async def root():
    return {"service": "ecoFlow", "version": settings.app_version, "status": "online", "arch": "unified-sync"}
