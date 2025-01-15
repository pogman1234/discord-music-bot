import asyncio
import os
import json
import logging
import sys
import signal
from fastapi.middleware.cors import CORSMiddleware
import discord
from discord.ext import commands
from fastapi import FastAPI, Depends
from uvicorn import Config, Server
from dotenv import load_dotenv
from googleapiclient.discovery import build

from .core.discord_bot import bot, youtube  # Import bot and youtube
from .core.bot import MusicBot

# --- Load environment variables ---
load_dotenv()

# --- Logging Setup (Adjusted for Cloud Run) ---
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

        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        log_entry.update(record.__dict__.get('extra', {}))
        return json.dumps(log_entry)

# Configure logging
logger = logging.getLogger('discord-music-bot')
logger.setLevel(logging.INFO)
ytdl_logger = logging.getLogger('ytdl')
ytdl_logger.setLevel(logging.INFO)

# Log to console (Cloud Run automatically captures stdout/stderr)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(GoogleCloudLogFormatter())
logger.addHandler(console_handler)
ytdl_logger.addHandler(console_handler)

# --- Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Needed for reading message content
intents.voice_states = True  # Needed for voice-related events

# --- Bot Setup ---
bot = commands.Bot(command_prefix=commands.when_mentioned_or("/"), intents=intents)

# --- YouTube Data API Setup ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# --- FastAPI Setup ---
app = FastAPI(title="Discord Music Bot API")
app.include_router(routes.router, prefix="/api")

# --- CORS Configuration ---
origins = [
    "https://poggles-discord-bot-235556599709.us-east1.run.app",  # Replace with your React app's URL on Cloud Run
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health Check Endpoint ---
@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

# --- Load Cogs ---
async def load_cogs():
    for filename in os.listdir("./app/cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            extension = filename[:-3]
            try:
                await bot.load_extension(f"app.cogs.{extension}")
                logger.info(f"Loaded cog: {extension}", extra={'cog': extension})
            except Exception as e:
                logger.error(f"Failed to load cog {extension}: {e}", exc_info=True, extra={'cog': extension})

# Global variable to indicate shutdown
shutdown_event = asyncio.Event()

# Make the music_bot instance accessible (moved up)
def get_music_bot():
    return bot.music_bot

# Import routes after get_music_bot is defined
from .api import routes  # Import routes here
app.include_router(routes.router, prefix="/api")

# Function to run the Discord bot
async def run_discord_bot():
    try:
        bot.music_bot = MusicBot(bot, youtube)
        await load_cogs()
        await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    finally:
        if not shutdown_event.is_set():
            await bot.close()

# Function to run the FastAPI server
async def run_fastapi_server():
    config = Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = Server(config)

    # Create a task for the server
    server_task = asyncio.create_task(server.serve())

    # Wait for either shutdown signal or server failure
    await asyncio.wait(
        [
            asyncio.create_task(shutdown_event.wait()),
            server_task
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # If shutdown is not set, it means the server exited unexpectedly
    if not shutdown_event.is_set():
        print("FastAPI server exited unexpectedly. Shutting down.")

    # Stop the server if it's still running
    if not server.should_exit:
        server.force_exit = True
        await server.shutdown()

    return server_task

# Signal handler function
def handle_exit(signum, frame):
    print("Shutting down gracefully...")
    shutdown_event.set()
    if bot:
        asyncio.create_task(bot.close())

# Set signal handlers
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# Main function to start both
async def main():
    # Start both the FastAPI server and the Discord bot concurrently
    fastapi_task = asyncio.create_task(run_fastapi_server())
    discord_task = asyncio.create_task(run_discord_bot())

    await asyncio.wait(
        [fastapi_task, discord_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

# Entry point for Gunicorn (and allows local testing)
if __name__ == "__main__":
    asyncio.run(main())