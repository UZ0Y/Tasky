# src/tester_tools/terminal_sender.py
import sys
from pathlib import Path
import asyncio
from datetime import datetime, timezone
import aiosqlite

# Fix path so imports work when run standalone
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.shared.config import DB_PATH

async def queue_proactive_message():
    print("\n========================================")
    print("🚀 Standalone Terminal Proactive Sender")
    print("Type your message to send to the last active channel.")
    print("========================================\n")

    async with aiosqlite.connect(DB_PATH) as db:
        # Fetch last channel
        async with db.execute("SELECT channel_id FROM MESSAGE_HISTORY ORDER BY id DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            if not row:
                print("❌ No channel history found in DB. Let someone message the bot first!")
                return
            target_channel_id = row[0]

    while True:
        loop = asyncio.get_running_loop()
        message_content = await loop.run_in_executor(None, input, f"[Target: {target_channel_id}] > ")
        
        if not message_content.strip():
            continue
        if message_content.strip().lower() == "exit":
            break

        # Insert into queue
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO PROACTIVE_QUEUE (channel_id, content, timestamp) VALUES (?, ?, ?)",
                (target_channel_id, message_content, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
            print("📤 Message queued for bot delivery!\n")

if __name__ == "__main__":
    asyncio.run(queue_proactive_message())