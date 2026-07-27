import asyncio
from src.shared.gemini_handler import ResponseGenerator
from src.shared.database import Database
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

async def test_classifier():
    db = Database()
    ai = ResponseGenerator(db)
    
    test_msgs = [
        "I will complete my essay",
        "Remind me to run 5k",
        "I need to study for the physics exam tomorrow",
        "This is an explicit actionable request to create a task"
    ]
    
    for msg in test_msgs:
        res = await ai.analyze_message_intent(msg)
        print(f"Message: {msg}")
        print(f"Result: {res}\n")

if __name__ == "__main__":
    asyncio.run(test_classifier())
