from pydantic import BaseModel
from typing import Literal, Optional

class ExtractionSchema(BaseModel):
    raw_fields: dict
    confidence: dict
    source: Literal["text", "image", "pdf", "audio"]
    extraction_model: str
