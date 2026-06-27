from typing import AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import settings
from llm.base import BaseLLM

class LocalOpenAIProvider(BaseLLM):
    def __init__(self, api_key: str | None = None, base_url: str | None = None, default_model: str | None = None):
        self._api_key = api_key or settings.local_llm_api_key
        self._base_url = base_url or settings.local_llm_base_url
        self._default_model = default_model or settings.local_llm_model
        
        # Instantiate OpenAI client pointing to the local inference gateway
        self.client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> Dict[str, Any]:
        """Sends chat messages and tools schemas to the local OpenAI endpoint, returning the formatted message dictionary."""
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
        """Sends chat messages and tools to the local OpenAI endpoint, streaming back text response tokens chunk by chunk."""
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
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
