from datetime import datetime
import asyncio
import json
import re
from typing import AsyncGenerator, List, Dict, Any, Optional

from agent.base import BaseAgent
from llm.base import BaseLLM
from memory.short_term import ShortTermMemory
from tools.registry import registry

# Long-Term Memory imports
from memory.long_term import LongTermMemory
from memory.fact_extractor import FactExtractor
from config.logging_config import logger

class SimpleAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseLLM,
        memory: ShortTermMemory,
        long_term_memory: Optional[LongTermMemory] = None,
        fact_extractor: Optional[FactExtractor] = None
    ):
        self.llm = llm
        self.memory = memory
        self.long_term_memory = long_term_memory or LongTermMemory()
        self.fact_extractor = fact_extractor or FactExtractor(llm_provider=llm)
        self.background_tasks = set()

    async def _expand_and_search(self, original_query: str, search_depth: str, topic: str, time_range: str) -> str:
        """Asynchronously triggers parallel searches using query expansion to gather diverse and fresh results."""
        logger.info(f"Agent: Expanding search query: '{original_query}'")
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
            logger.info(f"Agent: Generated expanded queries: {queries}")
        except Exception as e:
            logger.warning(f"Agent: Query expansion failed ({e}). Proceeding with original query.")
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
            
        logger.info(f"Agent: Executing {len(tasks)} parallel Tavily searches...")
        # Set return_exceptions=True so a single query failure doesn't crash the entire run loop
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. De-duplicate articles by URL and compile results
        combined_output = []
        seen_urls = set()
        
        for r in results:
            # Skip failed search tasks (exceptions) and log them
            if isinstance(r, Exception):
                logger.warning(f"Agent: Concurrency warning - parallel search query failed: {r}")
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
                
        logger.info(f"Agent: De-duplication complete (compiled {len(combined_output)} search results across {len(seen_urls)} unique URLs)")
        if not combined_output:
            return "No search results found."
            
        return "\n\n---\n\n".join(combined_output)

    async def run(self, session_id: str, user_input: str, user_id: str = "default_user") -> str:
        """Runs the agent loop until a final text response is generated."""
        logger.info(f"Agent: Starting run for session '{session_id}' (user_id: '{user_id}')")
        
        # 1. Retrieve relevant long-term memories before generation begins
        logger.info("Agent: Retrieving long-term memories...")
        memories = await self.long_term_memory.retrieve(user_id=user_id, query=user_input, limit=5)
        memory_facts = [m["fact"] for m in memories]
        logger.info(f"Agent: Retrieved and injected {len(memory_facts)} relevant memories")

        # 2. Save user input to history
        await self.memory.add_message(session_id, role="user", content=user_input)
        tool_schemas = registry.get_all_tool_schemas()
        
        while True:
            # Inject long-term memories during context rebuild
            logger.info("Agent: Rebuilding chat context history...")
            context = await self.memory.get_context(session_id, memories=memory_facts)
            
            logger.info("Agent: Querying LLM...")
            response = await self.llm.generate(context, tools=tool_schemas)
            
            if "tool_calls" in response and response["tool_calls"]:
                logger.info(f"Agent: LLM generated {len(response['tool_calls'])} tool calls")
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
                    logger.info(f"Agent: Executing tool '{tool_name}' with args: {args}")
                    if tool_name == "search_web":
                        query = args.get("query", "")
                        depth = args.get("search_depth", "basic")
                        topic = args.get("topic", "general")
                        tr = args.get("time_range", "none")
                        result = await self._expand_and_search(query, depth, topic, tr)
                    else:
                        result = await registry.execute(tool_name, args)
                    
                    logger.info(f"Agent: Tool '{tool_name}' execution completed. Result length: {len(result)} chars")
                    await self.memory.add_message(
                        session_id,
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"]
                    )
                continue
            else:
                final_content = response.get("content") or ""
                logger.info(f"Agent: Received final text response from LLM (length: {len(final_content)} chars)")
                await self.memory.add_message(session_id, role="assistant", content=final_content)
                
                # 3. Fire off background extraction task (non-blocking, zero latency)
                logger.info("Agent: Dispatching background fact extractor task...")
                task = asyncio.create_task(
                    self.fact_extractor.extract_and_store(
                        user_id=user_id,
                        user_input=user_input,
                        agent_response=final_content,
                        long_term_memory=self.long_term_memory,
                        session_id=session_id,
                        source_message=user_input
                    )
                )
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
                
                logger.info("Agent: Sync run complete")
                return final_content

    async def run_stream(self, session_id: str, user_input: str, user_id: str = "default_user") -> AsyncGenerator[str, None]:
        """Runs the agent loop, yielding execution alerts for tools and typewriter tokens for text."""
        logger.info(f"Agent: Starting stream run for session '{session_id}' (user_id: '{user_id}')")
        
        # 1. Retrieve relevant long-term memories before generation begins
        logger.info("Agent: Retrieving long-term memories...")
        memories = await self.long_term_memory.retrieve(user_id=user_id, query=user_input, limit=5)
        memory_facts = [m["fact"] for m in memories]
        logger.info(f"Agent: Retrieved and injected {len(memory_facts)} relevant memories")

        # 2. Save user input to history
        await self.memory.add_message(session_id, role="user", content=user_input)
        tool_schemas = registry.get_all_tool_schemas()
        
        while True:
            # Inject long-term memories during context rebuild
            logger.info("Agent: Rebuilding chat context history...")
            context = await self.memory.get_context(session_id, memories=memory_facts)
            
            logger.info("Agent: Querying LLM...")
            response = await self.llm.generate(context, tools=tool_schemas)
            
            if "tool_calls" in response and response["tool_calls"]:
                logger.info(f"Agent: LLM generated {len(response['tool_calls'])} tool calls")
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
                    logger.info(f"Agent: Yielding tool call alert: '{tool_name}'")
                    yield f"__TOOL_CALL__:{tool_name}:{json.dumps(args)}"
                    
                    if tool_name == "search_web":
                        query = args.get("query", "")
                        depth = args.get("search_depth", "basic")
                        topic = args.get("topic", "general")
                        tr = args.get("time_range", "none")
                        result = await self._expand_and_search(query, depth, topic, tr)
                    else:
                        result = await registry.execute(tool_name, args)
                    
                    logger.info(f"Agent: Tool '{tool_name}' execution completed. Result length: {len(result)} chars")
                    await self.memory.add_message(
                        session_id,
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"]
                    )
                continue
            else:
                final_content = response.get("content") or ""
                logger.info(f"Agent: Received final text response from LLM (length: {len(final_content)} chars)")
                await self.memory.add_message(session_id, role="assistant", content=final_content)
                
                # 3. Fire off background extraction task (non-blocking, zero latency)
                logger.info("Agent: Dispatching background fact extractor task...")
                task = asyncio.create_task(
                    self.fact_extractor.extract_and_store(
                        user_id=user_id,
                        user_input=user_input,
                        agent_response=final_content,
                        long_term_memory=self.long_term_memory,
                        session_id=session_id,
                        source_message=user_input
                    )
                )
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
                
                # Yield text chunks to simulate visual typing streaming
                chunk_size = 12
                for i in range(0, len(final_content), chunk_size):
                    yield final_content[i:i+chunk_size]
                    await asyncio.sleep(0.01)
                
                logger.info("Agent: Stream run complete")
                break

    async def cleanup(self):
        """Awaits all pending background tasks to ensure memories are saved before shutdown."""
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

    async def save_session_summary(self, session_id: str, user_id: str = "default_user") -> Optional[str]:
        """
        Retrieves the chat history for a session, generates an episodic summary,
        and saves it in long-term memory under the 'episode' category.
        """
        logger.info(f"Agent: Generating session summary for session '{session_id}' (user_id: '{user_id}')")
        raw_messages = await self.memory.storage.get_messages(session_id)
        
        # Filter and format conversation turns
        chat_turns = []
        for msg in raw_messages:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                chat_turns.append(f"{msg['role'].capitalize()}: {msg['content']}")
                
        # Don't summarize if there's very little exchange (less than 2 full turns)
        if len(chat_turns) < 4:
            logger.info("Agent: Skipping session summary generation: insufficient conversation history turns")
            return None
            
        history_text = "\n".join(chat_turns)
        
        # Generate summary using the extractor
        summary = await self.fact_extractor.generate_summary(history_text)
        if not summary:
            logger.warning("Agent: Summarizer failed to return a valid summary text")
            return None
            
        # Add date anchor for temporal reference (Episodic timeline)
        current_date = datetime.now().strftime("%B %d, %Y")
        anchored_summary = f"On {current_date}: {summary}"
        
        # Save as long-term memory
        logger.info(f"Agent: Storing episodic session summary fact in LTM: '{anchored_summary}'")
        await self.long_term_memory.store(
            user_id=user_id,
            fact=anchored_summary,
            category="episode",
            source_session_id=session_id,
            confidence=1.0
        )
        logger.info("Agent: Episodic session summary stored successfully")
        return anchored_summary