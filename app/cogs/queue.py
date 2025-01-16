from discord.ext import commands
from discord import app_commands
import discord
import logging
import json
import time

logger = logging.getLogger('discord-music-bot')

class QueueCog(commands.Cog):
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

    @app_commands.command(name="queue", description="Displays the current song queue")
    async def queue(self, interaction: discord.Interaction):
        """Displays the current song queue."""
        try:
            await interaction.response.defer()

            if not self.music_bot.queue:
                self._log(f"'queue' command used by {interaction.user} in {interaction.guild} - Queue is empty")
                await interaction.followup.send("The queue is empty.")
                return

            queue_list = ""
            queue_items = list(self.music_bot.queue)
            for i, song_info in enumerate(queue_items):
                queue_list += f"{i+1}. [{song_info['title']}]({song_info['url']})\n"

            embed = discord.Embed(title="Current Queue", description=queue_list, color=discord.Color.blue())
            self._log(f"'queue' command used by {interaction.user} in {interaction.guild} - Displaying queue")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            self._log(f"'queue' command failed: {e}", "ERROR")
            await interaction.followup.send("An error occurred while displaying the queue.")

async def setup(bot):
    logger.info("Loading queue cog")
    await bot.add_cog(QueueCog(bot))