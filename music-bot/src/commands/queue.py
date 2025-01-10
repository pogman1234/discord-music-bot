from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="Displays the current song queue")
    async def queue(self, interaction: discord.Interaction):
        """Displays the current song queue."""
        await interaction.response.defer()

        if self.bot.music_bot.song_queue.empty():
            await interaction.followup.send("The queue is empty.")
            return

        queue_list = ""
        # Safely copy items from the queue to a list
        queue_items = list(self.bot.music_bot.song_queue._queue)
        for i, song_info in enumerate(queue_items):
            queue_list += f"{i+1}. [{song_info['title']}]({song_info['url']})\n"

        embed = discord.Embed(title="Current Queue", description=queue_list, color=discord.Color.blue())
        await interaction.followup.send(embed=embed)

async def setup(bot):
    logger.info("Loading queue cog")
    await bot.add_cog(Queue(bot))