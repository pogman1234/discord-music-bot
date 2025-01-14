import asyncio
import discord
import threading
from discord.ext import commands
from yt_dlp import YoutubeDL
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import functools
import json
import time
from googleapiclient.discovery import build
import os
import logging

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
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
            'verbose': True,
            'debug_printtraffic': True,
            'no_cache_dir': True
        }
        self.ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()
        self.current_song = None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.volume = 0.5
        self.youtube = youtube
        self.download_dir = "music"

        # Set up loggers
        self.ytdl_logger = logging.getLogger('ytdl')
        self.ytdl_logger.setLevel(logging.DEBUG)
        self.discord_logger = logging.getLogger('discord')
        self.discord_logger.setLevel(logging.INFO)

        os.makedirs(self.download_dir, exist_ok=True)

    def _log(self, message, severity="INFO", logger=None, **kwargs):
        entry = {
            "message": message,
            "severity": severity,
            "timestamp": {"seconds": int(time.time()), "nanos": 0},
            **kwargs,
        }
        if logger:
            logger.log(logging.getLevelName(severity), json.dumps(entry))
        else:
            print(json.dumps(entry))

    async def on_ready(self):
        self._log(f"Logged in as {self.bot.user.name} ({self.bot.user.id})", "INFO", logger=self.discord_logger)

    async def play_next_song(self, ctx):
        if not self.queue:
            self.current_song = None
            self._log("Queue is empty, nothing to play.", "INFO", logger=self.discord_logger)
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song['title']}", "INFO", logger=self.discord_logger, url=self.current_song['url'])

        source = discord.FFmpegPCMAudio(self.current_song['filepath'])
        source.volume = self.volume
        self.current_song['source'] = source

        def after_callback(error):
            if error:
                self._log(f"Playback error: {error}", "ERROR", logger=self.discord_logger)
            
            # Schedule cleanup to run in the event loop
            self.loop.call_soon_threadsafe(self.cleanup_current_song)

            # Check the queue and play the next song if available
            if self.queue:
                coro = self.play_next_song(ctx)
                fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
                try:
                    fut.result()  # Wait for the coroutine to finish
                except Exception as e:
                    self._log(f"Error playing next song: {e}", "ERROR", logger=self.discord_logger)

        if ctx.voice_client:
            ctx.voice_client.play(
                source,
                after=lambda e: after_callback(e)
            )

    def play_next_song_callback(self, ctx):
        self.loop.call_soon_threadsafe(self.cleanup_current_song)
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play_next_song(ctx), self.loop)

    def cleanup_current_song(self):
        if self.current_song and os.path.exists(self.current_song['filepath']):
            try:
                os.remove(self.current_song['filepath'])
                self._log(f"Removed file: {self.current_song['filepath']}", "DEBUG", logger=self.discord_logger)
            except Exception as e:
                self._log(f"Error removing file: {e}", "ERROR", logger=self.discord_logger, filepath=self.current_song['filepath'])
            self.current_song = None

    async def add_to_queue(self, ctx, query):
        if 'playlist' in query.lower() or 'list' in query.lower():
            self._log(f"Playlists are not supported with YouTube API search, using yt_dlp instead: {query}", "WARNING", logger=self.discord_logger)
            info = await self.extract_playlist_info(query)
            if 'entries' in info:
                for entry in info['entries']:
                    song_info = await self.download_song(entry['url'])
                    if song_info:
                        self.queue.append(song_info)
                self._log(f"Added {len(info['entries'])} songs from playlist to the queue.", "INFO", logger=self.discord_logger)
            else:
                self._log("No entries found in playlist", "WARNING", logger=self.discord_logger)
        else:
            song_info = await self.search_and_download_song(query)
            if song_info:
                self.queue.append(song_info)
                self._log(f"Added song to queue: {song_info['title']}", "INFO", logger=self.discord_logger, url=song_info['url'])

        if not self.is_playing(ctx) and not self.current_song:
            await self.play_next_song(ctx)

        return song_info

    async def search_and_download_song(self, query):
        try:
            self._log(f"Searching YouTube for query: {query}", "INFO", logger=self.discord_logger)
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=1
            ).execute()

            if not search_response.get("items"):
                self._log(f"No results found for query: {query}", "WARNING", logger=self.discord_logger)
                return None

            video_id = search_response["items"][0]["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            return await self.download_song(video_url)

        except Exception as e:
            self._log(f"Error searching with YouTube API or downloading song: {e}", "ERROR", logger=self.discord_logger, query=query)
            return None

    async def download_song(self, url):
        try:
            self._log(f"Downloading song from URL: {url}", "INFO", logger=self.ytdl_logger)
            partial = functools.partial(self.ytdl.extract_info, url, download=True)
            info = await self.loop.run_in_executor(self.thread_pool, partial)

            filepath = os.path.join(self.download_dir, self.ytdl.prepare_filename(info))

            while not os.path.exists(filepath):
                await asyncio.sleep(0.5)

            song_info = {'title': info['title'], 'url': info['webpage_url'], 'filepath': filepath}
            self._log(f"Successfully downloaded: {info['title']}", "INFO", logger=self.ytdl_logger)
            return song_info
        except Exception as e:
            self._log(f"Error downloading song with yt_dlp: {e}", "ERROR", logger=self.ytdl_logger, url=url)
            return None

    async def extract_playlist_info(self, url):
        try:
            self._log(f"Extracting playlist info from URL: {url}", "INFO", logger=self.ytdl_logger)
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            info = await self.loop.run_in_executor(self.thread_pool, partial)
            return info
        except Exception as e:
            self._log(f"Error extracting playlist info: {e}", "ERROR", logger=self.ytdl_logger, url=url)
            return None

    async def get_stream_source(self, url):
        try:
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            data = await self.loop.run_in_executor(None, partial)
            filename = data['url'] if 'url' in data else self.ytdl.prepare_filename(data)
            return discord.FFmpegPCMAudio(filename)
        except Exception as e:
            self._log(f"Error getting stream source: {e}", "ERROR", logger=self.discord_logger, url=url)
            return None

    def is_playing(self, ctx):
        return ctx.voice_client and ctx.voice_client.is_playing()

    def get_currently_playing(self):
        if self.current_song:
            return self.current_song['title']
        return None

    def get_volume(self):
        return self.volume

    def set_volume(self, volume):
        self.volume = volume
        if self.current_song and self.current_song.get('source'):
            self.current_song['source'].volume = volume