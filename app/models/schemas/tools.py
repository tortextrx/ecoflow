from pydantic import BaseModel
from typing import Optional, Literal
from app.models.schemas.domain import DomainCommand

class ToolCall(BaseModel):
    tool_name: str
    domain_command: DomainCommand

class ToolResult(BaseModel):
    success: bool
    data: Optional[dict] = None
    error_message: Optional[str] = None
    needs_user_input: bool = False
    next_prompt: Optional[str] = None

class ExecutionMode(str):
    EXECUTE = "EXECUTE"
    ASK = "ASK"
    CONFIRM = "CONFIRM"
    BLOCK = "BLOCK"

class ActionPolicy(BaseModel):
    requires_confirmation: bool
    high_impact_fields: list[str]
    required_fields: list[str]
