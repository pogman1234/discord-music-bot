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
        # Add .mp3 extension explicitly
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
            'outtmpl': '%(id)s.%(ext)s',  # Simplified path
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
            'verbose': True,
            'postprocessors': [{  # Add postprocessor
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
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

        # Add FFMPEG options
        self.ffmpeg_options = {
            'options': '-vn -b:a 192k',
        }

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
        mp3_filepath = f"{abs_filepath}.mp3"
        
        self._log(f"Download path: {abs_filepath}", "DEBUG", logger=self.ytdl_logger)
        self._log(f"Expected MP3 path: {mp3_filepath}", "DEBUG", logger=self.ytdl_logger)

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
                if os.path.exists(mp3_filepath):
                    song.filepath = mp3_filepath  # Update to actual MP3 path
                    song.is_downloaded = True
                    self._log(f"MP3 file found at: {mp3_filepath}", "INFO", logger=self.ytdl_logger)
                    self._log("Download complete, triggering playback", "INFO", logger=self.ytdl_logger)
                    return True
                else:
                    raise FileNotFoundError(f"MP3 file not found at {mp3_filepath}")

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

    async def play_next_song_callback(self, ctx):
        """Callback method for after song finishes or an error occurs."""
        self._log("Song finished or error occurred, cleaning up", "DEBUG", logger=self.discord_logger)
        self.is_playing = False

        # Schedule next song in event loop
        if self.queue:
            self._log("Scheduling next song", "DEBUG", logger=self.discord_logger)
            asyncio.create_task(self.play_next_song(ctx))  # Use asyncio.create_task
        else:
            self._log("Queue empty after song finished or error", "INFO", logger=self.discord_logger)
            self.current_song = None

    async def play_next_song(self, ctx):
        self._log("=== Starting play_next_song ===", "DEBUG", logger=self.discord_logger)

        try:
            if not self.current_song:
                self._log("No current song set", "DEBUG", logger=self.discord_logger)
                return False

            # Use subprocess to get more detailed FFmpeg output
            process = await asyncio.create_subprocess_exec(
                'ffmpeg',
                '-i', self.current_song.filepath,
                '-vn',  # Disable video
                '-f', 'wav',  # Output format: WAV
                '-acodec', 'pcm_s16le',  # Audio codec: 16-bit PCM (standard for WAV)
                '-ar', '48000',  # Sample rate: 48000 Hz (Discord's preferred rate)
                '-ac', '2',  # Channels: 2 (stereo)
                '-loglevel', 'debug',
                '-',  # Output to stdout
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Read FFmpeg's output in real-time
            async def read_stream(self, stream, callback):
                while True:
                    line = await stream.read(1024)  # Read in chunks
                    if not line:
                        break
                    try:
                        # Attempt to decode as text
                        text_line = line.decode().strip()
                        self._log(f"FFmpeg: {text_line}", "DEBUG", logger=self.ytdl_logger)
                        await callback(text_line)
                    except UnicodeDecodeError:
                        # Handle binary data (e.g., write to file directly)
                        if self.file is not None and not self.file.closed:
                            self.file.write(line)

            asyncio.create_task(read_stream(process.stdout))
            asyncio.create_task(read_stream(process.stderr))

            # Create a FFmpegPCMAudio source with the process
            source = discord.FFmpegPCMAudio(
                process.stdout,
                pipe=True
            )

            transformed_source = discord.PCMVolumeTransformer(source, volume=self.volume)
            self.is_playing = True

            await ctx.send(f"🎵 Now playing: {self.current_song.title}")
            return True

        except Exception as e:
            self._log(f"Error in play_next_song: {str(e)}", "ERROR", logger=self.discord_logger)
            self.is_playing = False  # Ensure is_playing is set to False on error
            asyncio.create_task(self.play_next_song_callback(ctx))  # Call callback manually on error
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

    async def process_queue(self, ctx):
        while True:
            try:
                self._log("Queue processing cycle starting", "DEBUG", logger=self.discord_logger)

                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    self._log("Voice client not ready", "DEBUG", logger=self.discord_logger)
                    await asyncio.sleep(1)
                    continue

                async with self.queue_lock:
                    if self.queue and not self.is_playing:
                        next_song = self.queue.popleft()  # Get and remove from queue
                        self._log(f"Processing next song: {next_song.title}", "DEBUG", logger=self.discord_logger)

                        if not next_song.is_downloaded:
                            download_success = await self.download_song(next_song)
                            if not download_success:
                                self._log("Download failed", "ERROR", logger=self.discord_logger)
                                continue

                        # Set current song before playing
                        self.current_song = next_song
                        self._log(f"Set current song: {self.current_song.title}", "DEBUG", logger=self.discord_logger)

                        # Start playback
                        try:
                            await self.play_next_song(ctx)
                        except Exception as e:
                            self._log(f"Playback error: {str(e)}", "ERROR", logger=self.discord_logger)
                            self.is_playing = False  # Set is_playing to False on error
                            self.current_song = None  # Clear current song on error

                await asyncio.sleep(1)  # Check queue every second

            except Exception as e:
                self._log(f"Queue processing error: {str(e)}", "ERROR", logger=self.discord_logger)
                self.is_playing = False  # Ensure is_playing is set to False on error in the outer loop
                await asyncio.sleep(5)

    async def process_url_or_search(self, query: str) -> Optional[Dict]:
        """Process a URL or search query to get song information"""
        self._log(f"Processing query: {query}", "DEBUG", logger=self.ytdl_logger)
        
        try:
            # Check if query is a URL
            if any(domain in query.lower() for domain in ['youtube.com', 'youtu.be']):
                # Use yt-dlp for URLs
                self._log("Query appears to be URL, using yt-dlp", "DEBUG", logger=self.ytdl_logger)
                info = await self.loop.run_in_executor(
                    self.thread_pool,
                    functools.partial(self.download_ytdl.extract_info, query, download=False)
                )
                
                if not info:
                    self._log("No info found from URL", "ERROR", logger=self.ytdl_logger)
                    return None
                    
                return {
                    'id': info['id'],
                    'title': info['title'],
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info['webpage_url']
                }
                
            else:
                # Use YouTube API for search
                self._log("Using YouTube API for search", "DEBUG", logger=self.ytdl_logger)
                search_response = await self.loop.run_in_executor(
                    self.thread_pool,
                    lambda: self.youtube.search().list(
                        q=query,
                        part="snippet",
                        type="video",
                        maxResults=1
                    ).execute()
                )
                
                if not search_response.get('items'):
                    self._log("No search results found", "WARNING", logger=self.ytdl_logger)
                    return None
                    
                video = search_response['items'][0]
                video_id = video['id']['videoId']
                
                # Get additional video details
                video_response = await self.loop.run_in_executor(
                    self.thread_pool,
                    lambda: self.youtube.videos().list(
                        part="contentDetails,snippet",
                        id=video_id
                    ).execute()
                )
                
                if not video_response.get('items'):
                    self._log("Could not get video details", "ERROR", logger=self.ytdl_logger)
                    return None
                    
                video_info = video_response['items'][0]
                
                return {
                    'id': video_id,
                    'title': video_info['snippet']['title'],
                    'duration': 0,  # Duration parsing could be added here
                    'thumbnail': video_info['snippet']['thumbnails']['default']['url'],
                    'webpage_url': f"https://www.youtube.com/watch?v={video_id}"
                }
                
        except Exception as e:
            self._log(f"Error processing query: {str(e)}", "ERROR", logger=self.ytdl_logger, exc_info=True)
            return None