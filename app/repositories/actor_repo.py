from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.actor import Actor
from app.models.schemas.identity import ActorIdentity

async def get_or_create(db: AsyncSession, channel: str, user_id: str) -> ActorIdentity:
    import hashlib
    actor_id = hashlib.sha256(f"{channel}:{user_id}".encode()).hexdigest()
    result = await db.execute(select(Actor).where(Actor.actor_id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        actor = Actor(actor_id=actor_id, channel=channel, raw_user_id=user_id)
        db.add(actor)
        await db.flush()
    return ActorIdentity(
        actor_id=actor.actor_id,
        channel=actor.channel,
        raw_user_id=actor.raw_user_id,
        ecosoft_user_id=actor.ecosoft_user_id,
        ecosoft_sucursal=actor.ecosoft_sucursal,
        display_name=actor.display_name
    )
