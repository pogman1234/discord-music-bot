from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class NowPlaying(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="nowplaying", description="Shows the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Displays information about the currently playing song."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        current_song = music_bot.get_current_song()
        if current_song:
            # Create rich embed
            embed = discord.Embed(
                title="Now Playing", 
                description=f"[{current_song['title']}]({current_song['webpage_url']})", 
                color=discord.Color.blue()
            )

            # Add progress info if available
            if music_bot.audio_player.status.is_playing:
                progress = music_bot.audio_player.get_progress_string()
                embed.add_field(name="Progress", value=progress, inline=False)

            # Add thumbnail
            if current_song['thumbnail']:
                embed.set_thumbnail(url=current_song['thumbnail'])

            # Add duration if available
            if current_song['duration'] > 0:
                minutes = current_song['duration'] // 60
                seconds = current_song['duration'] % 60
                embed.add_field(
                    name="Duration", 
                    value=f"{minutes}:{seconds:02d}", 
                    inline=True
                )

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Nothing is currently playing.", ephemeral=True)

    @commands.command()
    async def progress(self, ctx):
        """Show current playback progress"""
        music_bot = self.bot.music_bot
        
        if not music_bot.audio_player.status.is_playing:
            await ctx.send("Nothing is playing.", ephemeral=True)
            return
            
        current_song = music_bot.get_current_song()
        if current_song:
            progress = music_bot.audio_player.get_progress_string()
            await ctx.send(f"🎵 {current_song['title']}\n⏳ {progress}")

async def setup(bot):
    logger.info("Loading nowplaying cog")
    await bot.add_cog(NowPlaying(bot))