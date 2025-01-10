import discord
from discord.ext import commands
from main import bot

async def setup(bot):  # Add this setup function
    bot.tree.command(name="stop", description="Stops the music and disconnects the bot.")(stop)

@commands.command()
async def stop(interaction: discord.Interaction):
    """Stops the music and disconnects the bot from the voice channel."""
    try:
        voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await interaction.response.send_message("Stopped the music and disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)