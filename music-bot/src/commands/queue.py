import discord
from discord.ext import commands
from main import bot

bot = commands.command()

@bot.tree.command(name="queue", description="Shows the current queue.")
async def queue(interaction: discord.Interaction):
    """Displays the current queue of songs."""
    if not bot.song_queue:
        await interaction.response.send_message("The queue is empty.", ephemeral=True)
        return

    queue_string = "\n".join([f"{i+1}. {song}" for i, song in enumerate(bot.song_queue)])
    await interaction.response.send_message(f"**Current Queue:**\n{queue_string}")