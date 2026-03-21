from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Literal, Optional

class ActorIdentity(BaseModel):
    actor_id: str
    channel: str
    raw_user_id: str
    ecosoft_user_id: Optional[int] = None
    ecosoft_sucursal: int = 1
    display_name: Optional[str] = None

class ConversationContext(BaseModel):
    conversation_id: UUID
    actor_id: str
    started_at: datetime
    last_activity: datetime
    status: Literal["active", "idle", "completed", "error"]

class OperationContext(BaseModel):
    operation_id: UUID
    conversation_id: UUID
    intent_name: str
    status: Literal["collecting", "confirming", "executing", "done", "failed", "cancelled"]
    domain_command: dict
    last_response_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
