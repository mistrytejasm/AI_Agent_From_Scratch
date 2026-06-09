from typing import AsyncGenerator
from agent.base import BaseAgent
from llm.base import BaseLLM
from memory.short_term import ShortTermMemory

class SimpleAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, memory: ShortTermMemory):
        self.llm = llm
        self.memory = memory

    async def run(self, session_id: str, user_input: str) -> str:
        """Processes user input, stores it in memory, and returns the full response from the LLM."""
        
        # 1. Save user input to memory database
        await self.memory.add_message(session_id, role="user", content=user_input)

        # 2. Get recent conversation sliding window context (system prompt + history)
        context = await self.memory.get_context(session_id)

        # 3. Generate response from the LLM
        response = await self.llm.generate(context)

        # 4. Save the LLM's response to memory database
        await self.memory.add_message(session_id, role="assistant", context=response)

        return response

    async def run_stream(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Processes user input, streams LLM response tokens back in real-time, and saves final response."""
        # 1. Save user input to memory database
        await self.memory.add_message(session_id, role="user", content=user_input)
        
        # 2. Get recent conversation sliding window context
        context = await self.memory.get_context(session_id)
        
        # 3. Stream response tokens from LLM and yield them to the UI
        response_tokens = []
        async for token in self.llm.stream(context):
            response_tokens.append(token)
            yield token
            
        # 4. Reconstruct full response string and save to database memory
        full_response = "".join(response_tokens)
        await self.memory.add_message(session_id, role="assistant", content=full_response)

