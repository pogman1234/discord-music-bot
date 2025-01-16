from discord.ext import commands
from discord import app_commands
import discord
import logging
import json
import time

logger = logging.getLogger('discord-music-bot')

class SkipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    def _log(self, message, severity="INFO", **kwargs):
        entry = {
            "message": message,
            "severity": severity,
            "timestamp": {"seconds": int(time.time()), "nanos": 0},
            **kwargs,
        }
        logger.log(logging.getLevelName(severity), json.dumps(entry))

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        """Skips the currently playing song."""
        try:
            await interaction.response.defer()

            voice_client = interaction.guild.voice_client

            if not voice_client or not voice_client.is_playing():
                self._log(f"'skip' command used by {interaction.user} in {interaction.guild} - Nothing playing")
                await interaction.followup.send("Not playing any music right now.", ephemeral=True)
                return

            if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
                self._log(f"'skip' command used by {interaction.user} in {interaction.guild} - Skipping current song")
                voice_client.stop()  # Stop the current song, which will trigger the 'after' callback
                await interaction.followup.send("Skipped the current song.")
            else:
                self._log(f"'skip' command used by {interaction.user} in {interaction.guild} - User not in same channel")
                await interaction.followup.send("You need to be in the same voice channel as the bot to skip songs.", ephemeral=True)
        except Exception as e:
            self._log(f"Error in skip command: {e}", "ERROR")
            await interaction.followup.send("An error occurred while trying to skip.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(SkipCog(bot))