from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord-music-bot')

class PlayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    @app_commands.command(name="play", description="Plays a song from a given URL or search query")
    async def play(self, interaction: discord.Interaction, *, query: str):
        """Plays a song from a given URL or search query."""
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel to use this command.", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        if not voice_client:
            logger.info(f"Connecting to voice channel: {voice_channel.name}")
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            logger.info(f"Moving to voice channel: {voice_channel.name}")
            await voice_client.move_to(voice_channel)

        logger.info(f"Adding to queue: {query}")
        ctx = await self.bot.get_context(interaction)
        song_info = await self.music_bot.add_to_queue(ctx, query)

        if song_info:
            logger.info(f"Song info: {song_info}")
            embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())

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

    def is_playing(self, ctx):
        voice_client = ctx.guild.voice_client
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(PlayCog(bot))