from uuid import UUID
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.raw_message import RawMessage

async def set_status(db: AsyncSession, raw_message_id: UUID, status: str):
    await db.execute(
        update(RawMessage)
        .where(RawMessage.id == raw_message_id)
        .values(processing_status=status)
    )
