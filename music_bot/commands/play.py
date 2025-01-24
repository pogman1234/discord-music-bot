from discord.ext import commands
from discord import app_commands
import discord
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_time: Dict[int, float] = {}

    @app_commands.command(
        name="play",
        description="Plays audio from a YouTube URL or search term"
    )
    @app_commands.describe(
        arg="YouTube URL or search term to play"
    )
    async def play(self, interaction: discord.Interaction, *, arg: str):
        """
        Plays audio from YouTube.
        
        Args:
            interaction: Discord interaction context
            arg: YouTube URL or search term
        """
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        guild_id = ctx.guild.id

        # Spam prevention
        current_time = discord.utils.utcnow().timestamp()
        if guild_id in self.last_message_time:
            if current_time - self.last_message_time[guild_id] < 2:
                logger.debug("Skipping duplicate message")
                return

        # Voice state validation
        if not ctx.author.voice:
            await interaction.followup.send(
                "You are not connected to a voice channel!",
                ephemeral=True
            )
            return

        voice_channel = ctx.author.voice.channel
        
        try:
            # Handle voice client
            voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            if voice_client is None:
                logger.info(f"Connecting to voice channel: {voice_channel.name}")
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                logger.info(f"Moving to voice channel: {voice_channel.name}")
                await voice_client.move_to(voice_channel)

            # Add to queue
            logger.info(f"Adding to queue: {arg}")
            song_info = await self.bot.music_bot.add_to_queue(ctx, arg)

            if song_info:
                logger.info(f"Song info: {song_info}")
                await interaction.followup.send(f"Added to queue: {song_info['title']}")
                self.last_message_time[guild_id] = current_time
            else:
                await interaction.followup.send(
                    "Could not find that song.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error playing song: {str(e)}")
            await interaction.followup.send(
                "An error occurred while trying to play that song.",
                ephemeral=True
            )

    @staticmethod
    def is_playing(ctx) -> bool:
        """Check if bot is currently playing in the guild"""
        voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(Play(bot))