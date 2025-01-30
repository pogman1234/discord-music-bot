from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stop", description="Stops the currently playing song and clears the queue")
    async def stop(self, interaction: discord.Interaction):
        """Stops the currently playing song and clears the queue."""
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Stop command initiated for guild {guild_id}")

        # Check voice states
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            logger.warning(f"Stop command failed - bot not connected to voice channel in guild {guild_id}")
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            logger.warning(f"Stop command failed - user not in bot's voice channel in guild {guild_id}")
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to stop playback.", 
                ephemeral=True
            )
            return

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            
            # Get current song before stopping
            current_song = queue_manager.get_currently_playing()
            if current_song:
                logger.info(f"Currently playing '{current_song.title}' in guild {guild_id}")
            
            # Stop audio player first
            if ctx.voice_client and ctx.voice_client.is_playing():
                music_bot.audio_player.stop(guild_id)
                logger.info(f"Stopped audio playback for guild {guild_id}")
            
            # Clear queue next
            await queue_manager.clear()
            logger.info(f"Cleared queue for guild {guild_id}")
            
            # Finally clear current song state
            await queue_manager.clear_current()
            logger.info(f"Cleared current song state for guild {guild_id}")
            
            # Prepare response message
            response = "Playback stopped and queue cleared."
            if current_song:
                response = f"Stopped playing: {current_song.title} and cleared queue."
                
            await interaction.followup.send(response, ephemeral=True)
            logger.info(f"Stop command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing stop command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to stop playback.", ephemeral=True)

async def setup(bot):
    logger.info("Loading stop command cog")
    await bot.add_cog(Stop(bot))