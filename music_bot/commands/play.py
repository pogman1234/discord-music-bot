from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a song from YouTube")
    async def play(self, interaction: discord.Interaction, song: str):
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        guild_id = ctx.guild.id
        
        logger.info(f"Play command initiated for guild {guild_id} with query: {song}")

        try:
            # Get voice states
            voice_client = ctx.voice_client
            voice_channel = ctx.author.voice.channel if ctx.author.voice else None

            if not voice_channel:
                logger.warning(f"Play command failed - user not in voice channel in guild {guild_id}")
                await interaction.followup.send("You need to be in a voice channel to play music.", ephemeral=True)
                return

            # Handle voice client connection
            if not voice_client:
                logger.info(f"Connecting to voice channel: {voice_channel.name} in guild {guild_id}")
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                logger.info(f"Moving to voice channel: {voice_channel.name} in guild {guild_id}")
                await voice_client.move_to(voice_channel)

            # Add to queue
            logger.info(f"Adding to queue: {song} for guild: {guild_id}")
            song_info = await self.bot.music_bot.add_to_queue(ctx, song, guild_id)

            if song_info:
                logger.info(f"Added song to queue for guild {guild_id}: {song_info}")
                await interaction.followup.send(f"Added to queue: {song_info['title']}", ephemeral=True)
            else:
                logger.warning(f"Could not find song for guild {guild_id}: {song}")
                await interaction.followup.send("Could not find that song.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error executing play command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to play that song.", ephemeral=True)

    @staticmethod
    def is_playing(ctx) -> bool:
        """Check if bot is currently playing in the guild"""
        voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(Play(bot))