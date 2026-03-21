import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import actor_repo, conversation_repo
from app.models.schemas.identity import ActorIdentity, ConversationContext

logger = logging.getLogger("ecoflow")

class IdentityResolver:
    async def resolve(self, db: AsyncSession, channel: str, user_id: str) -> tuple[ActorIdentity, ConversationContext]:
        actor = await actor_repo.get_or_create(db, channel, user_id)
        conv = await conversation_repo.get_active(db, actor.actor_id)
        if not conv:
            conv = await conversation_repo.create(db, actor.actor_id)
            logger.info(f"new_conversation_created actor={actor.actor_id} conv={conv.conversation_id}")
        else:
            await conversation_repo.touch(db, conv.conversation_id)
        return actor, conv
