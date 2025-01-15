from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class PlayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    @app_commands.command(name="play", description="Plays audio from a YouTube URL or search term")
    async def play(self, interaction: discord.Interaction, *, arg: str):
        """Plays audio from a YouTube URL or search term."""
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You are not connected to a voice channel!")
            return

        voice_channel = interaction.user.voice.channel

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            logger.info(f"Connecting to voice channel: {voice_channel.name}")
            voice_client = await voice_channel.connect()
        else:
            logger.info(f"Moving to voice channel: {voice_channel.name}")
            await voice_client.move_to(voice_channel)

        # Add to queue (only add to queue here)
        logger.info(f"Adding to queue: {arg}")
        ctx = await self.bot.get_context(interaction) # Create ctx from interaction
        song_info = await self.music_bot.add_to_queue(ctx, arg)

        if song_info:
            logger.info(f"Song info: {song_info}")

            # Send "Added to queue" message with clickable title
            embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())

            # Get the video thumbnail
            try:
                video_id = song_info['url'].split("watch?v=")[1]
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                embed.set_thumbnail(url=thumbnail_url)
            except Exception as e:
                logger.error(f"Error getting thumbnail: {e}")

            await interaction.followup.send(embed=embed)

        else:
            logger.error("Error: song_info is None")
            await interaction.followup.send("An error occurred while processing the song.")

    def is_playing(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(PlayCog(bot))