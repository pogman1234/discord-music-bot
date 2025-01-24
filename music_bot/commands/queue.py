from discord.ext import commands
from discord import app_commands
import discord
import json
import time
import logging

logger = logging.getLogger(__name__)

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="Displays the current song queue")
    async def queue(self, interaction: discord.Interaction):
        """Displays the current song queue."""
        try:
            await interaction.response.defer()

            queue_info = self.bot.music_bot.queue_manager.get_queue_info()
            if not queue_info:
                self._log(f"'queue' command used by {interaction.user} in {interaction.guild} - Queue is empty", "INFO")
                await interaction.followup.send("The queue is empty.")
                return

            queue_list = ""
            
            # Safely copy items from the queue to a list (no need to modify the queue directly)
            queue_items = list(self.bot.music_bot.queue)  # Access the deque directly
            for i, song_info in enumerate(queue_items):
                queue_list += f"{i+1}. [{song_info['title']}]({song_info['url']})\n"

            embed = discord.Embed(title="Current Queue", description=queue_list, color=discord.Color.blue())
            self._log(f"'queue' command used by {interaction.user} in {interaction.guild} - Displaying queue", "INFO")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            self._log(f"'queue' command failed: {e}", "ERROR")
            await interaction.followup.send("An error occurred while displaying the queue.")

    def _log(self, message, severity="INFO", **kwargs):
        entry = {
            "message": message,
            "severity": severity,
            "timestamp": {"seconds": int(time.time()), "nanos": 0},
            "component": "queue_cog",
            **kwargs,
        }
        logger.log(logging.getLevelName(severity), json.dumps(entry))

async def setup(bot):
    logger.info("Loading queue cog")
    await bot.add_cog(Queue(bot))