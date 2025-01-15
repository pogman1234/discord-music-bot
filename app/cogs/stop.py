from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class StopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    @app_commands.command(name="stop", description="Stops then clears the entire song queue")
    async def stop(self, interaction: discord.Interaction):
        """Stops and clears the entire song queue."""
        await interaction.response.defer()

        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
            self.music_bot.queue.clear()
            if voice_client.is_playing():
                voice_client.stop()  # Stop the currently playing song
            await interaction.followup.send("Stopped and cleared the song queue.")
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to stop the bot.", ephemeral=True)

async def setup(bot):
    logger.info("Loading stop cog")
    await bot.add_cog(StopCog(bot))