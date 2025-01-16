from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class SkipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        """Skips the currently playing song."""
        await interaction.response.defer()

        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_playing():
            await interaction.followup.send("Not playing any music right now.", ephemeral=True)
            return

        if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
            # Stop the current song, which will trigger the 'after' callback in 'play_next_song'
            voice_client.stop()
            await interaction.followup.send("Skipped the current song.")
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to skip songs.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(SkipCog(bot))