import asyncio
import discord
from discord.ext import commands
from main import bot

async def setup(bot):  # Add this setup function
    bot.tree.command(name="play", description="Play a song from Spotify")(play_song)

@commands.command()
async def play_song(interaction: discord.Interaction, query: str):
    """Plays a song from Spotify based on the provided query."""
    try:
        # Check if the user is in a voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel to play music!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel

        # Connect to the voice channel
        try:
            voice_client = await voice_channel.connect()
            bot.voice_client = voice_client
        except discord.ClientException:
            # Already connected to a voice channel
            voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

        # Search for the song on Spotify
        results = bot.sp.search(q=query, type='track', limit=1)
        if not results['tracks']['items']:
            await interaction.response.send_message("Song not found on Spotify.", ephemeral=True)
            return

        track = results['tracks']['items'][0]
        track_url = track['external_urls']['spotify']

        # Add the track URL to the queue
        bot.song_queue.append(track)  # Add the track object to the queue

        # If not playing, start playing from the queue
        if not bot.voice_client.is_playing():
            await play_next(interaction)
        else:
            await interaction.response.send_message(f"Added to queue: {track['name']} - {track['artists'][0]['name']}")

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

async def play_next(interaction: discord.Interaction):
    """Plays the next song in the queue."""
    if not bot.song_queue:
        await interaction.response.send_message("Queue is empty.", ephemeral=True)
        return

    track = bot.song_queue.popleft()  # Get the next track from the queue

    # Get the user's Spotify playback device
    devices = bot.sp.devices()
    if not devices['devices']:
        await interaction.response.send_message("No active Spotify devices found.", ephemeral=True)
        return
    device_id = devices['devices'][0]['id']

    # Start playback on the user's device
    bot.sp.start_playback(device_id=device_id, uris=[track['uri']])

    await interaction.response.send_message(f"Now playing: {track['name']} - {track['artists'][0]['name']}")