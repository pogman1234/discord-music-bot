from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Skip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot  # bot is your MusicBot instance

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        """Skips the currently playing song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await interaction.followup.send("Not playing any music right now.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            # Stop the current song, which will trigger the 'after' callback in 'play_next_song'
            ctx.voice_client.stop()
            await interaction.followup.send("Skipped the current song.")
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to skip songs.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(Skip(bot))