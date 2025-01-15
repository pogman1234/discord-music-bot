from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger('discord')

class NowPlaying(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="nowplaying", description="Shows the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Displays information about the currently playing song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if self.bot.music_bot.current_song:
            song_info = self.bot.music_bot.current_song
            title = song_info['title']
            url = song_info['url']

            embed = discord.Embed(title="Now Playing", description=f"[{title}]({url})", color=discord.Color.blue())

            # Add thumbnail (if available)
            try:
                video_id = url.split("watch?v=")[1]
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                embed.set_thumbnail(url=thumbnail_url)
            except:
                pass

            await interaction.followup.send(embed=embed)

        else:
            await interaction.followup.send("Nothing is currently playing.", ephemeral=True)

async def setup(bot):
    logger.info("Loading nowplaying cog")
    await bot.add_cog(NowPlaying(bot))