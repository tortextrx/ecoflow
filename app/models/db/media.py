import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class MediaAsset(Base):
    __tablename__ = "media_assets"
    media_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[str] = mapped_column(String(128), index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_filename: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MediaExtractionCache(Base):
    __tablename__ = "media_extraction_cache"
    media_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(nullable=True)
    extraction_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extraction_model: Mapped[str] = mapped_column(String(128))
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
