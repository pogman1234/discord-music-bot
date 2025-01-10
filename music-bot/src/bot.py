import discord
import yt_dlp as youtube_dl
import os
import asyncio
import logging
import sys
from threading import Thread, Lock
from queue import Queue

logger = logging.getLogger('discord')

class MusicBot:
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = asyncio.Queue()
        self.download_queue = Queue()
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
            'source_address': '0.0.0.0'
        }
        self.ffmpeg_options = {
            'options': '-vn',
        }
        self.download_thread = Thread(target=self.download_loop)
        self.download_thread.daemon = True
        self.download_thread.start()
        self.currently_playing = None
        self.voice_lock = asyncio.Lock()
        self.queue_lock = Lock()
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
                    return

                # Play the song
                player = discord.FFmpegPCMAudio(filename, **self.ffmpeg_options)
                voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.song_finished(ctx)))
                self.currently_playing = song_info
                logger.info(f"Playing '{song_info['title']}' in {ctx.guild.name}")

                # Send a message to the text channel
                embed = discord.Embed(color=discord.Color.blue())
                embed.description = f"Now playing: [{song_info['title']}]({song_info['url']})"
                embed.set_thumbnail(url=song_info.get('thumbnail'))
                await ctx.channel.send(embed=embed)

            except Exception as e:
                logger.error(f"Error in play_song: {e}")
                await ctx.channel.send("An error occurred while trying to play the song.")

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
        """Adds a song to the queue."""
        with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)

                song_info = {
                    'ctx': ctx,
                    'url': url,
                    'title': info.get('title', url),
                    'thumbnail': info.get('thumbnail', None),
                    'filename': filename
                }

                # Check if song is already in the queue or being downloaded
                with self.queue_lock:
                    if any(s['url'] == url for s in self.song_queue._queue) or any(s['url'] == url for s in self.download_queue.queue):
                        logger.info(f"'{song_info['title']}' is already in the queue or being downloaded.")
                        await ctx.channel.send(f"'{song_info['title']}' is already in the queue or being downloaded.")
                        return None

                if os.path.exists(filename):
                    # Song is already downloaded, add it directly to the song_queue
                    logger.info(f"'{song_info['title']}' found in cache.")
                    if not ctx.voice_client.is_playing() and self.currently_playing == None:
                        await self.play_song(ctx, song_info)
                    else:
                        await self.song_queue.put(song_info)

                    return song_info
                else:
                    # Add song to download queue
                    self.download_queue.put(song_info)
                    logger.info(f"Added '{song_info['title']}' to the download queue in {ctx.guild.name}")

                    return song_info

            except Exception as e:
                logger.error(f"Error in add_to_queue: {e}")
                await ctx.channel.send("An error occurred while adding the song to the queue.")

    def download_loop(self):
        """
        Background loop to handle downloads from the queue.
        """
        while True:
            song_info = self.download_queue.get()  # This will block until a new item is available
            if song_info is None:  # Could use a sentinel value to signal stopping
                continue
            try:
                with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
                    logger.info(f"Downloading '{song_info['title']}'")
                    info_result = ydl.extract_info(song_info['url'], download=True)
                    filename = ydl.prepare_filename(info_result)

                    # Update song_info with filename after download
                    song_info['filename'] = filename

                    ctx = song_info['ctx']

                    # Add song to playing queue
                    with self.queue_lock:
                        if not ctx.voice_client.is_playing() and self.currently_playing == None:
                            self.bot.loop.call_soon_threadsafe(asyncio.run_coroutine_threadsafe, self.play_song(ctx, song_info), self.bot.loop)
                        else:
                            self.bot.loop.call_soon_threadsafe(self.song_queue.put_nowait, song_info)
                    logger.info(f"Finished downloading '{song_info['title']}'")

            except Exception as e:
                logger.error(f"Error downloading {song_info['url']}: {e}")
                # Consider how to handle download failures, e.g., retry or notify
            finally:
                self.download_queue.task_done()

    async def start_disconnect_timer(self, ctx):
        """Starts the disconnect timer."""
        logger.info(f"Starting disconnect timer for {ctx.guild.name}")
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
                logger.info(f"Bot is alone in the voice channel in {ctx.guild.name}. Disconnecting.")
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