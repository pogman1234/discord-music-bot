from discord.ext import commands
from discord import app_commands
import discord
import validators
import asyncio
import logging

logger = logging.getLogger('discord')

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Plays audio from a YouTube URL or search term")
    async def play(self, interaction: discord.Interaction, *, arg: str):
        """Plays audio from a YouTube URL or search term."""
        await interaction.response.defer()

        ctx = await self.bot.get_context(interaction)

        if not ctx.author.voice:
            await interaction.followup.send("You are not connected to a voice channel!")
            return

        voice_channel = ctx.author.voice.channel

        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client is None:
            voice_client = await voice_channel.connect()
        else:
            await voice_client.move_to(voice_channel)

        # Add to queue
        song_info = await self.bot.music_bot.add_to_queue(ctx, arg)

        if song_info:
            if not self.is_playing(ctx):
                await interaction.followup.send(f"Playing [{song_info['title']}](<{song_info['url']}>)")
            else:
                # Send "Added to queue" message with clickable title
                embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())
                embed.set_thumbnail(url=song_info.get('thumbnail'))
                await interaction.followup.send(embed=embed)

    def is_playing(self, ctx):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(Play(bot))