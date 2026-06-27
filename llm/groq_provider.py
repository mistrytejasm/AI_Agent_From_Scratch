from typing import AsyncGenerator, Dict, Any, List
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import settings
from llm.base import BaseLLM

class GroqProvider(BaseLLM):
    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        self._api_key = api_key or settings.groq_api_key
        self._default_model = default_model or settings.groq_default_model
        self.client = AsyncGroq(api_key=self._api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> Dict[str, Any]:
        """Sends chat messages and tools schemas to Groq, returning the formatted message dictionary."""
        model = kwargs.pop("model", self._default_model)
        
        api_args = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        if tools:
            api_args["tools"] = tools
            
        response = await self.client.chat.completions.create(**api_args)
        message = response.choices[0].message
        
        # Format the output matching our database schemas
        msg_dict = {
            "role": "assistant",
            "content": message.content
        }
        
        # Parse requested tool calls if present
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in message.tool_calls
            ]

        # Log and include usage statistics if present
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            msg_dict["usage"] = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }
            from config.logging_config import logger
            logger.info(
                f"[LLM Token Usage] Model: {model} | Prompt Tokens: {usage.prompt_tokens} | "
                f"Completion Tokens: {usage.completion_tokens} | Total Tokens: {usage.total_tokens}"
            )

        return msg_dict

    async def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> AsyncGenerator[str, None]:
        """Sends chat messages and tools to Groq, streaming back text response tokens chunk by chunk."""
        model = kwargs.pop("model", self._default_model)
        
        api_args = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        if tools:
            api_args["tools"] = tools
            
        response = await self.client.chat.completions.create(**api_args)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content