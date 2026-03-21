import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Job(Base):
    __tablename__ = "jobs"
    job_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    raw_message_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
