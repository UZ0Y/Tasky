import discord
from dotenv import load_dotenv
import aiohttp, asyncio, os, logging

from shared import database

load_dotenv()
handler = logging.FileHandler(filename="Discord.log", mode="w", encoding="utf-8")

class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

        await database.initialize_db()
        print("db initialized")
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        parser:str = message.content
        
        if parser == "Task":
            print("""TASK FORMAT\n
                  Task => Title\n\t body""")

        if parser[:4] == "Task":
            pass
        
    
        
        

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