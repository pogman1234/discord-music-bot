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
import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

# Keep the Song data class from current code
@dataclass
class Song:
    url: str
    title: str
    duration: int
    thumbnail: str
    video_id: str
    filepath: str = ""
    is_downloaded: bool = False
    download_retries: int = 0
    max_retries: int = 3

    def __post_init__(self):
        self.filepath = os.path.join("music", f"{self.video_id}.mp3")

    def __getitem__(self, key):
        return getattr(self, key)

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
        # Keep initialization from current code but add debug logging settings
        self.bot = bot
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': os.path.join('music', '%(id)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': False,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'debug_printtraffic': True,
            'verbose': True
        }
        
        # Initialize loggers like in current code
        self.ytdl_logger = logging.getLogger('ytdl')
        self.ytdl_logger.setLevel(logging.DEBUG)
        self.discord_logger = logging.getLogger('discord')
        self.discord_logger.setLevel(logging.INFO)

        # Add debug file handler 
        ytdl_file_handler = logging.FileHandler('ytdl.log')
        ytdl_file_handler.setLevel(logging.DEBUG)
        ytdl_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ytdl_file_handler.setFormatter(ytdl_formatter)
        self.ytdl_logger.addHandler(ytdl_file_handler)

        # Other initialization from current code
        self.download_ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()  
        self.current_song = None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.volume = 0.5
        self.youtube = youtube
        self.download_dir = "music"
        self.is_playing = False
        self.queue_task = None
        self.queue_lock = asyncio.Lock()

        os.makedirs(self.download_dir, exist_ok=True)

    # Keep the logging method
    def _log(self, message, severity="DEBUG", logger=None, **kwargs):
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

    async def download_song(self, song: Song):
        """Download song with enhanced logging from previous code"""
        self._log(f"Starting download process for: {song.title}", "INFO", logger=self.ytdl_logger)
        self._log(f"Download directory: {self.download_dir}", "DEBUG", logger=self.ytdl_logger)
        
        # Add directory inspection logging from previous code
        current_directory = os.getcwd()
        self._log(f"Current working directory: {current_directory}", "DEBUG", logger=self.ytdl_logger)
        
        process = subprocess.run(['ls', '-lrt', current_directory], capture_output=True, text=True)
        self._log(f"ls -lrt output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)
        
        process = subprocess.run(['ls', '-lrt', self.download_dir], capture_output=True, text=True)
        self._log(f"ls -lrt music directory output:\n{process.stdout}", "DEBUG", logger=self.ytdl_logger)

        # Rest of download_song implementation from current code
        self._log(f"Expected filepath: {song.filepath}", "DEBUG", logger=self.ytdl_logger)
        
        # Verify FFMPEG installation
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self._log("FFMPEG is available", "INFO", logger=self.ytdl_logger)
        except Exception as e:
            self._log(f"FFMPEG not found: {str(e)}", "ERROR", logger=self.ytdl_logger)
            return False

        # Create absolute path for download
        abs_download_dir = os.path.abspath(self.download_dir)
        abs_filepath = os.path.join(abs_download_dir, f"{song.video_id}")
        self._log(f"Absolute filepath: {abs_filepath}", "DEBUG", logger=self.ytdl_logger)

        while song.download_retries < song.max_retries:
            try:
                self._log(f"Download attempt {song.download_retries + 1} starting", "INFO", logger=self.ytdl_logger)
                
                # Updated ytdl options for this download
                download_opts = self.ytdl_options.copy()
                download_opts.update({
                    'outtmpl': abs_filepath,
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                })
                
                # Create new YoutubeDL instance with updated options
                ytdl = YoutubeDL(download_opts)
                
                # Perform download in thread pool
                self._log(f"Starting YoutubeDL download for URL: {song.url}", "DEBUG", logger=self.ytdl_logger)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.thread_pool,
                    functools.partial(ytdl.download, [song.url])
                )

                # Verify file exists after download
                if os.path.exists(song.filepath):
                    song.is_downloaded = True
                    self._log(f"Download successful: {song.title}", "INFO", logger=self.ytdl_logger)
                    return True
                else:
                    raise FileNotFoundError(f"Downloaded file not found at {song.filepath}")

            except Exception as e:
                song.download_retries += 1
                self._log(
                    f"Download error (attempt {song.download_retries}/{song.max_retries}): {str(e)}",
                    "ERROR",
                    logger=self.ytdl_logger,
                    exc_info=True
                )
                self._log(f"Download attempt {song.download_retries + 1} completed", "DEBUG", logger=self.ytdl_logger)
                await asyncio.sleep(5)  # Increased wait time

        song.is_downloaded = False
        return False

    # Keep queue management methods from current code
    async def add_to_queue(self, ctx, query: str) -> Optional[Dict]:
        self._log(f"Adding to queue: {query}", "INFO", logger=self.discord_logger)
        try:
            song_data = await self.process_url_or_search(query)
            self._log(f"Retrieved song data: {json.dumps(song_data, indent=2)}", "DEBUG", logger=self.ytdl_logger)

            if not song_data:
                self._log("No song data found", "ERROR", logger=self.discord_logger)
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
            
            async with self.queue_lock:  # Acquire the lock
                self.queue.append(song)

            if not self.queue_task:
                self.queue_task = asyncio.create_task(self.process_queue(ctx))

            self._log(f"Created queue task: {self.queue_task is not None}", "INFO", logger=self.discord_logger)

            # Send full title in queue message
            await ctx.send(f"Added to queue: {full_title}")
            return song.to_dict()

        except Exception as e:
            self._log(f"Error adding song to queue: {str(e)}", "ERROR", logger=self.discord_logger)
            await ctx.send(f"Error adding song to queue: {str(e)}")
            return None

    async def play_next_song(self, ctx):   
        self._log("=== Starting play_next_song ===", "DEBUG", logger=self.discord_logger)
        
        try:
            # Step 1: Voice Client Validation
            self._log("Step 1: Checking voice client", "DEBUG", logger=self.discord_logger)
            if not ctx.voice_client:
                self._log("No voice client available", "ERROR", logger=self.discord_logger)
                await ctx.send("Bot is not connected to a voice channel.")
                return False

            # Step 2: Connection State
            self._log("Step 2: Checking connection state", "DEBUG", logger=self.discord_logger)
            if not ctx.voice_client.is_connected():
                self._log("Voice client disconnected", "ERROR", logger=self.discord_logger)
                try:
                    voice_channel = ctx.author.voice.channel if ctx.author.voice else None
                    if voice_channel:
                        await voice_channel.connect()
                        self._log("Reconnected to voice channel", "INFO", logger=self.discord_logger)
                    else:
                        await ctx.send("Please join a voice channel first!")
                        return False
                except Exception as e:
                    self._log(f"Connection error: {str(e)}", "ERROR", logger=self.discord_logger)
                    await ctx.send(f"Failed to connect: {str(e)}")
                    return False

            # Step 3: Queue Check
            self._log("Step 3: Checking queue state", "DEBUG", logger=self.discord_logger)
            async with self.queue_lock:
                if not self.queue:
                    self._log("Queue is empty", "INFO", logger=self.discord_logger)
                    self.current_song = None
                    self.is_playing = False
                    await ctx.send("Queue is empty.")
                    return False
                
                # Get next song
                self.current_song = self.queue.popleft()
                self._log(f"Got next song: {self.current_song.title}", "INFO", logger=self.discord_logger)

            # Step 4: File Verification
            self._log("Step 4: Verifying file exists", "DEBUG", logger=self.discord_logger)
            if not os.path.exists(self.current_song.filepath):
                self._log(f"File missing: {self.current_song.filepath}", "ERROR", logger=self.discord_logger)
                await ctx.send(f"Error: File not found for {self.current_song.title}")
                self.current_song = None
                await self.play_next_song(ctx)
                return False

            # Step 5: Audio Playback
            self._log("Step 5: Starting audio playback", "DEBUG", logger=self.discord_logger)
            try:
                ffmpeg_options = {
                    'options': '-vn -b:a 192k',
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                }
                
                source = discord.FFmpegPCMAudio(
                    self.current_song.filepath,
                    **ffmpeg_options
                )
                transformed_source = discord.PCMVolumeTransformer(source, volume=self.volume)

                def after_playing(error):
                    if error:
                        self._log(f"Playback error in callback: {str(error)}", "ERROR", logger=self.discord_logger)
                    self.play_next_song_callback(ctx)

                ctx.voice_client.play(transformed_source, after=after_playing)
                self.is_playing = True
                
                await ctx.send(f"🎵 Now playing: {self.current_song.title}")
                self._log(f"Successfully started playing: {self.current_song.title}", "INFO", logger=self.discord_logger)
                return True

            except Exception as e:
                self._log(f"Playback error: {str(e)}", "ERROR", logger=self.discord_logger)
                await ctx.send(f"Error playing {self.current_song.title}: {str(e)}")
                self.current_song = None
                await self.play_next_song(ctx)
                return False

        except Exception as e:
            self._log(f"Critical error in play_next_song: {str(e)}", "ERROR", logger=self.discord_logger)
            await ctx.send(f"An error occurred: {str(e)}")
            return False

    # Keep helper methods from current code
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

    # Add the process_queue method from current code
    async def process_queue(self, ctx):
        """Processes the song queue, downloading and playing songs as needed"""
        while True:
            try:
                self._log("Queue processing cycle starting", "DEBUG", logger=self.discord_logger)

                # Check voice client first
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    self._log("Voice client not ready", "ERROR", logger=self.discord_logger)
                    await asyncio.sleep(1)
                    continue

                async with self.queue_lock:  # Acquire the lock
                    self._log(f"Type of self.queue: {type(self.queue)}", "DEBUG", logger=self.discord_logger)
                    if self.queue and not self.is_playing:
                        self._log(f"Queue has {len(self.queue)} items and not currently playing", "INFO", logger=self.discord_logger)

                        next_song = self.queue[0]  # Access the queue (protected by lock)
                        self._log(f"Processing next song: {next_song.title}", "INFO", logger=self.ytdl_logger)

                        try:
                            if not next_song.is_downloaded:
                                self._log("Starting download...", "INFO", logger=self.ytdl_logger)
                                download_success = await asyncio.wait_for(
                                    self.download_song(next_song),
                                    timeout=300  # 5 minute timeout
                                )

                                if not download_success:
                                    self._log("Download failed, removing song", "ERROR", logger=self.discord_logger)
                                    self.queue.popleft()  # Modify queue (protected by lock)
                                    continue

                            self._log("Download complete, starting playback", "INFO", logger=self.discord_logger)
                            self.is_playing = True  # Set flag before playing
                            await self.play_next_song(ctx)

                        except asyncio.TimeoutError:
                            self._log("Operation timed out", "ERROR", logger=self.discord_logger)
                            self.queue.popleft()  # Modify queue (protected by lock)
                        except Exception as e:
                            self._log(f"Error in queue processing: {str(e)}", "ERROR", logger=self.discord_logger)
                            self.queue.popleft()  # Modify queue (protected by lock)
                    # Lock is automatically released when exiting 'async with' block

                await asyncio.sleep(1)

            except Exception as e:
                self._log(f"Critical error in queue processing: {str(e)}", "ERROR", logger=self.discord_logger)
                await asyncio.sleep(5)  # Longer sleep on critical error