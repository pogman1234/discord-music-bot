from discord.ext import commands
from discord import app_commands
import discord
import logging

logger = logging.getLogger(__name__)

class Pause(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pause", description="Pauses the currently playing song")
    async def pause(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ctx = await self.bot.get_context(interaction)
        music_bot = self.bot.music_bot
        guild_id = ctx.guild.id
        
        logger.info(f"Pause command initiated for guild {guild_id}")

        if not ctx.voice_client:
            logger.warning(f"Pause command failed - bot not connected to voice channel in guild {guild_id}")
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            logger.warning(f"Pause command failed - user not in bot's voice channel in guild {guild_id}")
            await interaction.followup.send(
                "You need to be in the same voice channel as the bot to pause playback.", 
                ephemeral=True
            )
            return

        try:
            queue_manager = music_bot.get_queue_manager(guild_id)
            current_song = queue_manager.get_currently_playing()
            
            if not current_song:
                logger.warning(f"Pause command failed - no song playing in guild {guild_id}")
                await interaction.followup.send("No song is currently playing.", ephemeral=True)
                return

            music_bot.audio_player.pause(guild_id)
            logger.info(f"Paused playback of '{current_song.title}' in guild {guild_id}")
            
            await interaction.followup.send(f"Paused: {current_song.title}", ephemeral=True)
            logger.info(f"Pause command completed successfully for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error executing pause command for guild {guild_id}: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while trying to pause playback.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Pause(bot))