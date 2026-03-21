import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Conversation(Base):
    __tablename__ = "conversations"
    conversation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[str] = mapped_column(String(128), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="active")
