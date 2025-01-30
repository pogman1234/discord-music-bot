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
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Now playing command initiated for guild {guild_id}")

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            current_song = queue_manager.get_currently_playing()
            
            if not current_song:
                logger.info(f"No song currently playing in guild {guild_id}")
                await interaction.followup.send("No song is currently playing.", ephemeral=True)
                return

            logger.info(f"Currently playing '{current_song.title}' in guild {guild_id}")
            await interaction.followup.send(f"Now Playing: {current_song.title}", ephemeral=True)
            logger.info(f"Now playing command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing now playing command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to get the current song.", ephemeral=True)

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