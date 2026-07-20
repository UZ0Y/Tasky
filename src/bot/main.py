import discord
from dotenv import load_dotenv
import os, logging, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# تم إصلاح الاستيراد هنا ليعتمد على الكود المجهز بالكامل في ملف database
from src.shared.database import Database
db = Database()

load_dotenv(dotenv_path=ROOT / ".env")
handler = logging.FileHandler(filename="Discord.log", mode="w", encoding="utf-8")

TASK_USAGE = "Task => <Title>\n<Body>"


def parse_task_message(content: str):
    lines = content.splitlines()
    if not lines:
        return None

    first_line = lines[0].strip()
    if not first_line.startswith("Task"):
        return None

    remainder = first_line[4:].strip()
    if remainder.startswith("=>"):
        head = remainder[2:].strip()
    elif remainder.startswith(":"):
        head = remainder[1:].strip()
    else:
        head = remainder

    if not head:
        return None

    body = "\n".join(line.strip() for line in lines[1:]).strip()
    return head, body


def format_task_help() -> str:
    return f"TASK FORMAT\n{TASK_USAGE}"


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

        await db.initialize_db()
        print("db initialized")
        
    async def on_message(self, message):
        
        # =========================================================
        # الـ Feature الجديدة: تسجيل كل رسالة مبعوثة للداتابيس بناءً على طلب المسؤول
        # =========================================================
        try:
            await db.add_message_history(
                author_id=message.author.id,
                author_name=message.author.global_name,
                channel_id=message.channel.id,
                content=message.content,
                iso_time_stamp=datetime.now(timezone.utc).isoformat()
            )
        
        except Exception as db_err:
            # طباعة الخطأ في الكونسول حتى لا يعطل عمل البوت الأساسي إذا فشل الاتصال بالداتابيس
            print(f"[Database Error] Failed to log message: {db_err}")
        # =========================================================

        # 1. تجاهل رسائل البوت نفسه لمنع التكرار اللانهائي
        if message.author == self.user:
            return

        # اللوجيك الأصلي الخاص بالـ Tasks دون تعديل أو تخريب
        content = message.content.strip()
        if content == "Task":
            await message.channel.send(format_task_help())
            return

        if content.startswith("Task"):
            parsed = parse_task_message(content)
            if parsed is None:
                await message.channel.send(format_task_help())
                return

            head, body = parsed
            timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            try:
                await db.add_task(message.author.id, head, body, timestamp)
                await message.channel.send(f"Task created: **{head}**")
            except Exception as e:
                if "UNIQUE" in str(e).upper():
                    await message.channel.send("A task with that title already exists. Please choose a different title.")
                else:
                    await message.channel.send("Failed to create the task. Please try again later.")
                    print(f"Failed to add task: {e}")


def main():
    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    try:
        client.run(os.getenv("TOKEN"), log_handler=handler, log_level=logging.DEBUG)
    except Exception as e:
        print(f"run failed: {e}")

if __name__ == "__main__":
    main()