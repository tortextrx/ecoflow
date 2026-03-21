import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Actor(Base):
    __tablename__ = "actors"
    actor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel: Mapped[str] = mapped_column(String(64))
    raw_user_id: Mapped[str] = mapped_column(String(512))
    ecosoft_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ecosoft_token_usuario: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ecosoft_sucursal: Mapped[int] = mapped_column(Integer, default=1)
    display_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
