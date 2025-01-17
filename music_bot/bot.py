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
    def __init__(self, url, title, duration, thumbnail):
        self.url = url
        self.video_id = self._extract_video_id(url)
        self.title = self._sanitize_filename(title)
        self.duration = duration
        self.thumbnail = thumbnail
        self.filepath = f"music/{self.video_id}.mp3"
        self.is_downloaded = False
    
    def __getitem__(self, key):
        return getattr(self, key)
        
    def _extract_video_id(self, url):
        if 'youtu.be' in url:
            return url.split('/')[-1]
        if 'youtube.com' in url:
            return url.split('v=')[-1].split('&')[0]
        return url[:11]  # YouTube IDs are 11 chars
        
    def _sanitize_filename(self, title):
        # Keep it simple and short
        safe_title = ''.join(c for c in title[:30] if c.isalnum() or c == ' ')
        return f"{safe_title}_{self.video_id}"
        
    def to_dict(self):
        return {
            'url': self.url,
            'title': self.title,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'filepath': self.filepath,
            'is_downloaded': self.is_downloaded
        }
        

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': 'music/%(id)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
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
        self.is_playing = False
        self.queue_task = None

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
        if not self.queue_task:
            self.queue_task = asyncio.create_task(self.process_queue())

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
            self._log("Queue is empty, nothing to play.", "INFO", logger=self.discord_logger)
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song.title}", "INFO", logger=self.discord_logger)

        if not hasattr(self.current_song, 'filepath') or not self.current_song.filepath:
            self._log("Song filepath not found", "ERROR", logger=self.discord_logger)
            await ctx.send("Error: Could not find audio file for this song.")
            return

        try:
            source = discord.FFmpegPCMAudio(self.current_song.filepath, **self.ffmpeg_options)
            transformed_source = discord.PCMVolumeTransformer(source, volume=self.volume)
            
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
            if not self.queue_task:
                self.queue_task = asyncio.create_task(self.process_queue())
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
            
            # Extract info and download
            partial = functools.partial(self.ytdl.extract_info, url, download=True)
            info = await self.loop.run_in_executor(self.thread_pool, partial)
            
            if not info:
                self._log("Failed to get video info", "ERROR", logger=self.ytdl_logger)
                return None

            # Get video ID and prepare filepath
            video_id = info.get('id', '')
            if not video_id:
                self._log("No video ID found", "ERROR", logger=self.ytdl_logger)
                return None
                
            filepath = os.path.join(self.download_dir, f"{video_id}.mp3")
            self._log(f"Expected filepath: {filepath}", "DEBUG", logger=self.ytdl_logger)

            # Wait for file with timeout
            total_wait_time = 0
            while not os.path.exists(filepath) and total_wait_time < 30:
                self._log(f"Waiting for file... ({total_wait_time}s)", "DEBUG", logger=self.ytdl_logger)
                if os.path.exists(self.download_dir):
                    files = os.listdir(self.download_dir)
                    self._log(f"Files in directory: {files}", "DEBUG", logger=self.ytdl_logger)
                await asyncio.sleep(2)
                total_wait_time += 2

            if os.path.exists(filepath):
                song_info = {
                    'title': info['title'],
                    'url': info['webpage_url'],
                    'filepath': filepath,
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', '')
                }
                self._log(f"Download successful: {info['title']}", "INFO", logger=self.ytdl_logger)
                return song_info
                
            self._log(f"Download failed - file not found: {filepath}", "ERROR", logger=self.ytdl_logger)
            return None

        except Exception as e:
            self._log(f"Download error: {str(e)}", "ERROR", logger=self.ytdl_logger, exc_info=True)
            return None
    
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

    async def process_queue(self):
        while True:
            if not self.is_playing and self.queue and not self.current_song:
                song = self.queue[0]
                if not song.is_downloaded:
                    await song.download(self.ytdl)
                if song.is_downloaded:
                    self.queue.popleft()
                    await self.play_next_song(self.ctx)
            await asyncio.sleep(1)