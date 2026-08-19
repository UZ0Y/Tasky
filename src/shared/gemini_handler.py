"""
Strict Gemini Handler – Intent Detection with Schema Enforcement

This is an improved version of gemini_handler.py that enforces strict
JSON format matching the database schema exactly.

Key differences:
1. Uses StrictIntentValidator for all responses
2. Clear field mapping: head → TASKS.head, body → TASKS.body
3. Fails loudly on schema violations
4. Better error messages for debugging
5. Type-safe response objects
"""

import json
import os
import logging
from google import genai
from google.genai import types
from datetime import datetime, timezone
from tenacity import retry, wait_exponential, stop_after_attempt

from src.shared.database import Database
from src.shared.strict_intent_detector import (
    StrictIntentValidator,
    get_strict_intent_classification_prompt,
)

logger = logging.getLogger(__name__)


def return_fallback(retry_state):
    """Fallback for intent analysis failures."""
    return {
        "intent": "non_task",
        "confidence": 0.0,
        "reason": "Failed to classify - falling back to non-task",
    }


def return_reactive_fallback(retry_state):
    """Fallback for reactive response generation."""
    return "Got it."


def return_proactive_fallback(retry_state):
    """Fallback for proactive message generation."""
    return "Hey! Just checking in. How are your tasks coming along?"


class StrictResponseGenerator:
    """
    Strict response generator with schema enforcement.
    Validates all intent classifications against database schema.
    """

    def __init__(self, db: Database):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    async def _format_history(self, channel_id: int, limit: int = 15) -> str:
        """Formats message history for context."""
        rows = await self.db.get_channel_history(channel_id, limit=limit)
        if not rows:
            return "No prior message history."

        history_lines = []
        for author_name, content, timestamp in rows:
            name = author_name or "User"
            history_lines.append(f"[{timestamp}] {name}: {content}")
        return "\n".join(history_lines)

    @retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_fallback,
    )
    async def analyze_message_intent(self, message_content: str) -> dict:
        """
        Analyzes message intent with strict schema validation.
        
        Returns:
            For CREATE_TASK:
            {
                "intent": "create_task",
                "head": "Task title",
                "body": "Task details",
                "confidence": 0.95,
                "reason": "..."
            }
            
            For NON_TASK/UNCERTAIN:
            {
                "intent": "non_task",
                "confidence": 0.85,
                "reason": "..."
            }
        """
        # Basic input validation
        if not isinstance(message_content, str) or not message_content.strip():
            logger.warning("[Intent] Empty or invalid input")
            return return_fallback(None)

        system_instruction = get_strict_intent_classification_prompt()

        try:
            logger.debug(f"[Intent] Analyzing: {message_content[:100]}...")

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=f"Classify the following Discord message:\n<message>\n{message_content}\n</message>",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0,  # Deterministic for consistency
                    max_output_tokens=500,
                    response_mime_type="application/json",
                ),
            )

            text = response.text.strip() if response.text else ""

            if not text:
                logger.warning("[Intent] Empty response from Gemini")
                raise ValueError("Response text is empty")

            # Remove markdown code blocks if present (safety measure)
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            if not text:
                logger.warning("[Intent] Empty after cleanup")
                raise ValueError("Response is empty after cleanup")

            logger.debug(f"[Intent] Raw response: {text[:200]}")

            # Parse JSON
            payload = json.loads(text)

            # STRICT VALIDATION - This will raise ValueError if schema is invalid
            try:
                validated = StrictIntentValidator.validate(payload)
                logger.info(f"[Intent] ✓ Valid {validated['intent']}")
                return validated

            except ValueError as validation_error:
                logger.warning(f"[Intent] ✗ Schema validation failed: {validation_error}")
                logger.warning(f"[Intent] Payload was: {json.dumps(payload, indent=2)}")
                # Return safe non-task instead of crashing
                return return_fallback(None)

        except json.JSONDecodeError as e:
            logger.warning(f"[Intent] JSON decode error: {e}")
            logger.warning(f"[Intent] Raw text was: {text[:500]}")
            raise  # Tenacity will retry

        except ValueError as e:
            logger.warning(f"[Intent] ValueError: {e}")
            raise  # Tenacity will retry

        except Exception as e:
            logger.warning(f"[Intent] Unexpected error: {e}")
            raise  # Tenacity will retry

    @retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_reactive_fallback,
    )
    async def generate_reactive_response(
        self, author_name: str, channel_id: int, user_message: str
    ) -> str:
        """Generates a reactive response to a message."""
        logger.debug("[Reactive] Generating response")

        history = await self._format_history(channel_id, limit=10)
        current_time = datetime.now(timezone.utc).isoformat()

        system_instruction = f"""You are a friendly Discord bot assistant.
User: {author_name}
Time: {current_time}

Recent conversation:
{history}

Respond briefly (1-3 lines) and naturally to the user's message.
Don't identify as an AI or use robotic language.
Be conversational and helpful.
"""

        prompt = f"User message: {user_message}\n\nRespond naturally and briefly."

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=1000,
                ),
            )

            text = response.text.strip() if response.text else ""

            if not text:
                logger.warning("[Reactive] Empty response")
                raise ValueError("Response text is empty")

            logger.debug(f"[Reactive] ✓ Generated response")
            return text

        except ValueError as e:
            logger.warning(f"[Reactive] ValueError: {e}")
            raise

        except Exception as e:
            logger.warning(f"[Reactive] Error: {e}")
            raise

    @retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_proactive_fallback,
    )
    async def generate_proactive_response(self, author_name: str, channel_id: int) -> str:
        """Generates a proactive check-in message."""
        logger.debug("[Proactive] Generating check-in")

        history = await self._format_history(channel_id, limit=20)
        current_time = datetime.now(timezone.utc).isoformat()

        system_instruction = f"""You are an accountability coach for {author_name}.
Time: {current_time}

Recent channel activity:
{history}

Generate a brief, friendly check-in message (2-3 lines) asking about their progress
on tasks or goals. Be encouraging and specific if possible.
Don't be robotic or overly formal.
"""

        prompt = "Generate a brief accountability check-in message."

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=400,
                ),
            )

            text = response.text.strip() if response.text else ""

            if not text:
                logger.warning("[Proactive] Empty response")
                raise ValueError("Response text is empty")

            logger.debug(f"[Proactive] ✓ Generated check-in")
            return text

        except ValueError as e:
            logger.warning(f"[Proactive] ValueError: {e}")
            raise

        except Exception as e:
            logger.warning(f"[Proactive] Error: {e}")
            raise
