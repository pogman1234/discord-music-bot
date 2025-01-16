from discord.ext import commands
from discord import app_commands
import discord
import logging
import json
import time

logger = logging.getLogger('discord-music-bot')

class NowPlayingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_bot = bot.music_bot

    def _log(self, message, severity="INFO", **kwargs):
        entry = {
            "message": message,
            "severity": severity,
            "timestamp": {"seconds": int(time.time()), "nanos": 0},
            **kwargs,
        }
        logger.log(logging.getLevelName(severity), json.dumps(entry))

    @app_commands.command(name="nowplaying", description="Shows the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Displays information about the currently playing song."""
        try:
            await interaction.response.defer()

            if not interaction.guild.voice_client:
                self._log(f"'nowplaying' command used by {interaction.user} in {interaction.guild} - Not in voice channel")
                await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
                return

            if self.music_bot.current_song:
                song_info = self.music_bot.current_song
                title = song_info['title']
                url = song_info['url']

                embed = discord.Embed(title="Now Playing", description=f"[{title}]({url})", color=discord.Color.blue())

                try:
                    video_id = url.split("watch?v=")[1]
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                    embed.set_thumbnail(url=thumbnail_url)
                except Exception as e:
                    self._log(f"Error getting thumbnail: {e}", "ERROR")

                self._log(f"'nowplaying' command used by {interaction.user} in {interaction.guild} - Playing: {title}")
                await interaction.followup.send(embed=embed)
            else:
                self._log(f"'nowplaying' command used by {interaction.user} in {interaction.guild} - Nothing playing")
                await interaction.followup.send("Nothing is currently playing.", ephemeral=True)
        except Exception as e:
            self._log(f"Error in nowplaying command: {e}", "ERROR")
            await interaction.followup.send("An error occurred while getting the current song.", ephemeral=True)

async def setup(bot):
    logger.info("Loading nowplaying cog")
    await bot.add_cog(NowPlayingCog(bot))