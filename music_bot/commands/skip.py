from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Skip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="skip", description="Skips the currently playing song")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Skip command initiated for guild {guild_id}")

        if not ctx.voice_client:
            logger.warning(f"Skip command failed - bot not connected to voice channel in guild {guild_id}")
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        queue_manager = music_bot.get_queue_manager(guild_id)
        if not queue_manager.is_playing:
            logger.warning(f"Skip command failed - no music playing in guild {guild_id}")
            await interaction.followup.send("Not playing any music right now.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            logger.warning(f"Skip command failed - user not in bot's voice channel in guild {guild_id}")
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to skip songs.", 
                ephemeral=True
            )
            return

        try:
            # Get current song before skipping
            current_song = queue_manager.get_currently_playing()
            if current_song:
                logger.info(f"Skipping current song '{current_song.title}' in guild {guild_id}")
            
            # Stop current playback
            music_bot.audio_player.stop(guild_id)
            logger.info(f"Stopped audio playback for guild {guild_id}")
            
            # Clear current song in queue manager
            await queue_manager.clear_current()
            logger.info(f"Cleared current song state for guild {guild_id}")
            
            response = "Skipped the current song."
            if current_song:
                response = f"Skipped: {current_song.title}"
                
            await interaction.followup.send(response, ephemeral=True)
            logger.info(f"Skip command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing skip command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("Error skipping song.", ephemeral=True)

async def setup(bot):
    logger.info("Loading skip cog")
    await bot.add_cog(Skip(bot))