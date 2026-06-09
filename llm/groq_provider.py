from typing import AsyncGenerator, Dict, Any, List
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from llm.base import BaseLLM

class GroqProvider(BaseLLM):
    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        # Fall back to environment settings if values aren't injected explicitly
        self._api_key = api_key or settings.groq_api_key
        self._default_model = default_model or settings.groq_default_model

        # Initialise AsyncGroq client
        self.client = AsyncGroq(api_key=self._api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )

    async def generate(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Sends chat messages to Groq and awaits the full response."""
        model = kwargs.pop("model", self._default_model)

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            **kwargs
        )
        return response.choices[0].message.content

    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[str, None]:
        """Sends chat messages to Groq and streams response tokens chunk by chunk."""
        model = kwargs.pop("model", self._default_model)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token
