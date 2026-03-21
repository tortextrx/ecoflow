import uuid, hashlib
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional

class Attachment(BaseModel):
    attachment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["image", "pdf", "audio", "video", "other"]
    content_b64: Optional[str] = None
    url: Optional[str] = None
    mime_type: str = "application/octet-stream"
    original_filename: Optional[str] = None

class IncomingMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str = "generic"
    user_id: str
    text: Optional[str] = None
    attachments: list[Attachment] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    external_message_id: Optional[str] = None

    def get_external_id(self) -> str:
        return self.external_message_id or f"{self.channel}:{self.user_id}:{self.id}"

    def get_session_id(self) -> str:
        return hashlib.sha256(f"{self.channel}:{self.user_id}".encode()).hexdigest()[:32]

class SimulateRequest(BaseModel):
    channel: str = "generic"
    user_id: str = "test_user"
    text: Optional[str] = None
    attachments: list[Attachment] = []
