from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Resume(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="resume", description="Resumes the currently paused song")
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Resume command initiated for guild {guild_id}")

        if not ctx.voice_client:
            logger.warning(f"Resume command failed - bot not connected to voice channel in guild {guild_id}")
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            logger.warning(f"Resume command failed - user not in bot's voice channel in guild {guild_id}")
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to resume playback.", 
                ephemeral=True
            )
            return

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            current_song = queue_manager.get_currently_playing()
            
            if not current_song:
                logger.warning(f"Resume command failed - no song to resume in guild {guild_id}")
                await interaction.followup.send("No song is currently paused.", ephemeral=True)
                return

            music_bot.audio_player.resume(guild_id)
            logger.info(f"Resumed playback of '{current_song.title}' in guild {guild_id}")
            
            await interaction.followup.send(f"Resumed: {current_song.title}", ephemeral=True)
            logger.info(f"Resume command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing resume command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("Error resuming playback.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Resume(bot))