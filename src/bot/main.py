import discord
from discord.ext import tasks
import os
import sys
import logging
import asyncio
from datetime import datetime, timezone

from src.shared.config import DB_PATH, LOG_PATH, TOKEN
from src.shared.database import Database
from src.shared.gemini_handler import ResponseGenerator
import aiosqlite

db = Database()

logger = logging.getLogger(__name__)

if not logger.handlers:
    file_handler = logging.FileHandler(filename=LOG_PATH, mode="w", encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")

        await db.initialize_db()
        logger.info("db initialized")

        await db.label_missing_author_names(self.user.id, self.user.name)
        logger.info("message history normalized")

        self.loop.create_task(self.process_queue_loop())
        logger.info("listener activated")

        self.ai = ResponseGenerator(db)
        logger.info("Response generator activated")

    async def on_message(self, message):
        try:
            await db.add_message_history(
                author_id=message.author.id,
                author_name=message.author.global_name or message.author.name,
                channel_id=message.channel.id,
                content=message.content,
                iso_time_stamp=datetime.now(timezone.utc).isoformat()
            )
        except Exception as db_err:
            logger.error(f"[Database Error] Failed to log message: {db_err}")

        # Ignore bot's own messages
        if message.author == self.user:
            return

        content = message.content.strip()
        command = content.casefold()

        # Check database for pending transactions instead of self.pending_tasks
        try:
            pending_task = await db.get_pending_task(message.author.id, message.channel.id)
        except Exception as e:
            logger.error(f"Error fetching pending task: {e}")
            pending_task = None

        if pending_task and command == "confirm":
            timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            try:
                await db.add_task(
                    message.author.id,
                    pending_task["title"],
                    pending_task["body"],
                    timestamp,
                )
                await db.delete_pending_task(message.author.id, message.channel.id)
                await message.channel.send(f"Task created: **{pending_task['title']}**")
            except aiosqlite.IntegrityError:
                await message.channel.send("A task with that title already exists. Please choose a different title.")
            except Exception as e:
                logger.error(f"Failed to create the task: {e}")
                await message.channel.send("Failed to create the task. Please try again later.")
            return

        if pending_task and command == "cancel":
            try:
                await db.delete_pending_task(message.author.id, message.channel.id)
            except Exception as e:
                logger.error(f"Failed to delete pending task: {e}")
            await message.channel.send("Okay, I discarded that task proposal.")
            return

        intent = await self.ai.analyze_message_intent(content)
        if intent.get("intent") == "create_task":
            try:
                await db.set_pending_task(
                    message.author.id, 
                    message.channel.id, 
                    intent["title"], 
                    intent["body"],
                    datetime.now(timezone.utc).isoformat()
                )
            except Exception as e:
                logger.error(f"Error writing pending task: {e}")
            
            await message.channel.send(
                f"I found a task: **{intent['title']}**. Reply `confirm` to create it or `cancel` to discard it."
            )
            return

        logger.info("[DEBUG] Bypassed tasks. Proceeding to AI generation...")
        author_name = message.author.global_name or message.author.name
        ai_reply = await self.ai.generate_reactive_response(
            author_name=author_name,
            channel_id=message.channel.id,
            user_message=message.content
        )
        logger.info(f"[DEBUG] AI Reply received: '{ai_reply}'")
        await message.channel.send(ai_reply)
        logger.info("[DEBUG] AI reply successfully sent to Discord channel.")

    async def send_proactive_message(self, channel_id: int, content: str):
        """Sends a message to a specific channel proactively from anywhere."""
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                channel = await self.fetch_channel(channel_id)
            
            if isinstance(channel, discord.TextChannel):
                await channel.send(content)
                return True
            else:
                logger.warning(f"Channel {channel_id} is not a text channel.")
                return False
        except Exception as e:
            logger.error(f"Failed to send proactive message: {e}")
            return False

    async def process_queue_loop(self):
        """Polls the database every 2 seconds for new proactive messages to send."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                async with aiosqlite.connect(DB_PATH) as db_conn:
                    async with db_conn.execute("SELECT id, channel_id, content FROM PROACTIVE_QUEUE WHERE status = 'PENDING'") as cursor:
                        rows = await cursor.fetchall()
                        
                        for msg_id, channel_id, content in rows:
                            success = await self.send_proactive_message(channel_id, content)
                            
                            if success:
                                await db_conn.execute("UPDATE PROACTIVE_QUEUE SET status = 'SENT' WHERE id = ?", (msg_id,))
                                await db_conn.commit()
                                logger.info(f"Delivered queued message {msg_id}")
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(2.0)


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)

def main():
    try:
        if not TOKEN:
            logger.error("No token provided.")
            sys.exit(1)
        client.run(TOKEN, log_handler=logging.FileHandler(filename=LOG_PATH, mode="w", encoding="utf-8"), log_level=logging.INFO)
    except Exception as e:
        logger.error(f"run failed: {e}")

if __name__ == "__main__":
    main()
