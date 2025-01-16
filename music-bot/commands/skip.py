from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Skip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        """Skips the currently playing song."""
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await interaction.response.send_message("Not playing any music right now.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            # Stop the current song, which will trigger the 'after' callback in 'play_song'
            ctx.voice_client.stop()
            await interaction.response.send_message("Skipped the current song.")
        else:
            await interaction.response.send_message("You need to be in the same voice channel as the bot to skip songs.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(Skip(bot))