from typing import AsyncGenerator, Dict, Any, List
from llm.base import BaseLLM

class FallbackLLMProvider(BaseLLM):
    def __init__(self, primary: BaseLLM, fallback: BaseLLM):
        self.primary = primary
        self.fallback = fallback

    async def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> Dict[str, Any]:
        """Tries the primary provider first, falling back to the backup provider on any exception."""
        # Check model parameter if overridden, otherwise use defaults
        primary_model = kwargs.get("model", getattr(self.primary, "_default_model", "unknown"))
        fallback_model = kwargs.get("model", getattr(self.fallback, "_default_model", "unknown"))
        
        try:
            print(f"\n[LLM Call] Routing to Local OpenAI Engine (model: {primary_model})...")
            return await self.primary.generate(messages, tools=tools, **kwargs)
        except Exception as e:
            print(f"\n[LLM Fallback] Primary LLM provider failed: {e}")
            print(f"[LLM Call] Routing to Backup Groq Engine (model: {fallback_model})...")
            return await self.fallback.generate(messages, tools=tools, **kwargs)

    async def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> AsyncGenerator[str, None]:
        """Streams from the primary provider, switching to the fallback provider if the primary fails."""
        primary_model = kwargs.get("model", getattr(self.primary, "_default_model", "unknown"))
        fallback_model = kwargs.get("model", getattr(self.fallback, "_default_model", "unknown"))
        
        try:
            print(f"\n[LLM Call] Routing to Local OpenAI Engine (model: {primary_model})...")
            async for token in self.primary.stream(messages, tools=tools, **kwargs):
                yield token
        except Exception as e:
            print(f"\n[LLM Fallback] Primary LLM stream failed: {e}")
            print(f"[LLM Call] Routing to Backup Groq Engine (model: {fallback_model})...")
            async for token in self.fallback.stream(messages, tools=tools, **kwargs):
                yield token
