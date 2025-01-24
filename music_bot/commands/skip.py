from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Skip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        """Skips the currently playing song."""
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot

        # Check if playing and user in correct channel
        if not ctx.voice_client:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return

        if not music_bot.queue_manager.is_playing:
            await interaction.response.send_message("Not playing any music right now.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            await interaction.response.send_message(
                "You need to be in the same voice channel as the bot to skip songs.", 
                ephemeral=True
            )
            return

        try:
            # Stop current playback
            music_bot.audio_player.stop()
            
            # Clear current song in queue manager
            await music_bot.queue_manager.clear_current()
            
            current = music_bot.get_current_song()
            if current:
                await interaction.response.send_message(f"Skipped: {current['title']}")
            else:
                await interaction.response.send_message("Skipped the current song.")

        except Exception as e:
            logger.error(f"Error skipping song: {e}")
            await interaction.response.send_message("Error skipping song.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(Skip(bot))