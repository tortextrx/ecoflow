import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class RawMessage(Base):
    __tablename__ = "raw_messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_message_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(64))
    raw_actor_id: Mapped[str] = mapped_column(String(512))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")
