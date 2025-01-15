from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stop", description="Stops then clears the entire song queue")
    async def stop(self, interaction: discord.Interaction):
        """Stops and clears the entire song queue."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            self.bot.music_bot.queue.clear()
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()  # Stop the currently playing song
            await interaction.followup.send("Stopped and cleared the song queue.")
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to stop the bot.", ephemeral=True)

async def setup(bot):
    logger.info("Loading stop cog")
    await bot.add_cog(Stop(bot))