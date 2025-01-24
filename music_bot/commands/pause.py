from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Pause(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pause", description="Pauses the currently playing song")
    async def pause(self, interaction: discord.Interaction):
        """Pauses the currently playing song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot

        # Check voice states
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to pause playback.", 
                ephemeral=True
            )
            return

        try:
            current_song = music_bot.get_current_song()
            if not current_song:
                await interaction.followup.send("No song is currently playing.", ephemeral=True)
                return

            if music_bot.audio_player.pause():
                await interaction.followup.send(f"Paused: {current_song['title']}")
            else:
                await interaction.followup.send("Nothing is playing.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error pausing playback: {e}")
            await interaction.followup.send("Error pausing playback.", ephemeral=True)

async def setup(bot):
    logger.info("Loading pause cog")
    await bot.add_cog(Pause(bot))