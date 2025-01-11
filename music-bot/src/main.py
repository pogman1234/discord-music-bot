import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import logging
import asyncio
from bot import MusicBot
import threading
import uvicorn
from fastapi import FastAPI

# Load environment variables
load_dotenv()

# --- Logging Setup ---
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)  # Changed to INFO

# Create a file handler to write logs to a file
file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(file_handler)

# Create a stream handler to print logs to the console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(console_handler)

# --- Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Needed for reading message content
intents.voice_states = True  # Needed for voice-related events

# --- Bot Setup ---
bot = commands.Bot(command_prefix=commands.when_mentioned_or("/"), intents=intents)

# --- FastAPI Setup for Health Check ---
app = FastAPI()

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

def run_webserver():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- Event: on_ready ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands (register them with Discord)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    print(f"Bot is ready. Logged in as {bot.user}")
    print("------")

    bot.music_bot = MusicBot(bot)

# --- Command: /ping ---
@bot.tree.command(name="ping", description="Replies with Pong!")
async def ping(interaction: discord.Interaction):
    logger.info(f"'/ping' command used by {interaction.user} in {interaction.guild}")
    await interaction.response.send_message("Pong!", ephemeral=True)

# --- Load Cogs ---
async def load_cogs():
    for filename in os.listdir("./music-bot/src/commands"):
        if filename.endswith(".py"):
            extension = filename[:-3]
            try:
                await bot.load_extension(f"commands.{extension}")
                logger.info(f"Loaded cog: {extension}")
            except Exception as e:
                logger.error(f"Failed to load cog {extension}: {e}")

async def start_bot():
    await load_cogs()
    # Start the health check web server in a separate thread
    webserver_thread = threading.Thread(target=run_webserver)
    webserver_thread.daemon = True
    webserver_thread.start()
    # Start the bot
    await bot.start(os.getenv("DISCORD_BOT_TOKEN"))

# --- Start Bot ---
async def main():
    await start_bot()

if __name__ == "__main__":
    asyncio.run(main())