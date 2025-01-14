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
            logger.info(f"Connecting to voice channel: {voice_channel.name}")
            voice_client = await voice_channel.connect()
        else:
            logger.info(f"Moving to voice channel: {voice_channel.name}")
            await voice_client.move_to(voice_channel)

        # Add to queue
        logger.info(f"Adding to queue: {arg}")
        song_info = await self.bot.music_bot.add_to_queue(ctx, arg)

        if song_info:
            logger.info(f"Song info: {song_info}")
            if 'filepath' in song_info:
                logger.info(f"Attempting to play from: {song_info['filepath']}")
            else:
                logger.error("Filepath not found in song_info")
                await interaction.followup.send("Error: Could not find the audio file.")
                return

            def after_playing(error):
                if error:
                    logger.error(f'Error during playback: {error}')
                self.bot.loop.call_soon_threadsafe(self.bot.music_bot.play_next_song_callback, ctx)

            try:
                # Play the song
                if not self.is_playing(ctx):
                    voice_client.play(
                        discord.FFmpegPCMAudio(song_info['filepath']),
                        after=after_playing
                    )
                    await interaction.followup.send(f"Playing [{song_info['title']}](<{song_info['url']}>)")
                else:
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
            except Exception as e:
                logger.error(f"Error during playback: {e}")
                await interaction.followup.send("An error occurred during playback.")
        else:
            logger.error("Error: song_info is None")
            await interaction.followup.send("An error occurred while processing the song.")

    def is_playing(self, ctx):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(Play(bot))