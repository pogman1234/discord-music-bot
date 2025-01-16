from discord.ext import commands
from discord import app_commands
import discord
import logging
import json
import time

logger = logging.getLogger('discord-music-bot')

class PauseCog(commands.Cog):
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

    @app_commands.command(name="pause", description="Pauses the currently playing song")
    async def pause(self, interaction: discord.Interaction):
        """Pauses the currently playing song."""
        try:
            await interaction.response.defer()

            voice_client = interaction.guild.voice_client

            if not voice_client or not voice_client.is_connected():
                self._log(f"'pause' command used by {interaction.user} in {interaction.guild} - Not in voice channel")
                await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
                return

            if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
                if voice_client.is_playing():
                    voice_client.pause()
                    self._log(f"'pause' command used by {interaction.user} in {interaction.guild} - Paused playback")
                    await interaction.followup.send("Paused the song.")
                else:
                    self._log(f"'pause' command used by {interaction.user} in {interaction.guild} - Nothing playing")
                    await interaction.followup.send("Nothing is playing.", ephemeral=True)
            else:
                self._log(f"'pause' command used by {interaction.user} in {interaction.guild} - User not in same channel")
                await interaction.followup.send("You need to be in the same voice channel as the bot to use this command.", ephemeral=True)
        except Exception as e:
            self._log(f"Error in pause command: {e}", "ERROR")
            await interaction.followup.send("An error occurred while trying to pause.", ephemeral=True)

async def setup(bot):
    logger.info("Loading pause cog")
    await bot.add_cog(PauseCog(bot))