import logging, uuid
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.chat_service import ChatService
from app.models.schemas.chat import ChatResponse

logger = logging.getLogger("ecoflow")
router = APIRouter()
chat_service = ChatService()

# 10 MB Max attachment size
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIMES = {"image/jpeg", "image/png", "application/pdf"}

@router.post("/api/ecoflow/chat", response_model=ChatResponse)
async def chat(
    session_id: str = Form(..., max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"),
    message: Optional[str] = Form("", max_length=1000),
    file: Optional[UploadFile] = File(None),
    x_trace_id: Optional[str] = Header(None, max_length=100)
):
    trace_id = x_trace_id or str(uuid.uuid4())
    
    file_bytes = None
    filename = None
    if file and file.filename:
        if file.content_type not in ALLOWED_MIMES:
            logger.warning({"action": "upload_rejected", "reason": "invalid_mime", "mime": file.content_type, "trace_id": trace_id})
            return ChatResponse(reply="Formato de archivo no soportado. Usa JPEG, PNG o PDF.")
            
        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            logger.warning({"action": "upload_rejected", "reason": "size_exceeded", "size": len(file_bytes), "trace_id": trace_id})
            return ChatResponse(reply="El archivo es demasiado grande (máximo 10MB).")
            
        filename = file.filename
        logger.info({"action": "chat_upload", "session": session_id, "file": filename, "size": len(file_bytes), "trace_id": trace_id})

    try:
        # Lógica principal delegada
        response = await chat_service.handle(
            session_id=session_id,
            message=message or "",
            file_bytes=file_bytes,
            filename=filename,
            trace_id=trace_id
        )
        return response
    except Exception as e:
        logger.error({"action": "global_unhandled_error", "trace_id": trace_id, "error_msg": str(e)}, exc_info=True)
        return ChatResponse(reply="He tenido un problema procesando tu petición. Por favor, inténtalo de nuevo en unos segundos.")
