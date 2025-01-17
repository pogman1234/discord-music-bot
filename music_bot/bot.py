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
    def __init__(self, url, title, duration, thumbnail, video_id):
        self.url = url
        self.video_id = video_id  # Extracted from URL or provided directly
        self.title = self._sanitize_filename(title)
        self.duration = duration
        self.thumbnail = thumbnail
        self.filepath = f"music/{self.video_id}.mp3"
        self.is_downloaded = False

    def __getitem__(self, key):
        return getattr(self, key)

    def _sanitize_filename(self, title):
        """Keep full title for display, sanitize only for filesystem"""
        return ''.join(c for c in title if c.isalnum() or c in ' -_()[]{}')

    def to_dict(self):
        return {
            'url': self.url,
            'title': self.title,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'filepath': self.filepath,
            'is_downloaded': self.is_downloaded,
            'video_id': self.video_id
        }

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': 'music/%(id)s.%(ext)s', # Directly save to the correct location
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0'
        }
        self.ffmpeg_options = {
            'options': '-vn'
        }
        self.ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()  # Stores Song objects
        self.current_song = None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.volume = 0.5
        self.youtube = youtube
        self.download_dir = "music"
        self.is_playing = False
        self.queue_task = None
        self.queues = {}  # Guild ID -> Queue mapping

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
        self.ctx = ctx

        if not ctx.voice_client:
            self._log("No voice client found", "ERROR", logger=self.discord_logger)
            return

        if not ctx.voice_client.is_connected():
            self._log("Voice client not connected", "ERROR", logger=self.discord_logger)
            await ctx.send("Bot is not connected to a voice channel.")
            return

        if not self.queue:
            self.current_song = None
            self.is_playing = False
            self._log("Queue is empty, nothing to play.", "INFO", logger=self.discord_logger)
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song.title}", "INFO", logger=self.discord_logger)

        if not self.current_song.is_downloaded:
          await self.download_song(self.current_song)

        if not hasattr(self.current_song, 'filepath') or not self.current_song.filepath or not os.path.exists(self.current_song.filepath):
            self._log("Song filepath not found or invalid", "ERROR", logger=self.discord_logger)
            await ctx.send("Error: Could not find audio file for this song.")
            self.play_next_song_callback(ctx)
            return

        try:
            source = discord.FFmpegPCMAudio(self.current_song.filepath, **self.ffmpeg_options)
            transformed_source = discord.PCMVolumeTransformer(source, volume=self.volume)
            self.is_playing = True
            ctx.voice_client.play(
                transformed_source,
                after=lambda e: self.play_next_song_callback(ctx) if e is None else self._log(f"Error in playback: {e}", "ERROR")
            )

            await ctx.send(f"Now playing: {self.current_song.title}")

        except Exception as e:
            self._log(f"Error during playback: {str(e)}", "ERROR", logger=self.discord_logger)
            await ctx.send(f"An error occurred while playing the song: {str(e)}")
            self.play_next_song_callback(ctx)

    def play_next_song_callback(self, ctx):
        self.loop.call_soon_threadsafe(self.cleanup_current_song)
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play_next_song(ctx), self.loop)

    def cleanup_current_song(self):
        self.current_song = None

    async def add_to_queue(self, ctx, query: str) -> Optional[Dict]:
        """Adds a song to the queue (processes URL or search) and returns song info"""
        try:
            song_data = await self.process_url_or_search(query)

            if not song_data:
                await ctx.send("Could not find a video based on your query.")
                return None
            
            # Extract video ID directly from search results or URL
            video_id = song_data.get('id')
            if not video_id:
                self._log("No video ID found in song data", "ERROR", logger=self.ytdl_logger)
                await ctx.send("Error: Could not extract video ID.")
                return None

            # Get full title from song_data
            full_title = song_data.get('title', 'Unknown Title')

            song = Song(
                url=song_data.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}"),
                title=full_title,  # Use full title instead of truncated
                duration=song_data.get('duration', 0),
                thumbnail=song_data.get('thumbnail'),
                video_id=video_id
            )
            
            self.queue.append(song)
            if not self.queue_task:
                self.queue_task = asyncio.create_task(self.process_queue(ctx))

            # Send full title in queue message
            await ctx.send(f"Added to queue: {full_title}")
            return song.to_dict()

        except Exception as e:
            self._log(f"Error adding song to queue: {str(e)}", "ERROR", logger=self.discord_logger)
            await ctx.send(f"Error adding song to queue: {str(e)}")
            return None

    async def process_url_or_search(self, query: str) -> dict:
        """Process either direct URLs or search terms"""
        try:
            # Check if query is a URL
            is_url = query.startswith(('http://', 'https://', 'www.'))
            
            if is_url:
                # Direct URL handling
                info = await self.loop.run_in_executor(
                    self.thread_pool,
                    lambda: self.ytdl.extract_info(query, download=False)
                )
            else:
                # Search handling
                search_query = f"ytsearch:{query}"  # Use ytsearch instead of auto
                info = await self.loop.run_in_executor(
                    self.thread_pool,
                    lambda: self.ytdl.extract_info(search_query, download=False)
                )

            # Handle search results
            if 'entries' in info:
                info = info['entries'][0]
            
            if not info:
                raise ValueError("No results found")
                
            return info
            
        except Exception as e:
            self._log(f"Error processing URL/search: {str(e)}", "ERROR", logger=self.ytdl_logger)
            raise

    async def download_song(self, song: Song):
        """Downloads a song using yt-dlp and updates the Song object"""
        try:
            self._log(f"Downloading song: {song.title} (URL: {song.url})", "INFO", logger=self.ytdl_logger)

            # Download using yt-dlp directly to the correct path
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
              self.thread_pool, 
              functools.partial(self.ytdl.download, [song.url])
            )

            song.is_downloaded = True
            self._log(f"Download successful: {song.title}", "INFO", logger=self.ytdl_logger)

        except Exception as e:
            self._log(f"Download error: {str(e)}", "ERROR", logger=self.ytdl_logger, exc_info=True)
            song.is_downloaded = False

    def get_currently_playing(self):
        """Returns the title of the currently playing song or None if not playing."""
        return self.current_song.title if self.current_song else None

    def is_playing_func(self, ctx):
        """Checks if the bot is currently playing audio in the guild."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

    def get_queue_info(self) -> List[Dict]:
        """Returns formatted information about all songs in queue"""
        return [song.to_dict() for song in self.queue]

    def get_current_song(self) -> Optional[Dict]:
        """Returns information about currently playing song"""
        return self.current_song.to_dict() if self.current_song else None

    def get_queue_position(self) -> int:
        """Returns current position in queue"""
        if not self.current_song:
            return 0
        try:
            return list(self.queue).index(self.current_song)
        except ValueError:
            return 0

    async def process_queue(self, ctx):
        """Processes the song queue, downloading and playing songs as needed"""
        while True:
            if self.queue and not self.is_playing:
                next_song = self.queue[0]
                if not next_song.is_downloaded:
                    await self.download_song(next_song)
                if next_song.is_downloaded:
                    await self.play_next_song(ctx)
            await asyncio.sleep(1)

    def get_queue(self, guild_id: int = None) -> List[Song]:
        """Get the current song queue for a guild"""
        if guild_id is None:
            # Return first guild's queue for testing
            if not self.queues:
                return []
            return list(self.queues.values())[0]
        return self.queues.get(guild_id, [])