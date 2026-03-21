from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db.event import ConversationEvent
from uuid import UUID

async def append(db: AsyncSession, session_id: str, event_type: str, payload: dict, conversation_id: UUID | None = None, versions: dict | None = None):
    evt = ConversationEvent(
        session_id=session_id,
        conversation_id=conversation_id,
        event_type=event_type,
        payload=payload,
        versions=versions or {}
    )
    db.add(evt)
    await db.flush()

async def get_conversation_events(db: AsyncSession, conversation_id: UUID, limit: int = 20) -> list[ConversationEvent]:
    result = await db.execute(
        select(ConversationEvent)
        .where(ConversationEvent.conversation_id == conversation_id)
        .order_by(ConversationEvent.timestamp.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
