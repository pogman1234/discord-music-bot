from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stop", description="Stops then clears the entire song queue")
    async def stop(self, interaction: discord.Interaction):
        """Stops and clears the entire song queue."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot

        # Check voice states
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to stop the bot.", 
                ephemeral=True
            )
            return

        try:
            # Stop playback
            music_bot.audio_player.stop()
            
            # Clear queue and reset state
            await music_bot.queue_manager.clear()
            await music_bot.queue_manager.clear_current()
            
            await interaction.followup.send("Stopped and cleared the song queue.")
            
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            await interaction.followup.send("Error stopping playback.", ephemeral=True)

async def setup(bot):
    logger.info("Loading stop cog")
    await bot.add_cog(Stop(bot))