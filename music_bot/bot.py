import asyncio
import discord
import json
import requests
import os
import logging
from typing import Optional, Dict, List
from models.song import Song
from services.queue_manager import QueueManager
from services.queue_downloader import QueueDownloader
from services.audio_player import AudioPlayer

logger = logging.getLogger(__name__)

class MusicBot:
    def __init__(self, bot, youtube, guilds):
        self.bot = bot
        self.youtube = youtube
        self.guilds = guilds
        
        # Initialize services
        self.download_dir = "music"
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.queue_managers = {}  # Dictionary to hold queue managers for each guild
        self.queue_tasks = {}  # Dictionary to hold queue tasks for each guild
        
        # Initialize queue downloader
        self.queue_downloader = QueueDownloader(self, youtube, self.get_queue_manager, self.guilds)
        
        # Initialize audio player
        self.audio_player = AudioPlayer(self)
        
        # Start queue downloader in background
        asyncio.create_task(self.queue_downloader.start())

        # Initialize queues for each guild
        asyncio.create_task(self.initialize_queues())

    async def initialize_queues(self):
        """Initialize queue managers for all guilds"""
        try:
            for guild in self.guilds:
                guild_id = int(guild["id"])
                self.get_queue_manager(guild_id)
                logger.info(f"Initialized queue manager for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error initializing queues: {e}", exc_info=True)

    def get_queue_manager(self, guild_id: int) -> QueueManager:
        """Get or create a queue manager for the guild"""
        try:
            if guild_id not in self.queue_managers:
                logger.info(f"Creating new queue manager for guild {guild_id}")
                self.queue_managers[guild_id] = QueueManager(self, guild_id)
            return self.queue_managers[guild_id]
        except Exception as e:
            logger.error(f"Error getting queue manager for guild {guild_id}: {e}", exc_info=True)
            raise

    async def add_to_queue(self, ctx, query: str, guild_id: int) -> Optional[Dict]:
        """Add a song to the queue from URL or search query"""
        try:
            song_data = await self.process_url_or_search(query)
            if not song_data:
                return None

            song = Song(**song_data)
            queue_manager = self.get_queue_manager(guild_id)
            await queue_manager.add(song)
            
            if guild_id not in self.queue_tasks:
                self.queue_tasks[guild_id] = asyncio.create_task(self.process_queue(ctx, guild_id))

            return song.to_dict()

        except Exception as e:
            logger.error(f"Error adding song to queue: {str(e)}", exc_info=True)
            return None

    async def process_queue(self, ctx, guild_id: int):
        """Main queue processing loop for a specific guild"""
        queue_manager = self.get_queue_manager(guild_id)
        while True:
            try:
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    logger.debug("Voice client not connected, waiting...")
                    await asyncio.sleep(1)
                    continue

                if not queue_manager.is_playing:
                    next_song = await queue_manager.get_next()
                    if (next_song):
                        logger.debug(f"Got next song: {next_song.title}")
                        
                        # Start playing if already downloaded
                        if next_song.is_downloaded:
                            await queue_manager.set_current(next_song)
                            success = await self.audio_player.play_next(ctx, next_song)
                            
                            if not success:
                                logger.error(f"Failed to play: {next_song.title}")
                                await queue_manager.clear_current()
                        else:
                            # If not downloaded, initiate download and wait
                            logger.debug(f"Waiting for download: {next_song.title}")
                            success = await self.queue_downloader.download_song(next_song)
                            if success:
                                await queue_manager.set_current(next_song)
                                success = await self.audio_player.play_next(ctx, next_song)
                                if not success:
                                    logger.error(f"Failed to play: {next_song.title}")
                                    await queue_manager.clear_current()
                            else:
                                logger.error(f"Failed to download: {next_song.title}")

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Queue processing error: {str(e)}", exc_info=True)
                await queue_manager.clear_current()
                await asyncio.sleep(5)

    async def process_url_or_search(self, query: str) -> Optional[Dict]:
        """Process URL or search query to get song information"""
        if any(domain in query.lower() for domain in ['youtube.com', 'youtu.be']):
            return await self._process_url(query)
        return await self._process_search(query)

    async def _process_url(self, url: str) -> Optional[Dict]:
        """Process YouTube URL"""
        info = await self.queue_downloader.extract_info(url)
        if not info:
            return None
            
        return {
            'id': info['id'],
            'title': info['title'],
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'webpage_url': info['webpage_url']
        }

    async def _process_search(self, query: str) -> Optional[Dict]:
        """Process search query using YouTube API"""
        video_id = await self.queue_downloader.search_video(query)
        if not video_id:
            return None
            
        video_info = await self.queue_downloader.get_video_details(video_id)
        if not video_info:
            return None

        return {
            'id': video_id,
            'title': video_info['snippet']['title'],
            'duration': video_info['duration'],
            'thumbnail': video_info['snippet']['thumbnails']['default']['url'],
            'webpage_url': f"https://www.youtube.com/watch?v={video_id}"
        }