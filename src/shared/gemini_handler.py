import json
import os
import logging
from google import genai
from google.genai import types
from datetime import datetime, timezone
from tenacity import retry, wait_exponential, stop_after_attempt

from src.shared.prompts import get_reactive_prompt, get_proactive_prompt
from src.shared.database import Database

logger = logging.getLogger(__name__)

def return_fallback(retry_state):
    return {"intent": "non_task", "title": None, "body": "", "confidence": 0.0, "reason": ""}

def return_reactive_fallback(retry_state):
    return "Hey, having trouble reaching my brain right now, but I'm tracking!"

def return_proactive_fallback(retry_state):
    return "Hey! Just dropping in for a quick accountability check-in. How are your tasks coming along?"

class ResponseGenerator:
    def __init__(self, db: Database):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    async def _format_history(self, channel_id: int, limit: int = 15) -> str:
        rows = await self.db.get_channel_history(channel_id, limit=limit)
        if not rows:
            return "No prior message history."
        
        history_lines = []
        for author_name, content, timestamp in rows:
            name = author_name or "User"
            history_lines.append(f"[{timestamp}] {name}: {content}")
        return "\n".join(history_lines)

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), retry_error_callback=return_fallback)
    async def analyze_message_intent(self, message_content: str) -> dict:
        """Returns a validated task proposal, or a safe non-task result."""
        fallback = return_fallback(None)
        if not isinstance(message_content, str) or not message_content.strip():
            return fallback

        system_instruction = """
You classify one Discord message. Decide whether the author is clearly asking to
create a personal task. Return JSON only, with exactly these fields:
{
  "intent": "create_task" | "non_task" | "uncertain",
  "title": string | null,
  "body": string,
  "confidence": number from 0 to 1,
  "reason": string
}
- Use "create_task" for an explicit, actionable request or commitment (e.g., "I will complete my essay", "Remind me to run 5k").
- For "create_task", you MUST extract or generate a short, descriptive string for "title".
- Normal conversation, status updates, questions, hypotheticals, and vague goals are "non_task".
- For "non_task" and "uncertain", "title" MUST be null and "body" MUST be an empty string ("").
- This is a proposal mechanism; never claim a task was already created.
""".strip()

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=f"Classify the following message bounded by <user_message> tags:\n<user_message>\n{message_content}\n</user_message>",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0,
                    max_output_tokens=250,
                    response_mime_type="application/json",
                ),
            )
            text = response.text
            if text:
                text = text.strip()
            if not text:
                raise ValueError("Response text is empty or blank")
            
            # Remove any unwanted Markdown codeblock formatting the AI might add
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
                
            payload = json.loads(text)
        except ValueError as exc:
            logger.warning(f"[AI Error] Intent parsing failed or was blocked by safety (ValueError): {exc}")
            return fallback
        except Exception as exc:
            logger.warning(f"[AI Error] Intent classification attempt failed: {exc}")
            raise # Raise for tenacity retry

        if not isinstance(payload, dict):
            return fallback

        intent = payload.get("intent")
        title = payload.get("title")
        body = payload.get("body")
        confidence = payload.get("confidence")
        reason = payload.get("reason")
        if intent not in {"create_task", "non_task", "uncertain"}:
            return fallback
        if not isinstance(body, str) or not isinstance(reason, str):
            return fallback
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            return fallback
        if not 0 <= confidence <= 1:
            return fallback

        if intent == "create_task":
            if not isinstance(title, str) or not title.strip():
                return fallback
            return {
                "intent": intent,
                "title": title.strip(),
                "body": body.strip(),
                "confidence": float(confidence),
                "reason": reason.strip(),
            }

        if title is not None or body.strip():
            return fallback
        return {
            "intent": intent,
            "title": None,
            "body": "",
            "confidence": float(confidence),
            "reason": reason.strip(),
        }

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), retry_error_callback=return_reactive_fallback)
    async def generate_reactive_response(self, author_name: str, channel_id: int, user_message: str) -> str:
        logger.info("[AI DEBUG] Entering generate_reactive_response()")
        history = await self._format_history(channel_id, limit=10)
        current_time = datetime.now(timezone.utc).isoformat()
        system_instruction = get_reactive_prompt(
            author_name,
            current_time,
            history,
            user_message,
        )
        prompt = (
            f"Recent Conversation History:\n{history}\n\n"
            f"Latest User Message from {author_name} (bounded by <user_message> tags):\n<user_message>\n{user_message}\n</user_message>\n\n"
            "Provide a short, direct reactive response."
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=1000,
                )
            )
            text = response.text
            if not text:
                raise ValueError("Response text is empty")
            return text.strip()
        except ValueError as e:
            logger.warning(f"[AI Error] Reactive generation blocked by safety (ValueError): {e}")
            return "Got it."
        except Exception as e:
            logger.warning(f"[AI Error] Reactive generation attempt failed: {e}")
            raise # Raise for tenacity retry

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), retry_error_callback=return_proactive_fallback)
    async def generate_proactive_response(self, author_name: str, channel_id: int) -> str:
        history = await self._format_history(channel_id, limit=20)
        current_time = datetime.now(timezone.utc).isoformat()
        system_instruction = get_proactive_prompt(
            author_name=author_name,
            current_time=current_time,
            history=history,
            tasks="No task data is currently available.",
        )

        prompt = (
            f"Recent Channel Context:\n{history}\n\n"
            "Generate a proactive accountability check-in message."
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=400,
                )
            )
            text = response.text
            if not text:
                raise ValueError("Response text is empty")
            return text.strip()
        except ValueError as e:
            logger.warning(f"[AI Error] Proactive generation blocked by safety (ValueError): {e}")
            return "Hey! Just checking in on your goals today. How's progress?"
        except Exception as e:
            logger.warning(f"[AI Error] Proactive generation attempt failed: {e}")
            raise # Raise for tenacity retry
