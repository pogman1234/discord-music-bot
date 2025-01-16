from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Pause(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pause", description="Pauses the currently playing song")
    async def pause(self, interaction: discord.Interaction):
        """Pauses the currently playing song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            if ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                await interaction.followup.send("Paused the song.")
            else:
                await interaction.followup.send("Nothing is playing.", ephemeral=True)
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to use this command.", ephemeral=True)

async def setup(bot):
    logger.info("Loading pause cog")
    await bot.add_cog(Pause(bot))