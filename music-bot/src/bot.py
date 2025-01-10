
import discord
from discord.ext import commands
import logging
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spotify API credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# Initialize the Spotify client
client_credentials_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

class MusicBot(commands.Bot):
    def __init__(self, intents, application_id):
        super().__init__(command_prefix='/', intents=intents, application_id=application_id)
        self.voice_client = None
        self.song_queue = deque()
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri="http://localhost:8080/callback",  # Replace with your actual redirect URI
            scope="user-read-playback-position user-modify-playback-state"
        ))

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.process_commands(message)

    async def setup_hook(self):
        # Sync commands globally
        await self.tree.sync()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Invalid command. Use `/help` to see available commands.", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: {error.param.name}", ephemeral=True)
        elif isinstance(error, commands.CommandInvokeError):
            original_error = error.original
            if isinstance(original_error, discord.HTTPException):
                if original_error.status == 403:
                    await ctx.send("I don't have permission to do that.", ephemeral=True)
                elif original_error.status == 500:
                    logger.exception(f"Internal server error: {original_error}")
                    await ctx.send("An unexpected error occurred on Discord's end.", ephemeral=True)
            else:
                logger.exception(f"An error occurred during command execution: {original_error}")
                await ctx.send("An unexpected error occurred.", ephemeral=True)
        else:
            logger.error(f"An error occurred: {error}")
            await ctx.send("An unexpected error occurred.", ephemeral=True)