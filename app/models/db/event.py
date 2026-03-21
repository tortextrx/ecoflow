import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    versions: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
