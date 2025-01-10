from discord.ext import commands
from discord import app_commands
import discord
import yt_dlp as youtube_dl
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
        try:
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

            # Check if the argument is a URL or a search term
            if not validators.url(arg):
                # Search for the song on YouTube
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'default_search': 'auto',
                    'logtostderr': False
                }
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(f"ytsearch:{arg}", download=False)
                        if 'entries' in info:
                            entry = info['entries'][0]
                            url = entry['webpage_url']
                        else:
                            await interaction.followup.send("Could not find any results for your query.")
                            return
                    except Exception as e:
                        logger.info(f"error {e}")
                        await interaction.followup.send("Could not find any results for your query.")
                        return
            else:
                url = arg

            # Add to queue
            song_info = await self.bot.music_bot.add_to_queue(ctx, url)

            if song_info:
                if not self.is_playing(ctx):
                    await interaction.followup.send(f"Playing [{song_info['title']}](<{url}>)")
                else:
                    # Send "Added to queue" message with clickable title
                    embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())
                    embed.set_thumbnail(url=song_info.get('thumbnail'))
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send("An error occurred while processing your request.")

    def is_playing(self, ctx):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    logger.info("Loading play cog")
    await bot.add_cog(Play(bot))