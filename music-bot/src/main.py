import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import logging
import asyncio
from bot import MusicBot
from googleapiclient.discovery import build
import threading
import json
from flask import Flask, render_template
import sys

# --- Load environment variables ---
load_dotenv()

# --- Logging Setup ---
class GoogleCloudLogFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "component": record.name,
            "time": self.formatTime(record),
            "logging.googleapis.com/sourceLocation": {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName
            },
        }

        # Include exception info if available
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        # Add extra fields if available (for structured logging)
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)

        return json.dumps(log_entry)

# Configure logging
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Log to a file
file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
file_handler.setFormatter(GoogleCloudLogFormatter())
logger.addHandler(file_handler)

# Log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(GoogleCloudLogFormatter())
logger.addHandler(console_handler)

# --- Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Needed for reading message content
intents.voice_states = True  # Needed for voice-related events

# --- Bot Setup ---
bot = commands.Bot(command_prefix=commands.when_mentioned_or("/"), intents=intents)

# --- YouTube Data API Setup ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# --- Flask Setup for Health Check and Frontend ---
app = Flask(__name__, template_folder='/app/templates')  # Adjusted template folder path

@app.route("/healthz")
def health_check():
    return {"status": "ok"}

@app.route("/")
def index():
    song_info = bot.music_bot.get_currently_playing()
    return render_template("index.html", song=song_info)

# --- Event: on_ready ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands (register them with Discord)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)

    print(f"Bot is ready. Logged in as {bot.user}")
    print("------")

    bot.music_bot = MusicBot(bot, youtube)

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
                logger.info(f"Loaded cog: {extension}", extra={'cog': extension})
            except Exception as e:
                logger.error(f"Failed to load cog {extension}: {e}", exc_info=True, extra={'cog': extension})

async def start_bot():
    await load_cogs()
    await bot.start(os.getenv("DISCORD_BOT_TOKEN"))

# --- Start Bot and Flask App ---
async def main():
    # Run Flask app in a separate thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))))
    flask_thread.daemon = True
    flask_thread.start()
    
    await start_bot()

if __name__ == "__main__":
    asyncio.run(main())