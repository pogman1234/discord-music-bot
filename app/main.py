#Updated main.py
import asyncio
import os
import json
import logging
import sys
import signal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.discord_bot import bot, youtube  # Import bot and youtube
from .core.bot import MusicBot

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

# --- FastAPI Setup ---
app = FastAPI(title="Discord Music Bot API")

# Mount the static files from the React build
app.mount("/", StaticFiles(directory="/app/frontend/build", html=True), name="static")

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

# Create MusicBot instance on startup
@app.on_event("startup")
async def startup_event():
    bot.music_bot = MusicBot(bot, youtube)
    await load_cogs()
    asyncio.create_task(run_discord_bot())

# Import routes after app is defined
from .api import routes
app.include_router(routes.router, prefix="/api")

# Function to run the Discord bot
async def run_discord_bot():
    try:
        await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}", exc_info=True)
    finally:
        if not shutdown_event.is_set():
            await bot.close()
            
# Signal handler function
def handle_exit(signum, frame):
    print("Shutting down gracefully...")
    shutdown_event.set()
    if bot:
        asyncio.create_task(bot.close())

# Set signal handlers
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# Main function
async def main():
    # Create the run_discord_bot task but don't wait for it here
    discord_task = asyncio.create_task(run_discord_bot())

    # You can add other tasks here if needed

    # Keep the main function alive to handle signals
    await discord_task

# Entry point for Gunicorn (and allows for local testing)
if __name__ == "__main__":
    asyncio.run(main())