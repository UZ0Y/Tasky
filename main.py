import discord
from dotenv import load_dotenv
import aiohttp, asyncio, os, sqlite3

load_dotenv()

class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
    
    async def  on_message(self):
        print(f"message from {self.author}:\n\t {self.content}")

def main():
    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    try:
        client.run(_ = os.getenv("TOKEN"))
    except all:
        print("run failed")

if __name__ == "__name__":
    main()