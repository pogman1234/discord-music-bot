from discord.ext import commands
from discord import app_commands
import discord
import logging
import asyncio

logger = logging.getLogger(__name__)

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Clears the current song queue")
    async def clear(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Clear command initiated for guild {guild_id}")

        if not ctx.voice_client:
            logger.warning(f"Clear command failed - bot not connected to voice channel in guild {guild_id}")
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            logger.warning(f"Clear command failed - user not in bot's voice channel in guild {guild_id}")
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to clear the queue.", 
                ephemeral=True
            )
            return

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            await queue_manager.clear()
            logger.info(f"Cleared queue for guild {guild_id}")
            
            await interaction.followup.send("Queue cleared.", ephemeral=True)
            logger.info(f"Clear command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing clear command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to clear the queue.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Clear(bot))