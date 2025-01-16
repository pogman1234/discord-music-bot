from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Clears the song queue")
    async def clear(self, interaction: discord.Interaction):
        """Clears the entire song queue."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            self.bot.music_bot.queue.clear()
            await interaction.followup.send("Cleared the song queue.")
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to clear the queue.", ephemeral=True)

async def setup(bot):
    logger.info("Loading clear cog")
    await bot.add_cog(Clear(bot))