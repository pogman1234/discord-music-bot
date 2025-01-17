import asyncio
import discord
import subprocess
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
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime

class Song:
    def __init__(self, url: str, title: str, duration: int, thumbnail: str = None):
        self.url = url
        self.title = title
        self.duration = duration
        self.thumbnail = thumbnail
        self.filepath = None  # Add filepath attribute
        self.source = None    # Add source attribute

    def __getitem__(self, key):
        # Enable dictionary-like access
        return getattr(self, key)

    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'title': self.title,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'filepath': self.filepath if hasattr(self, 'filepath') else None
        }

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join('music', '%(extractor)s-%(id)s-%(title)s.%(ext)s'),  # Corrected outtmpl
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': False,  # Enabled logging from yt_dlp
            'no_warnings': False,  # Enabled warnings from yt_dlp
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'verbose': True,  # Enabled verbose output from yt_dlp
            'debug_printtraffic': True,
            'no_cache_dir': True
        }
        self.ffmpeg_options = {
            'options': '-vn'
        }
        self.ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()  # Will now store Song objects
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
        self.ctx = ctx  # Store context for use in after_callback

        if not self.queue:
            self.current_song = None
            self._log("Queue is empty, nothing to play.", "INFO", logger=self.discord_logger)
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song.title}", "INFO", logger=self.discord_logger,
                  url=self.current_song.url)

        # Log the filepath before creating FFmpegPCMAudio source
        self._log(f"Attempting to play from: {self.current_song.filepath}", "DEBUG", logger=self.discord_logger)

        try:
            source = discord.FFmpegPCMAudio(self.current_song.filepath, **self.ffmpeg_options)
        except discord.errors.ClientException as e:
            self._log(f"Error creating FFmpegPCMAudio source: {e}", "ERROR", logger=self.discord_logger)
            await ctx.send("An error occurred while preparing the song for playback.")
            return

        source.volume = self.volume
        self.current_song.source = source

        def after_callback(error):
            if error:
                self._log(f"Playback error: {error}", "ERROR", logger=self.discord_logger)

            # Schedule cleanup to run in the event loop
            self.loop.call_soon_threadsafe(self.cleanup_current_song)

            # Schedule play_next_song to run in the event loop if there are songs in the queue
            if self.queue:
                coro = self.play_next_song(self.ctx)  # Pass the context
                asyncio.run_coroutine_threadsafe(coro, self.loop)

        if ctx.voice_client:
            try:
                ctx.voice_client.play(
                    source,
                    after=lambda e: after_callback(e)  # Correctly pass 'e' to after_callback
                )
            except discord.errors.ClientException as e:
                self._log(f"Error during playback: {e}", "ERROR", logger=self.discord_logger)
                await ctx.send("An error occurred during playback.")
                return

    def play_next_song_callback(self, ctx):
        self.loop.call_soon_threadsafe(self.cleanup_current_song)
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play_next_song(ctx), self.loop)

    def cleanup_current_song(self):
        if self.current_song and os.path.exists(self.current_song.filepath):
            try:
                # os.remove(self.current_song.filepath) # No need to remove file
                self._log(f"Removed file: {self.current_song.filepath}", "DEBUG", logger=self.discord_logger)
            except Exception as e:
                self._log(f"Error removing file: {e}", "ERROR", logger=self.discord_logger,
                          filepath=self.current_song.filepath)
        self.current_song = None

    async def add_to_queue(self, url: str) -> Optional[Dict]:
        """Adds a song to the queue and returns song info"""
        try:
            info = await self.loop.run_in_executor(
                None,
                lambda: self.ytdl.extract_info(url, download=False)
            )
            
            if 'entries' in info:
                info = info['entries'][0]
                
            song = Song(
                url=info['url'],
                title=info['title'],
                duration=info['duration'],
                thumbnail=info.get('thumbnail')
            )
            
            self.queue.append(song)
            return song.to_dict()
            
        except Exception as e:
            self.discord_logger.error(f"Error adding song to queue: {str(e)}")
            return None

    async def search_and_download_song(self, query):
        try:
            self._log(f"Searching YouTube for query: {query}", "INFO", logger=self.discord_logger)
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=1
            ).execute()

            self._log(f"YouTube API search response: {search_response}", "DEBUG", logger=self.ytdl_logger)

            if not search_response.get("items"):
                self._log(f"No results found for query: {query}", "WARNING", logger=self.discord_logger)
                return None

            video_id = search_response["items"][0]["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            self._log(f"Found video URL: {video_url}", "INFO", logger=self.discord_logger)

            return await self.download_song(video_url)

        except Exception as e:
            self._log(f"Error searching with YouTube API or downloading song: {e}", "ERROR",
                      logger=self.discord_logger, query=query)
            return None

    async def download_song(self, url):
        try:
            self._log(f"Downloading song from URL: {url}", "INFO", logger=self.ytdl_logger)

            # Get the current working directory
            current_directory = os.getcwd()
            self._log(f"Current working directory: {current_directory}", "DEBUG", logger=self.ytdl_logger)

            # Execute ls -lrt in the current directory
            self._log(f"Executing ls -lrt in {current_directory}", "DEBUG", logger=self.ytdl_logger)
            process = subprocess.run(['ls', '-lrt', current_directory], capture_output=True, text=True)
            self._log(f"ls -lrt output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)

            # Execute ls -lrt in the music directory
            music_directory = self.download_dir  # Use self.download_dir directly
            self._log(f"Executing ls -lrt in {music_directory}", "DEBUG", logger=self.ytdl_logger)
            process = subprocess.run(['ls', '-lrt', music_directory], capture_output=True, text=True)
            self._log(f"ls -lrt output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)

            partial = functools.partial(self.ytdl.extract_info, url, download=True)
            info = await self.loop.run_in_executor(self.thread_pool, partial)

            self._log(f"yt_dlp info: {info}", "DEBUG", logger=self.ytdl_logger)

            filepath = os.path.join(self.ytdl.prepare_filename(info))

            # Wait for file to be created with a longer interval and timeout
            total_wait_time = 0
            while not os.path.exists(filepath) and total_wait_time < 60:  # Timeout after 60 seconds
                self._log(f"Waiting for file to be downloaded: {filepath} (waited {total_wait_time} seconds)", "DEBUG",
                          logger=self.ytdl_logger)
                
                # Execute ls -lrt in the music directory
                self._log(f"Executing ls -lrt in {music_directory}", "DEBUG", logger=self.ytdl_logger)
                process = subprocess.run(['ls', '-lrt', music_directory], capture_output=True, text=True)
                self._log(f"ls -lrt output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)

                # Execute ls -lrt in the parent directory of music directory
                parent_directory = os.path.dirname(music_directory)
                self._log(f"Executing ls -lrt in {parent_directory}", "DEBUG", logger=self.ytdl_logger)
                process = subprocess.run(['ls', '-lrt', parent_directory], capture_output=True, text=True)
                self._log(f"ls -lrt output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)

                await asyncio.sleep(5)  # Wait for 5 seconds
                total_wait_time += 5

            if os.path.exists(filepath):
                song_info = {'title': info['title'], 'url': info['webpage_url'], 'filepath': filepath}
                self._log(f"Song info before return: {song_info}", "DEBUG", logger=self.ytdl_logger)
                self._log(f"Successfully downloaded: {info['title']}", "INFO", logger=self.ytdl_logger)
                return song_info
            else:
                self._log(f"File did not download after waiting for 60 seconds: {filepath}", "ERROR",
                          logger=self.ytdl_logger)
                return None

        except Exception as e:
            self._log(f"Error downloading song with yt_dlp: {e}", "ERROR", logger=self.ytdl_logger, url=url)
            # Add more specific exception handling here, if possible
            if 'info' in locals() and info:
                self._log(f"Partial yt_dlp info: {info}", "DEBUG", logger=self.ytdl_logger)
            return None  # Ensure None is returned on error
    
    def get_currently_playing(self):
        """Returns the title of the currently playing song or None if not playing."""
        if self.current_song:
            return self.current_song.title
        return None
    
    def is_playing(self, ctx):
        """Checks if the bot is currently playing audio in the guild."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

    def get_queue_info(self) -> List[Dict]:
        """Returns formatted information about all songs in queue"""
        return [song.to_dict() for song in self.queue]

    def get_current_song(self) -> Optional[Dict]:
        """Returns information about currently playing song"""
        if self.current_song:
            return self.current_song.to_dict()
        return None

    def get_queue_position(self) -> int:
        """Returns current position in queue"""
        if not self.current_song:
            return 0
        try:
            return list(self.queue).index(self.current_song)
        except ValueError:
            return 0