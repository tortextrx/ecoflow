from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum

class ModelHint(str, Enum):
    CONVERSATION = "conversation"
    EXTRACTION = "extraction"
    RESPONSE_GEN = "response_gen"
    STT = "stt"

class LLMResponse(BaseModel):
    text: str
    tool_calls: list[dict] = []
    response_id: str
    tokens_used: int = 0
