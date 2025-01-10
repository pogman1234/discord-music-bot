import discord
from discord.ext import commands
from main import bot

async def setup(bot):  # Add this setup function
    bot.tree.command(name="pause", description="Pauses the currently playing song.")(pause)

@commands.command()
async def pause(interaction: discord.Interaction):
    """Pauses the currently playing song."""
    try:
        voice_client = bot.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Paused the music.", ephemeral=True)
        else:
            await interaction.response.send_message("I'm not playing anything right now.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)