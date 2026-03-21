from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.operation import Operation
from app.models.schemas.identity import OperationContext

async def get_active(db: AsyncSession, conversation_id: UUID) -> OperationContext | None:
    result = await db.execute(
        select(Operation).where(
            Operation.conversation_id == conversation_id,
            Operation.status.in_(["collecting", "confirming", "executing"])
        )
    )
    op = result.scalar_one_or_none()
    if op:
        return OperationContext(
            operation_id=op.operation_id,
            conversation_id=op.conversation_id,
            intent_name=op.intent_name,
            status=op.status,
            domain_command=op.domain_command,
            last_response_id=op.last_response_id,
            created_at=op.created_at,
            completed_at=op.completed_at
        )
    return None

async def create(db: AsyncSession, conversation_id: UUID, intent_name: str, domain_command: dict) -> OperationContext:
    op = Operation(
        conversation_id=conversation_id,
        intent_name=intent_name,
        domain_command=domain_command
    )
    db.add(op)
    await db.flush()
    return OperationContext(
        operation_id=op.operation_id,
        conversation_id=op.conversation_id,
        intent_name=op.intent_name,
        status=op.status,
        domain_command=op.domain_command,
        last_response_id=op.last_response_id,
        created_at=op.created_at,
        completed_at=op.completed_at
    )

async def update_doc(db: AsyncSession, op: OperationContext):
    await db.execute(
        update(Operation)
        .where(Operation.operation_id == op.operation_id)
        .values(
            status=op.status,
            domain_command=op.domain_command,
            last_response_id=op.last_response_id,
            completed_at=op.completed_at
        )
    )
