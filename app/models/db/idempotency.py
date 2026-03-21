import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    key_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="seen")
    result_ref: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
