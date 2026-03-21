from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    session_id: str
    message: Optional[str] = ""

class ChatResponse(BaseModel):
    reply: str
    state: str = "idle"
    extracted_data: Optional[dict] = None
    erp_result: Optional[dict] = None
