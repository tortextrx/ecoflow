import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Operation(Base):
    __tablename__ = "operations"
    operation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    intent_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="collecting")
    domain_command: Mapped[dict] = mapped_column(JSON, default=dict)
    last_response_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
