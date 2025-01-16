import asyncio
import discord
from yt_dlp import YoutubeDL
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import functools
import json
import time
import os
import logging
import functools
import subprocess

class MusicBot:
    def __init__(self, bot, youtube):
        """
        Initializes the MusicBot with the given bot and YouTube API client.
        
        Args:
            bot (discord.Client): The Discord bot instance.
            youtube (googleapiclient.discovery.Resource): The YouTube API client.
        """
        self.bot = bot
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(os.path.abspath('/app/music'), '%(extractor)s-%(id)s-%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': False,
            'no_warnings': False,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'verbose': False,
            'debug_printtraffic': True,
            'no_cache_dir': True
        }
        self.ffmpeg_options = {
            'options': '-vn'
        }
        self.ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()
        self.current_song = None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.volume = 0.5
        self.youtube = youtube
        self.download_dir = os.path.abspath("music")
        self.max_concurrent_downloads = 4
        self.currently_downloading = set()

        # Set up loggers
        self.ytdl_logger = logging.getLogger('ytdl')
        self.ytdl_logger.setLevel(logging.INFO)
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

    def get_currently_playing(self):
        """Returns the title of the currently playing song or None if not playing."""
        if self.current_song:
            return self.current_song['title']
        return None

    def is_playing(self, ctx):
        """Checks if the bot is currently playing audio in the guild."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

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
                self._log(f"Error removing file: {e}", "ERROR", logger=self.discord_logger,
                         filepath=self.current_song['filepath'])
        self.current_song = None
        self.currently_downloading.discard(self.current_song['url'])
        asyncio.run_coroutine_threadsafe(self.trigger_next_download(), self.loop)

    async def play_next_song(self, ctx):
        self.ctx = ctx  # Store context for use in after_callback

        if not self.queue:
            self.current_song = None
            self._log("Queue is empty, nothing to play.", "INFO", logger=self.discord_logger)
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song['title']}", "INFO", logger=self.discord_logger,
                 url=self.current_song['url'])

        # Check if the song is already downloaded before attempting to play
        if self.current_song['filepath'] is None:
            self._log(f"Song not yet downloaded, triggering download: {self.current_song['title']}", "INFO", logger=self.discord_logger)
            await self.trigger_download_for_current_song()
            return  # Return and rely on trigger_download_for_current_song to call play_next_song again

        # Log the filepath before creating FFmpegPCMAudio source
        self._log(f"Attempting to play from: {self.current_song['filepath']}", "DEBUG", logger=self.discord_logger)

        try:
            source = discord.FFmpegPCMAudio(self.current_song['filepath'], **self.ffmpeg_options)
        except discord.errors.ClientException as e:
            self._log(f"Error creating FFmpegPCMAudio source: {e}", "ERROR", logger=self.discord_logger)
            await ctx.send("An error occurred while preparing the song for playback.")
            return

        source.volume = self.volume
        self.current_song['source'] = source

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

    async def add_to_queue(self, ctx, query):
        if 'playlist' in query.lower() or 'list' in query.lower():
            self._log(f"Playlists are not supported with YouTube API search, using yt_dlp instead: {query}",
                     "WARNING", logger=self.discord_logger)
            info = await self.extract_playlist_info(query)
            if 'entries' in info:
                for entry in info['entries']:
                    song_info = {
                        'title': entry['title'],
                        'url': entry['url'],
                        'filepath': None  # Mark as not downloaded yet
                    }
                    self.queue.append(song_info)
                    self._log(f"Added song from playlist to queue: {song_info['title']}", "INFO",
                             logger=self.discord_logger, url=song_info['url'])
                # Start downloading the first song immediately if nothing is playing
                if not self.is_playing(ctx) and not self.current_song:
                    await self.trigger_download_for_current_song()
            else:
                self._log("No entries found in playlist", "WARNING", logger=self.discord_logger)
        else:
            song_info = await self.search_song(query)
            self._log(f"Song info in add_to_queue: {song_info}", "DEBUG", logger=self.discord_logger)
            if song_info:
                song_info['filepath'] = None  # Mark as not downloaded yet
                self.queue.append(song_info)
                self._log(f"Added song to queue: {song_info['title']}", "INFO", logger=self.discord_logger,
                         url=song_info['url'])

        # Trigger download process
        await self.trigger_next_download()

        if not self.is_playing(ctx) and not self.current_song:
            await self.play_next_song(ctx)

        return song_info

    async def search_song(self, query):
        """Searches for a song using the YouTube API and returns song info."""
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
            video_title = search_response["items"][0]["snippet"]["title"]

            self._log(f"Found video URL: {video_url}", "INFO", logger=self.discord_logger)

            return {'title': video_title, 'url': video_url}

        except Exception as e:
            self._log(f"Error searching with YouTube API: {e}", "ERROR", logger=self.discord_logger, query=query)
            return None

    async def download_song(self, song_info):
        """
        Downloads a song using yt_dlp in a background thread.

        Args:
            song_info (dict): A dictionary containing the song information, including the URL.

        Updates:
            song_info (dict): Updates the dictionary with the filepath of the downloaded song.

        Returns:
            dict: The updated song_info dictionary with the filepath of the downloaded song, or None if an error occurs.
        """
        url = song_info['url']
        try:
            self._log(f"Downloading song from URL: {url}", "INFO", logger=self.ytdl_logger)

            partial = functools.partial(self.ytdl.extract_info, url, download=True)
            info = await self.loop.run_in_executor(self.thread_pool, partial)
            self._log(f"Current working directory: {os.getcwd()}")
            relative_filepath = self.ytdl.prepare_filename(info)
            absolute_filepath = os.path.abspath(relative_filepath)
            song_info['filepath'] = absolute_filepath
            self._log(f"Downloaded file path: {absolute_filepath}")

            self._log(f"Successfully downloaded: {info['title']} into {song_info['filepath']}", "INFO", logger=self.ytdl_logger)
            
            if song_info == self.current_song:
                await self.play_next_song(self.ctx)
                
            return song_info

        except Exception as e:
            self._log(f"Error downloading song with yt_dlp: {e}", "ERROR", logger=self.ytdl_logger, url=url)
            if 'info' in locals() and info:
                self._log(f"Partial yt_dlp info: {info}", "DEBUG", logger=self.ytdl_logger)
            return None
        finally:
            self.currently_downloading.discard(url)
            await self.trigger_next_download()
            
    async def trigger_download_for_current_song(self):
        """Triggers the download of the current song and sets up a callback for when it's done."""
        if self.current_song and self.current_song['filepath'] is None and self.current_song['url'] not in self.currently_downloading:
            self.currently_downloading.add(self.current_song['url'])
            # Create a task for the download process
            download_task = asyncio.create_task(self.download_song(self.current_song))
            
            self._log(f"Download triggered for current song: {self.current_song['title']}", "INFO", logger=self.discord_logger)

    async def trigger_next_download(self):
        """Triggers the download of the next song in the queue if conditions are met."""
        # Count the number of songs that are either downloaded or currently being downloaded
        downloaded_or_downloading_count = sum(1 for song in self.queue if song['filepath'] is not None or song['url'] in self.currently_downloading)

        # Start downloading if we haven't reached the max concurrent downloads and there are songs in the queue
        while len(self.currently_downloading) < self.max_concurrent_downloads and downloaded_or_downloading_count < len(self.queue) and downloaded_or_downloading_count < 4:
            for song in self.queue:
                if song['filepath'] is None and song['url'] not in self.currently_downloading:
                    self.currently_downloading.add(song['url'])
                    # Start the download process in the background
                    asyncio.create_task(self.download_song(song))
                    downloaded_or_downloading_count += 1
                    break

    async def extract_playlist_info(self, url):
        """
        Extracts information about a YouTube playlist using yt_dlp.
        Skips entries that are unavailable due to copyright, termination, or other reasons.

        Args:
            url: The URL of the YouTube playlist.

        Returns:
            A dictionary containing playlist information, including a list of entries (videos),
            or None if an error occurs.
        """
        try:
            self._log(f"Extracting playlist info for URL: {url}", "INFO", logger=self.ytdl_logger)

            # Use yt_dlp to extract playlist information without downloading
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            info = await self.loop.run_in_executor(self.thread_pool, partial)

            if not info:
                self._log(f"Could not extract playlist info for URL: {url}", "WARNING", logger=self.ytdl_logger)
                return None

            self._log(f"Extracted playlist info: {info}", "DEBUG", logger=self.ytdl_logger)

            # Check if the extracted info is a playlist
            if 'entries' not in info:
                self._log(f"URL does not appear to be a playlist: {url}", "WARNING", logger=self.ytdl_logger)
                return None

            # Filter out unavailable entries
            filtered_entries = []
            for entry in info['entries']:
                if entry is not None:
                    try:
                        # Attempt to get the 'id' of the entry. If it fails, the entry is likely unavailable.
                        entry_id = entry.get('id')
                        if entry_id is None:
                            self._log(f"Skipping unavailable entry: No ID found", "INFO", logger=self.ytdl_logger)
                            continue  # Skip this entry

                        # Additional check for 'ie_key' as before
                        if entry.get('ie_key') == 'RemovedVideo':
                            self._log(f"Skipping unavailable entry: {entry_id} (RemovedVideo)", "INFO", logger=self.ytdl_logger)
                            continue # Skip this entry

                        # If all checks pass, add the entry to the filtered list
                        filtered_entries.append(entry)
                        
                    except Exception as e:
                        self._log(f"Error processing entry {entry.get('id', 'Unknown')}: {e}", "ERROR", logger=self.ytdl_logger)
                        continue  # Skip this entry on error
                else:
                    self._log(f"Skipping unavailable entry: None", "INFO", logger=self.ytdl_logger)

            info['entries'] = filtered_entries
            return info

        except Exception as e:
            self._log(f"Error extracting playlist info: {e}", "ERROR", logger=self.ytdl_logger, url=url)
            return None