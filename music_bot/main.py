import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import os
import uvicorn
from dotenv import load_dotenv
import logging
import asyncio
from bot import MusicBot
from googleapiclient.discovery import build
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys

from routes import currently_playing
from routes import queue


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
        log_entry.update(record.__dict__.get('extra', {}))

        return json.dumps(log_entry)

# Configure logging
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
ytdl_logger = logging.getLogger('ytdl')
ytdl_logger.setLevel(logging.DEBUG)

# Log to a file
file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
file_handler.setFormatter(GoogleCloudLogFormatter())
logger.addHandler(file_handler)
ytdl_logger.addHandler(file_handler)

# Log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(GoogleCloudLogFormatter())
logger.addHandler(console_handler)
ytdl_logger.addHandler(console_handler)

# --- Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# --- Bot Setup ---
bot = commands.Bot(command_prefix=commands.when_mentioned_or("/"), intents=intents)

# --- YouTube Data API Setup ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# --- FastAPI Setup for Health Check and API Endpoints ---
app = FastAPI()

# CORS configuration (adjust origins as needed for your frontend)
origins = [ 
    "https://poggles-discord-bot-235556599709.us-east1.run.app",
    "https://music-bot-frontend-235556599709.us-central1.run.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

app.include_router(currently_playing.init_router(bot))
app.include_router(queue.init_router(bot))

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
    

# --- Command: /ping ---
@bot.tree.command(name="ping", description="Replies with Pong!")
async def ping(interaction: discord.Interaction):
    logger.info(f"'/ping' command used by {interaction.user} in {interaction.guild}")
    await interaction.response.send_message("Pong!", ephemeral=True)

# --- Load Cogs ---
async def load_cogs():
    commands_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands")
    logger.info(f"Loading cogs from: {commands_dir}")
    
    try:
        files = [f for f in os.listdir(commands_dir) 
                if f.endswith('.py') and not f.startswith('__')]
        logger.info(f"Found cog files: {files}")
        
        for filename in files:
            cog_name = filename[:-3]  # Remove .py extension
            # Change the import path to be relative
            full_path = f"commands.{cog_name}"
            
            try:
                logger.info(f"Attempting to load cog: {full_path}")
                await bot.load_extension(full_path)
                logger.info(f"Successfully loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {str(e)}", exc_info=True)
                continue
                
        logger.info(f"Cog loading complete. Loaded {len(files)} cogs")
    except Exception as e:
        logger.error(f"Failed to load cogs: {str(e)}", exc_info=True)

async def start_bot():
    bot.music_bot = MusicBot(bot, youtube)
    await load_cogs()
    await bot.start(os.getenv("DISCORD_BOT_TOKEN"))

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)