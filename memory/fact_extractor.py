import json
import asyncio
from typing import List, Dict, Any, Optional

from llm.groq_provider import GroqProvider
from config.logging_config import logger

class FactExtractor:
    """
    Analyzes conversation exchanges using an LLM to extract structured facts
    about the user. Filters out conversational noise and runs asynchronously.
    """
    SYSTEM_PROMPT = """You are a precise, production-grade fact extraction engine.
Analyze the conversation turn between a user and an assistant, and extract atomic, self-contained facts about the user that are worth remembering across sessions.

Focus on extracting details related to:
1. Personal preferences (likes, dislikes, workflow preferences, coding styles).
2. Project details (tech stack, tools used, database setup, environment constraints).
3. Personal info (location, role, background, experience level).
4. Goals (what the user is building, learning, or trying to achieve).
5. Decisions (design choices, framework selection, custom architectures chosen).
6. Technical context (patterns followed, specific configurations, programming practices).

DO NOT extract:
- Casual talk, greetings, politeness ("thanks", "how are you", "good morning").
- Temporary context (e.g., debugging a specific syntax error that won't matter in the next session).
- Questions asked by the user (only extract what they state as true about themselves/their setup).
- Tool results, time requests, or temporary calculations.

If no long-term facts are present, return an empty list of facts.

You must output a valid JSON object in this exact format:
{
  "facts": [
    {
      "fact": "Atomic fact statement (e.g., 'User prefers Python for backend development')",
      "category": "user_preference|project_detail|personal_info|goal|decision|technical_context",
      "confidence": 0.95
    }
  ]
}
"""

    def __init__(self, llm_provider: Optional[GroqProvider] = None):
        self.llm = llm_provider or GroqProvider()

    def _should_extract(self, user_input: str) -> bool:
        """
        Determines if a conversation turn is worth processing for fact extraction.
        Skips greetings, brief acknowledgments, and slash commands.
        """
        text = user_input.strip().lower()

        # 1. Skip slash commands
        if text.startswith("/"):
            return False

        # 2. Skip simple greetings or farewells
        greetings = {"hi", "hello", "hey", "yo", "sup", "howdy", "bye", "goodbye", "ciao", "greetings"}
        if text in greetings:
            return False

        # 3. Skip brief acknowledgments or casual short answers
        casuals = {"thanks", "thank you", "ok", "okay", "yes", "no", "great", "nice", "awesome", "perfect", "cool", "sure"}
        if text in casuals:
            return False

        # 4. Skip if the text is too short to contain factual context
        words = text.split()
        if len(words) < 3:
            return False

        return True

    def _parse_facts(self, llm_output: str) -> List[Dict[str, Any]]:
        """
        Robustly parses LLM output into a list of structured facts.
        Handles markdown code fences and invalid formats.
        """
        if not llm_output or not llm_output.strip():
            return []

        cleaned = llm_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            # Match our requested object structure
            if isinstance(data, dict) and "facts" in data:
                facts = data["facts"]
                if isinstance(facts, list):
                    return facts
            # Fallback if the LLM returned a list directly
            elif isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fact extraction JSON: {e}\nRaw output: {llm_output}")
            return []

    async def extract(self, user_input: str, agent_response: str) -> List[Dict[str, Any]]:
        """
        Calls the LLM to extract facts from the turn. Returns a list of fact dicts.
        """
        # Skip if the input doesn't contain useful information
        if not self._should_extract(user_input):
            logger.info("FactExtractor: Skipping fact extraction because user input is conversational noise / too short")
            return []

        logger.info("FactExtractor: Analyzing conversation turn for long-term facts...")
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User: {user_input}\nAssistant: {agent_response}"
            }
        ]

        try:
            # Call LLM with JSON mode enabled
            response = await self.llm.generate(
                messages=messages,
                response_format={"type": "json_object"}
            )
            llm_output = response.get("content", "")
            return self._parse_facts(llm_output)
        except Exception as e:
            logger.error(f"LLM fact extraction call failed: {e}")
            return []

    async def extract_and_store(
        self,
        user_id: str,
        user_input: str,
        agent_response: str,
        long_term_memory: Any,
        session_id: Optional[str] = None,
        source_message: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts facts from a conversation turn and stores them in long-term memory.
        Runs deduplication automatically through long_term_memory.store().
        """
        logger.info(f"FactExtractor: Starting extract_and_store for session '{session_id}' (user_id: '{user_id}')")
        # 1. Extract facts from the conversation turn
        facts = await self.extract(user_input, agent_response)
        logger.info(f"FactExtractor: Extracted {len(facts)} facts from turn")
        if not facts:
            return []

        results = []
        # 2. Store each extracted fact
        for item in facts:
            fact_text = item.get("fact", "").strip()
            category = item.get("category", "general").strip()
            confidence = item.get("confidence", 1.0)

            if not fact_text:
                continue

            logger.info(f"FactExtractor: Storing extracted fact: '{fact_text}'")
            # Store the fact (the memory manager handles insertion, updating, or reinforcing)
            outcome = await long_term_memory.store(
                user_id=user_id,
                fact=fact_text,
                category=category,
                source_session_id=session_id,
                source_message=source_message,
                confidence=confidence
            )
            results.append({
                "fact": fact_text,
                "outcome": outcome
            })

        logger.info(f"FactExtractor: Extract and store completed successfully. Outcomes: {results}")
        return results

    async def generate_summary(self, chat_history_text: str) -> Optional[str]:
        """
        Generates a concise 2-3 sentence summary of a chat history to act as episodic memory.
        """
        logger.info("FactExtractor: Generating episodic session summary...")
        prompt = (
            "You are a precise summarization engine. Analyze the following conversation history and generate a "
            "concise 2-3 sentence digest. Focus strictly on the primary topics discussed, decisions made, goals established, "
            "and technical context. Do not include greetings, introductions, or pleasantries. "
            "Write the summary in the third person, starting directly with the core topics.\n\n"
            f"CONVERSATION HISTORY:\n{chat_history_text}\n\n"
            "Summary:"
        )
        try:
            response = await self.llm.generate([{"role": "user", "content": prompt}])
            summary = response.get("content", "").strip()
            if summary:
                logger.info(f"FactExtractor: Episodic session summary generated successfully: '{summary}'")
            else:
                logger.warning("FactExtractor: Episodic summary output was empty")
            return summary if summary else None
        except Exception as e:
            logger.error(f"Failed to generate session summary via LLM: {e}")
            return None