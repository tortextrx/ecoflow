from pydantic import BaseModel
from uuid import UUID

class DomainCommand(BaseModel):
    intent_name: str
    operation_id: UUID
    fields: dict
    missing_required: list[str] = []
    missing_optional: list[str] = []
    ambiguous: list[str] = []
    is_complete: bool = False
    completion_score: float = 0.0
