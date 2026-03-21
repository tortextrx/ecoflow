import logging
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.chat_service import ChatService
from app.models.schemas.chat import ChatResponse

logger = logging.getLogger("ecoflow")
router = APIRouter()
chat_service = ChatService()

@router.post("/api/ecoflow/chat", response_model=ChatResponse)
async def chat(
    session_id: str = Form(...),
    message: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None)
):
    file_bytes = None
    filename = None
    if file and file.filename:
        file_bytes = await file.read()
        filename = file.filename
        logger.info(f"chat_upload session={session_id} file={filename} size={len(file_bytes)}")

    response = await chat_service.handle(
        session_id=session_id,
        message=message or "",
        file_bytes=file_bytes,
        filename=filename
    )
    return response
