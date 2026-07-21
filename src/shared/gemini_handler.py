import os, sys
import aiosqlite
from google import genai
from google.genai import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.shared.config import DB_PATH
from src.shared.prompts import get_reactive_prompt, get_proactive_prompt
from src.shared.database import Database

class ResponseGenerator:
    def __init__(self, db: Database):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Initialize official Google GenAI client
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

    async def generate_reactive_response(self, author_name: str, channel_id: int, user_message: str) -> str:
        print("[AI DEBUG] A. Entering generate_reactive_response()")
        history = await self._format_history(channel_id, limit=10)
        current_time = datetime.now(timezone.utc).isoformat()
        system_instruction = get_reactive_prompt(
            author_name,
            current_time,
            history,
            user_message,
        )
        print(f"[AI DEBUG] B. History fetched. Length: {len(history)} characters")
        prompt = (
            f"Recent Conversation History:\n{history}\n\n"
            f"Latest User Message from {author_name}: {user_message}\n\n"
            "Provide a short, direct reactive response."
        )

        try:
            print("[AI DEBUG] C. Calling Gemini API asynchronously...")
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=1000,
                )
            )
            print("[AI DEBUG] D. Gemini API responded successfully.")
            if response.candidates:
                print(f"[AI DEBUG] E. Finish reason: {response.candidates[0].finish_reason}")
            return response.text.strip() if response.text else "Got it."
        except Exception as e:
            print(f"[AI Error] Reactive generation failed: {e}")
            return "Hey, having trouble reaching my brain right now, but I'm tracking!"

    async def generate_proactive_response(self, author_name: str, channel_id: int) -> str:
        system_instruction = get_proactive_prompt(author_name)
        history = await self._format_history(channel_id, limit=20)

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
            return response.text.strip() if response.text else "Hey! Just checking in on your goals today. How's progress?"
        except Exception as e:
            print(f"[AI Error] Proactive generation failed: {e}")
            return "Hey! Just dropping in for a quick accountability check-in. How are your tasks coming along?"
