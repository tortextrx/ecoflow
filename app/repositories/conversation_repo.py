from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.conversation import Conversation
from app.models.schemas.identity import ConversationContext

async def get_active(db: AsyncSession, actor_id: str) -> ConversationContext | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.actor_id == actor_id,
            Conversation.status == "active"
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        return ConversationContext(
            conversation_id=conv.conversation_id,
            actor_id=conv.actor_id,
            started_at=conv.started_at,
            last_activity=conv.last_activity,
            status=conv.status,
            session_data=conv.session_data or {}
        )
    return None

async def create(db: AsyncSession, actor_id: str) -> ConversationContext:
    conv = Conversation(actor_id=actor_id, session_data={})
    db.add(conv)
    await db.flush()
    return ConversationContext(
        conversation_id=conv.conversation_id,
        actor_id=conv.actor_id,
        started_at=conv.started_at,
        last_activity=conv.last_activity,
        status=conv.status,
        session_data=conv.session_data
    )

async def touch(db: AsyncSession, conversation_id: UUID):
    await db.execute(
        update(Conversation)
        .where(Conversation.conversation_id == conversation_id)
        .values(last_activity=datetime.utcnow())
    )

async def update_session_data(db: AsyncSession, conversation_id: UUID, session_data: dict):
    await db.execute(
        update(Conversation)
        .where(Conversation.conversation_id == conversation_id)
        .values(session_data=session_data, last_activity=datetime.utcnow())
    )
