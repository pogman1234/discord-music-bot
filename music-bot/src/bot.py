import asyncio
import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import functools
import json
import time
from googleapiclient.discovery import build

class MusicBot(commands.Bot):
    def __init__(self, command_prefix, intents, youtube_api_key):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        }
        self.ytdl = YoutubeDL(self.ytdl_options)
        self.queue = deque()
        self.current_song = None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor()
        self.volume = 0.5
        self.youtube = build("youtube", "v3", developerKey=youtube_api_key)

    def _log(self, message, severity="INFO", **kwargs):
        entry = {
            "message": message,
            "severity": severity,
            "timestamp": {"seconds": int(time.time()), "nanos": 0},
            **kwargs,
        }
        print(json.dumps(entry))

    async def on_ready(self):
        self._log(f"Logged in as {self.user.name} ({self.user.id})", "INFO")

    async def play_next_song(self, ctx):
        if not self.queue:
            self.current_song = None
            self._log("Queue is empty, nothing to play.", "INFO")
            return

        self.current_song = self.queue.popleft()
        self._log(f"Playing next song: {self.current_song['title']}", "INFO", url=self.current_song['url'])
        source = await self.get_stream_source(self.current_song['url'])
        source.volume = self.volume
        self.current_song['source'] = source

        if ctx.voice_client:
            ctx.voice_client.play(
                source,
                after=lambda e: self.loop.call_soon_threadsafe(self.play_next_song_callback, ctx) if not self.is_playing(ctx) else None
            )

    def play_next_song_callback(self, ctx):
        asyncio.run_coroutine_threadsafe(self.play_next_song(ctx), self.loop)

    async def add_to_queue(self, ctx, query):
        if 'playlist' in query.lower() or 'list' in query.lower():
            self._log(f"Playlists are not supported with YouTube API search, using yt_dlp instead: {query}", "WARNING")
            info = await self.extract_playlist_info(query)
            if 'entries' in info:
                for entry in info['entries']:
                    song_info = await self.extract_song_info_with_ytdlp(entry['url'])
                    if song_info:
                        self.queue.append(song_info)
                self._log(f"Added {len(info['entries'])} songs from playlist to the queue.", "INFO")
            else:
                self._log("No entries found in playlist", "WARNING")
        else:
            song_info = await self.search_and_extract_song_info(query)
            if song_info:
                self.queue.append(song_info)
                self._log(f"Added song to queue: {song_info['title']}", "INFO", url=song_info['url'])

        if not self.is_playing(ctx) and not self.current_song:
            await self.play_next_song(ctx)

        return song_info

    async def search_and_extract_song_info(self, query):
        try:
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=1
            ).execute()

            if not search_response.get("items"):
                self._log(f"No results found for query: {query}", "WARNING")
                return None

            video_id = search_response["items"][0]["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return await self.extract_song_info_with_ytdlp(video_url)

        except Exception as e:
            self._log(f"Error searching with YouTube API: {e}", "ERROR", query=query)
            return None

    async def extract_song_info_with_ytdlp(self, url):
        try:
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            info = await self.loop.run_in_executor(self.thread_pool, partial)
            song_info = {'title': info['title'], 'url': info['url']}
            return song_info
        except Exception as e:
            self._log(f"Error extracting song info with yt_dlp: {e}", "ERROR", url=url)
            return None

    async def extract_playlist_info(self, url):
        try:
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            info = await self.loop.run_in_executor(self.thread_pool, partial)
            return info
        except Exception as e:
            self._log(f"Error extracting playlist info: {e}", "ERROR", url=url)
            return None

    async def get_stream_source(self, url):
        try:
            partial = functools.partial(self.ytdl.extract_info, url, download=False)
            data = await self.loop.run_in_executor(None, partial)
            filename = data['url'] if 'url' in data else self.ytdl.prepare_filename(data)
            return discord.FFmpegPCMAudio(filename)
        except Exception as e:
            self._log(f"Error getting stream source: {e}", "ERROR", url=url)
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