from discord.ext import commands
from discord import app_commands
import discord
import logging
import asyncio

logger = logging.getLogger(__name__)

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Clears the song queue")
    async def clear(self, interaction: discord.Interaction):
        """Clears the entire song queue."""
        try:
            await interaction.response.defer()
            ctx = await self.bot.get_context(interaction)
            music_bot = self.bot.music_bot

            # Validate voice states
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
                return

            if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
                await interaction.followup.send(
                    "You need to be in the same voice channel as the bot to clear the queue.", 
                    ephemeral=True
                )
                return

            # Get queue length before clearing
            queue_length = music_bot.queue_manager.get_queue_length()
            
            # Clear queue using queue manager
            await music_bot.queue_manager.clear()
            
            # Ensure queue processing task continues
            if not music_bot.queue_task or music_bot.queue_task.done():
                music_bot.queue_task = asyncio.create_task(music_bot.process_queue(ctx))
                
            logger.info(f"Queue cleared by user command. Items cleared: {queue_length}")
            
            try:
                await interaction.followup.send(f"Cleared {queue_length} songs from the queue.")
                logger.debug("Clear confirmation message sent successfully")
            except Exception as msg_error:
                logger.error(f"Failed to send clear confirmation: {msg_error}")
                
        except Exception as e:
            logger.error(f"Error in clear command: {e}")
            try:
                await interaction.followup.send("Error clearing the queue.", ephemeral=True)
            except:
                logger.error("Failed to send error message")

async def setup(bot):
    logger.info("Loading clear cog")
    await bot.add_cog(Clear(bot))