import asyncio
import json
import re
from typing import AsyncGenerator, List, Dict, Any
from agent.base import BaseAgent
from llm.base import BaseLLM
from memory.short_term import ShortTermMemory
from tools.registry import registry

class SimpleAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, memory: ShortTermMemory):
        self.llm = llm
        self.memory = memory

    async def _expand_and_search(self, original_query: str, search_depth: str, topic: str, time_range: str) -> str:
        """Asynchronously triggers parallel searches using query expansion to gather diverse and fresh results."""
        # 1. Ask the LLM to formulate 2 alternative search terms to broaden the search context
        prompt = (
            f"Given the user's target search query: '{original_query}', generate exactly 2 alternative, "
            f"distinct search queries that would help gather the most comprehensive and up-to-date information. "
            f"Respond with ONLY the two queries, one per line. Do not write any other conversational text."
        )
        
        try:
            # Use a fast non-blocking call to get alternative queries
            expansion_response = await self.llm.generate([{"role": "user", "content": prompt}])
            lines = [line.strip().strip('"') for line in expansion_response.get("content", "").split("\n") if line.strip()]
            queries = [original_query] + lines[:2]
        except Exception:
            queries = [original_query]

        # 2. Fire searches in parallel
        tasks = []
        for q in queries:
            api_args = {
                "query": q,
                "search_depth": search_depth,
                "topic": topic,
                "time_range": time_range
            }
            tasks.append(registry.execute("search_web", api_args))
            
        # Set return_exceptions=True so a single query failure doesn't crash the entire run loop
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. De-duplicate articles by URL and compile results
        combined_output = []
        seen_urls = set()
        
        for r in results:
            # Skip failed search tasks (exceptions) and log them
            if isinstance(r, Exception):
                print(f"[Agent] Concurrency warning - parallel search query failed: {r}")
                continue
            
            # Split individual search outputs by the '---' separator we defined in search_tools
            items = r.split("---")
            for item in items:
                if not item.strip():
                    continue
                # Parse URL using regex to check for duplicates
                url_match = re.search(r"URL:\s*(https?://[^\n]+)", item)
                if url_match:
                    url = url_match.group(1).strip()
                    if url in seen_urls:
                        continue  # Skip duplicate link
                    seen_urls.add(url)
                combined_output.append(item.strip())
                
        if not combined_output:
            return "No search results found."
            
        return "\n\n---\n\n".join(combined_output)

    async def run(self, session_id: str, user_input: str) -> str:
        """Runs the agent loop until a final text response is generated."""
        await self.memory.add_message(session_id, role="user", content=user_input)
        tool_schemas = registry.get_all_tool_schemas()
        
        while True:
            context = await self.memory.get_context(session_id)
            response = await self.llm.generate(context, tools=tool_schemas)
            
            if "tool_calls" in response and response["tool_calls"]:
                await self.memory.add_message(
                    session_id, 
                    role="assistant", 
                    content=response.get("content"), 
                    tool_calls=response["tool_calls"]
                )
                
                for tc in response["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                        
                    # Intercept search tool to perform expanded parallel search
                    if tool_name == "search_web":
                        query = args.get("query", "")
                        depth = args.get("search_depth", "basic")
                        topic = args.get("topic", "general")
                        tr = args.get("time_range", "none")
                        result = await self._expand_and_search(query, depth, topic, tr)
                    else:
                        result = await registry.execute(tool_name, args)
                    
                    await self.memory.add_message(
                        session_id,
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"]
                    )
                continue
            else:
                final_content = response.get("content") or ""
                await self.memory.add_message(session_id, role="assistant", content=final_content)
                return final_content

    async def run_stream(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Runs the agent loop, yielding execution alerts for tools and typewriter tokens for text."""
        await self.memory.add_message(session_id, role="user", content=user_input)
        tool_schemas = registry.get_all_tool_schemas()
        
        while True:
            context = await self.memory.get_context(session_id)
            response = await self.llm.generate(context, tools=tool_schemas)
            
            if "tool_calls" in response and response["tool_calls"]:
                await self.memory.add_message(
                    session_id, 
                    role="assistant", 
                    content=response.get("content"), 
                    tool_calls=response["tool_calls"]
                )
                
                for tc in response["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                        
                    # Yield token with tool name and arguments to notify CLI
                    yield f"__TOOL_CALL__:{tool_name}:{json.dumps(args)}"
                    
                    if tool_name == "search_web":
                        query = args.get("query", "")
                        depth = args.get("search_depth", "basic")
                        topic = args.get("topic", "general")
                        tr = args.get("time_range", "none")
                        result = await self._expand_and_search(query, depth, topic, tr)
                    else:
                        result = await registry.execute(tool_name, args)
                    
                    await self.memory.add_message(
                        session_id,
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"]
                    )
                continue
            else:
                final_content = response.get("content") or ""
                await self.memory.add_message(session_id, role="assistant", content=final_content)
                
                # Yield text chunks to simulate visual typing streaming
                chunk_size = 12
                for i in range(0, len(final_content), chunk_size):
                    yield final_content[i:i+chunk_size]
                    await asyncio.sleep(0.01)
                break