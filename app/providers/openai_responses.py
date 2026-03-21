import logging
from typing import Optional
from openai import AsyncOpenAI
from app.models.schemas.llm import LLMResponse, ModelHint
from app.core.config import settings

logger = logging.getLogger("ecoflow")

class OpenAIResponsesProvider:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url="https://openrouter.ai/api/v1")
        self.default_model = "openai/gpt-4o-mini"

    def _get_model(self, hint: ModelHint) -> str:
        if hint == ModelHint.EXTRACTION:
            return "openai/gpt-4o"
        return self.default_model

    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        model_hint: ModelHint = ModelHint.CONVERSATION,
        **kwargs
    ) -> LLMResponse:
        model = self._get_model(model_hint)
        logger.debug(f"LLM request model={model} messages_count={len(messages)}")
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                **kwargs
            )
            
            choice = response.choices[0]
            message = choice.message
            
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    import json
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    })

            return LLMResponse(
                text=message.content or "",
                tool_calls=tool_calls,
                response_id=response.id,
                tokens_used=response.usage.total_tokens if response.usage else 0
            )
        except Exception as e:
            logger.error(f"LLM Error: {str(e)}")
            raise
