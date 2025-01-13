import discord
import yt_dlp as youtube_dl
import os
import asyncio
import logging
import sys
from googleapiclient.discovery import build

logger = logging.getLogger('discord')

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
        self.youtube = youtube  # YouTube Data API client
        self.song_queue = asyncio.Queue()
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': 'music/%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'cookiefile': '/app/cookies.txt'
        }
        self.ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        self.currently_playing = None
        self.voice_lock = asyncio.Lock()
        self.disconnect_timer = None

    async def play_song(self, ctx, song_info):
        """Plays a song."""
        async with self.voice_lock:
            voice_client = ctx.voice_client

            if voice_client is None:
                logger.error("Voice client is None in play_song.")
                return

            try:
                filename = song_info['filename']

                # Ensure the file exists before attempting to play it
                if not os.path.exists(filename):
                    logger.error(f"File not found: {filename}")
                    await ctx.channel.send("The requested song could not be found.")
                    await self.song_finished(ctx)
                    return

                # Play the song
                loop = asyncio.get_event_loop()
                player = discord.FFmpegPCMAudio(filename, **self.ffmpeg_options)
                voice_client.play(player, after=lambda e: loop.call_soon_threadsafe(self.bot.loop.create_task, self.song_finished(ctx)))
                self.currently_playing = song_info
                logger.info(f"Playing '{song_info['title']}' in {ctx.guild.name}", extra={
                    'song_info': {
                        'title': song_info['title'],
                        'url': song_info['url'],
                        'guild': ctx.guild.name
                    }
                })

                # Send a message to the text channel
                embed = discord.Embed(color=discord.Color.blue())
                embed.description = f"Now playing: [{song_info['title']}]({song_info['url']})"
                embed.set_thumbnail(url=song_info.get('thumbnail'))
                await ctx.channel.send(embed=embed)

            except Exception as e:
                logger.error(f"Error in play_song: {e}", exc_info=True)
                await ctx.channel.send("An error occurred while trying to play the song.")
                await self.song_finished(ctx)

    async def song_finished(self, ctx):
        # If bot is alone, start timer
        if self.is_voice_empty(ctx):
            await self.start_disconnect_timer(ctx)
        # Otherwise, play next song
        else:
            await self.play_next_song(ctx)

    async def play_next_song(self, ctx):
        """Plays the next song in the queue."""
        try:
            next_song_info = await self.song_queue.get()
            self.currently_playing = next_song_info
            await self.play_song(ctx, next_song_info)
        except asyncio.QueueEmpty:
            logger.info(f"Queue is empty in {ctx.guild.name}.")
            # Add logging for when a song is skipped
            if ctx.voice_client.is_playing():
                logger.info(f"Song skipped in {ctx.guild.name}.")
            self.currently_playing = None
        finally:
            self.song_queue.task_done()

    async def add_to_queue(self, ctx, url):
        """Adds a song to the queue and starts downloading in the background."""
        try:
            # Use the YouTube Data API to search for the video
            search_response = self.youtube.search().list(
                q=url,
                part="snippet",
                type="video",
                maxResults=1
            ).execute()

            if not search_response.get('items'):
                await ctx.channel.send("Could not find any results for your query.")
                return None

            # Get the first result
            video_id = search_response['items'][0]['id']['videoId']
            video_title = search_response['items'][0]['snippet']['title']
            thumbnail = search_response['items'][0]['snippet']['thumbnails']['default']['url']
            url = f"https://www.youtube.com/watch?v={video_id}"

            with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)

            song_info = {
                'ctx': ctx,
                'url': url,
                'title': video_title,
                'thumbnail': thumbnail,
                'filename': filename
            }

            if os.path.exists(filename):
                # Song is already downloaded, add it directly to the song_queue
                logger.info(f"'{song_info['title']}' found in cache.", extra={
                    'action': 'add_to_queue',
                    'source': 'cache',
                    'guild': ctx.guild.name
                })
                if not ctx.voice_client.is_playing() and self.currently_playing == None:
                    await self.play_song(ctx, song_info)
                else:
                    await self.song_queue.put(song_info)
                    # Send a message to the text channel
                    embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())
                    embed.set_thumbnail(url=song_info.get('thumbnail'))
                    await ctx.channel.send(embed=embed)

                return song_info
            else:
                # Add song to download queue
                logger.info(f"Added '{song_info['title']}' to the download queue in {ctx.guild.name}", extra={
                    'action': 'add_to_queue',
                    'source': 'download',
                    'guild': ctx.guild.name
                })
                asyncio.create_task(self.download_and_play(ctx, song_info))

                return song_info

        except Exception as e:
            logger.error(f"Error in add_to_queue: {e}", exc_info=True)
            await ctx.channel.send("An error occurred while adding the song to the queue.")

    async def download_song(self, song_info):
        """Downloads a song using yt_dlp."""
        try:
            logger.info(f"Downloading '{song_info['title']}'", extra={
                'action': 'download',
                'url': song_info['url'],
                'guild': song_info['ctx'].guild.name
            })
            loop = asyncio.get_event_loop()
            with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
                await loop.run_in_executor(None, lambda: ydl.download([song_info['url']]))

            logger.info(f"Finished downloading '{song_info['title']}'", extra={
                'action': 'download_finished',
                'url': song_info['url'],
                'guild': song_info['ctx'].guild.name
            })

        except Exception as e:
            logger.error(f"Error downloading {song_info['url']}: {e}", exc_info=True)

    async def start_disconnect_timer(self, ctx):
        """Starts the disconnect timer."""
        logger.info(f"Starting disconnect timer for {ctx.guild.name}", extra={
            'action': 'start_disconnect_timer',
            'guild': ctx.guild.name
        })
        if self.disconnect_timer:
            self.disconnect_timer.cancel()  # Cancel any existing timer

        self.disconnect_timer = self.bot.loop.create_task(self.disconnect_after_delay(ctx))

    async def disconnect_after_delay(self, ctx):
        """Disconnects from the voice channel after a delay if no one else is in the channel."""
        await asyncio.sleep(10)  # Wait for 10 seconds

        voice_client = ctx.guild.voice_client
        if voice_client:
            # Check if bot is alone in the voice channel
            if self.is_voice_empty(ctx):
                logger.info(f"Bot is alone in the voice channel in {ctx.guild.name}. Disconnecting.", extra={
                    'action': 'disconnect',
                    'guild': ctx.guild.name
                })
                await voice_client.disconnect()
                self.currently_playing = None
                logger.info(f"Exiting the bot with code 0.")
                sys.exit(0)  # Exit with code 0

    def is_voice_empty(self, ctx):
        """Checks if the voice channel is empty (except for the bot)."""
        voice_client = ctx.guild.voice_client
        if voice_client:
            return len(voice_client.channel.members) == 1
        return True  # No voice client means it's considered empty

    def get_currently_playing(self):
        """Returns information about the currently playing song or None."""
        return self.currently_playing