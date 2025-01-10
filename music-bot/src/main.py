import asyncio
import discord
import os
import importlib
from dotenv import load_dotenv
from bot import MusicBot

# Load environment variables from .env file
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create the bot instance
bot = MusicBot(intents=intents, application_id=int(APPLICATION_ID))

async def load_commands():
    # Set the working directory to the directory containing main.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("Loading commands from directory:", os.getcwd())
    print("Files found:", os.listdir("./commands"))

    for filename in os.listdir("./commands"):
        if filename.endswith(".py"):
            try:
                await importlib.import_module(f"commands.{filename[:-3]}").setup(bot)
                print(f"    Loaded extension: commands.{filename[:-3]}")
            except Exception as e:
                print(f"    Failed to load extension: commands.{filename[:-3]}")
                print(f"      Error: {e}")

# Run the bot and load commands
async def main():
    async with bot:
        await load_commands()
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())