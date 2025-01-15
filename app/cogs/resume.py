from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class Resume(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="resume", description="Resumes the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resumes the currently paused song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if ctx.author.voice and ctx.author.voice.channel == ctx.voice_client.channel:
            if ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                await interaction.followup.send("Resumed the song.")
            else:
                await interaction.followup.send("Nothing is paused.", ephemeral=True)
        else:
            await interaction.followup.send("You need to be in the same voice channel as the bot to use this command.", ephemeral=True)

async def setup(bot):
    logger.info("Loading resume cog")
    await bot.add_cog(Resume(bot))