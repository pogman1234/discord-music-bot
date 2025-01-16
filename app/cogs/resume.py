from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class ResumeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    @app_commands.command(name="resume", description="Resumes the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resumes the currently paused song."""
        await interaction.response.defer()

        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if interaction.user.voice and interaction.user.voice.channel == voice_client.channel:
            if voice_client.is_paused():
                voice_client.resume()
                await interaction.followup.send("Resumed the song.")
            else:
                await interaction.followup.send("Nothing is paused.", ephemeral=True)
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to use this command.", ephemeral=True)

async def setup(bot):
    logger.info("Loading resume cog")
    await bot.add_cog(ResumeCog(bot))