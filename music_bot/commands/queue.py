from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="Displays the current song queue")
    async def queue(self, interaction: discord.Interaction):
        """Displays the current song queue."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Queue command initiated for guild {guild_id}")

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            queue = queue_manager.get_queue_info()
            
            if not queue:
                logger.info(f"Queue is empty for guild {guild_id}")
                await interaction.followup.send("The queue is currently empty.", ephemeral=True)
                return

            queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(queue)])
            logger.info(f"Retrieved queue info for guild {guild_id}: {len(queue)} songs")
            
            await interaction.followup.send(f"Current Queue:\n{queue_list}", ephemeral=True)
            logger.info(f"Queue command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing queue command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to display the queue.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Queue(bot))