from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


PendingFieldGuess = Literal["operario", "cliente", "descripcion", "cif", "none"]
ConfidenceHint = Literal["high", "medium", "low"]


class CognitiveIntentOutput(BaseModel):
    """Contrato tipado mínimo para parseo de intención cognitiva.

    Mantiene compatibilidad con `parse_intent(...) -> dict` al serializarse con `model_dump()`.
    """

    model_config = ConfigDict(extra="ignore")

    intent: str = Field(default="unknown", min_length=1, max_length=64)
    entities: dict = Field(default_factory=dict)
    pending_field_guess: PendingFieldGuess = "none"
    confirm_signal: bool = False
    deny_signal: bool = False
    confidence_hint: ConfidenceHint = "medium"

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, value):
        if value is None:
            return "unknown"
        text = str(value).strip()
        return text or "unknown"

    @field_validator("entities", mode="before")
    @classmethod
    def ensure_entities_dict(cls, value):
        return value if isinstance(value, dict) else {}


def cognitive_output_json_schema() -> dict:
    """Schema JSON interno para auditoría y pruebas de contrato."""
    return CognitiveIntentOutput.model_json_schema()
