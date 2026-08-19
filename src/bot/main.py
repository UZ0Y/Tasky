"""
Tasky Discord Bot - With Strict Intent Detection

This is an improved version of main.py that uses strict schema validation
for all intent detection responses.

Key improvements:
1. Strict intent detection enforces exact database schema format
2. Clear field mapping: head (not title), body (not description)
3. Better error messages for debugging
4. Validates before creating pending tasks
5. Comprehensive logging
"""

import discord
from discord.ext import tasks
import os
import sys
import logging
import asyncio
from datetime import datetime, timezone

from src.shared.config import DB_PATH, LOG_PATH, TOKEN
from src.shared.database import Database
from src.shared.gemini_handler import StrictResponseGenerator as ResponseGenerator
import aiosqlite

db = Database()

logger = logging.getLogger(__name__)

if not logger.handlers:
    file_handler = logging.FileHandler(filename=LOG_PATH, mode="w", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)


class MyClient(discord.Client):
    """Discord bot client with strict intent detection."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_task_started = False

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")

        await db.initialize_db()
        logger.info("Database initialized")

        await db.label_missing_author_names(self.user.id, self.user.name)
        logger.info("Message history normalized")

        if not self.bg_task_started:
            self.loop.create_task(self.process_queue_loop())
            self.bg_task_started = True
            logger.info("Background queue processor started")

        self.ai = ResponseGenerator(db)
        logger.info("Strict Response Generator initialized")

    async def on_message(self, message):
        """Handles incoming messages with strict intent detection."""
        try:
            # Log message to history
            await db.add_message_history(
                author_id=message.author.id,
                author_name=message.author.global_name or message.author.name,
                channel_id=message.channel.id,
                content=message.content,
                iso_time_stamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as db_err:
            logger.error(f"[Database] Failed to log message: {db_err}")

        # Ignore bot's own messages
        if message.author == self.user:
            return

        content = message.content.strip()
        command = content.casefold()

        # ====================================================================
        # CONFIRMATION/CANCELLATION HANDLING
        # ====================================================================

        try:
            pending_task = await db.get_pending_task(message.author.id, message.channel.id)
        except Exception as e:
            logger.error(f"[Database] Error fetching pending task: {e}")
            pending_task = None

        if pending_task and command == "confirm":
            timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            try:
                await db.confirm_pending_task(
                    message.author.id,
                    message.channel.id,
                    pending_task["title"],
                    pending_task["body"],
                    timestamp,
                )
                await message.channel.send(f"✅ Task created: **{pending_task['title']}**")
                logger.info(f"[Task] Created: {pending_task['title']}")
            except aiosqlite.IntegrityError:
                await message.channel.send(
                    "⚠️ A task with that title already exists. Please choose a different title."
                )
                logger.warning(f"[Task] Duplicate title: {pending_task['title']}")
            except Exception as e:
                logger.error(f"[Task] Failed to confirm: {e}")
                await message.channel.send("❌ Failed to create the task. Please try again later.")
            return

        if pending_task and command == "cancel":
            try:
                await db.delete_pending_task(message.author.id, message.channel.id)
                await message.channel.send("Okay, I discarded that task proposal.")
                logger.info("[Task] Cancelled pending task")
            except Exception as e:
                logger.error(f"[Task] Failed to cancel: {e}")
            return

        # ====================================================================
        # STRICT INTENT ANALYSIS
        # ====================================================================

        logger.info("[Intent] Analyzing message...")
        intent_result = await self.ai.analyze_message_intent(content)

        # ====================================================================
        # HANDLE CREATE_TASK INTENT
        # ====================================================================

        if intent_result.get("intent") == "create_task":
            logger.info(
                f"[Intent] ✓ Detected create_task (confidence: {intent_result['confidence']})"
            )

            # Extract fields from strict schema
            title = intent_result.get("head")  # Uses 'head' not 'title'
            body = intent_result.get("body", "")

            if not title:
                logger.error("[Intent] Missing 'head' field in create_task response")
                await message.channel.send("❌ Internal error: Invalid task data. Please try again.")
                return

            try:
                await db.set_pending_task(
                    message.author.id,
                    message.channel.id,
                    title,
                    body,
                    datetime.now(timezone.utc).isoformat(),
                )
                logger.info(f"[Pending] Task proposal: {title}")
            except Exception as e:
                logger.error(f"[Database] Error writing pending task: {e}")
                await message.channel.send("❌ Failed to process task proposal. Please try again.")
                return

            await message.channel.send(
                f"I found a task: **{title}**\n"
                f"Reply `confirm` to create it or `cancel` to discard it."
            )
            return

        # ====================================================================
        # HANDLE NON_TASK / UNCERTAIN INTENT
        # ====================================================================

        if intent_result.get("intent") in ("non_task", "uncertain"):
            logger.info(f"[Intent] ✓ Detected {intent_result['intent']}")
            logger.info("[Response] Generating reactive response...")

            author_name = message.author.global_name or message.author.name
            ai_reply = await self.ai.generate_reactive_response(
                author_name=author_name,
                channel_id=message.channel.id,
                user_message=message.content,
            )

            logger.info(f"[Response] ✓ Generated: {ai_reply[:100]}...")
            await message.channel.send(ai_reply)
            return

        # Fallback (should not reach here with proper validator)
        logger.warning(f"[Intent] Unknown intent type: {intent_result.get('intent')}")
        await message.channel.send("Got it.")

    async def send_proactive_message(self, channel_id: int, content: str):
        """Sends a proactive message to a channel."""
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                channel = await self.fetch_channel(channel_id)

            if isinstance(channel, discord.TextChannel):
                await channel.send(content)
                logger.info(f"[Proactive] Sent to channel {channel_id}")
                return True
            else:
                logger.warning(f"[Proactive] Channel {channel_id} is not a text channel")
                return False
        except Exception as e:
            logger.error(f"[Proactive] Failed to send: {e}")
            return False

    async def process_queue_loop(self):
        """Background task: polls for queued proactive messages."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                async with aiosqlite.connect(DB_PATH, timeout=5.0) as db_conn:
                    async with db_conn.execute(
                        "SELECT id, channel_id, content FROM PROACTIVE_QUEUE WHERE status = 'PENDING'"
                    ) as cursor:
                        rows = await cursor.fetchall()

                        for msg_id, channel_id, content in rows:
                            success = await self.send_proactive_message(channel_id, content)

                            if success:
                                await db_conn.execute(
                                    "UPDATE PROACTIVE_QUEUE SET status = 'SENT' WHERE id = ?",
                                    (msg_id,),
                                )
                                await db_conn.commit()
                                logger.info(f"[Queue] Delivered message {msg_id}")
            except Exception as e:
                logger.error(f"[Queue] Processor error: {e}")
            await asyncio.sleep(2.0)


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)


def main():
    """Main entry point."""
    try:
        if not TOKEN:
            logger.error("No Discord token provided")
            sys.exit(1)
        logger.info("Starting Tasky Discord Bot (Strict Mode)...")
        client.run(
            TOKEN,
            log_handler=logging.FileHandler(filename=LOG_PATH, mode="w", encoding="utf-8"),
            log_level=logging.INFO,
        )
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
