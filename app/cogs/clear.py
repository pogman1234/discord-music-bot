from discord.ext import commands
from discord import app_commands
import discord
import logging
import json
import time

logger = logging.getLogger('discord-music-bot')

class ClearCog(commands.Cog):
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

    @app_commands.command(name="clear", description="Clears the song queue")
    async def clear(self, interaction: discord.Interaction):
        """Clears the entire song queue."""
        try:
            await interaction.response.defer()

            voice_client = interaction.guild.voice_client

            if not voice_client or not voice_client.is_connected():
                self._log(f"'clear' command used by {interaction.user} in {interaction.guild} - Not in voice channel")
                await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
                return

            if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
                self._log(f"'clear' command used by {interaction.user} in {interaction.guild} - Clearing queue")
                self.music_bot.queue.clear()
                await interaction.followup.send("Cleared the song queue.")
            else:
                self._log(f"'clear' command used by {interaction.user} in {interaction.guild} - User not in same channel")
                await interaction.followup.send("You need to be in the same voice channel as the bot to clear the queue.", ephemeral=True)
        except Exception as e:
            self._log(f"Error in clear command: {e}", "ERROR")
            await interaction.followup.send("An error occurred while trying to clear the queue.", ephemeral=True)

async def setup(bot):
    logger.info("Loading clear cog")
    await bot.add_cog(ClearCog(bot))