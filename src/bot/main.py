import discord
from dotenv import load_dotenv
import aiohttp, asyncio, os, logging, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import database

load_dotenv()
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

        await database.initialize_db()
        print("db initialized")

    async def on_message(self, message):
        if message.author == self.user:
            return

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
            timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            try:
                await database.add_task(message.author.id, head, body, timestamp)
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