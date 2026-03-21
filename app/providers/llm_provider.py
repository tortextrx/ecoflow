from typing import Protocol, Optional
from app.models.schemas.llm import LLMResponse, ModelHint

class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]],
        model_hint: ModelHint,
        **kwargs
    ) -> LLMResponse:
        ...
