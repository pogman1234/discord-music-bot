import asyncio
import discord
import json
import time
import os
import logging
from typing import Optional, Dict, List
from models.song import Song
from services.queue_manager import QueueManager
from services.queue_downloader import QueueDownloader
from services.audio_player import AudioPlayer

logger = logging.getLogger(__name__)

class MusicBot:
    def __init__(self, bot, youtube):
        self.bot = bot
        self.youtube = youtube
        
        # Initialize services
        self.download_dir = "music"
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.queue_manager = QueueManager(self)
        self.queue_downloader = QueueDownloader(
            queue_manager=self.queue_manager,
            youtube=youtube,
            music_bot=self
        )
        self.audio_player = AudioPlayer(self)
        self.queue_task = None
        
        # Start queue downloader in background
        asyncio.create_task(self.queue_downloader.start())

    # Add these getter methods to properly expose queue information
    def get_queue_info(self) -> List[Dict]:
        """Get information about all songs in queue"""
        return self.queue_manager.get_queue_info()

    def get_current_song(self) -> Optional[Dict]:
        """Get currently playing song"""
        if self.queue_manager.current_song:
            return self.queue_manager.current_song.to_dict()
        return None

    @property
    def is_playing(self) -> bool:
        """Get playing status"""
        return self.queue_manager.is_playing

    async def add_to_queue(self, ctx, query: str) -> Optional[Dict]:
        """Add a song to the queue from URL or search query"""
        logger.info(f"Adding to queue: {query}")
        try:
            song_data = await self.process_url_or_search(query)
            if not song_data:
                await ctx.send("Could not find a video based on your query.")
                return None

            song = Song(**song_data)
            await self.queue_manager.add(song)
            
            if not self.queue_task:
                self.queue_task = asyncio.create_task(self.process_queue(ctx))

            await ctx.send(f"Added to queue: {song.title}")
            return song.to_dict()

        except Exception as e:
            logger.error(f"Error adding song to queue: {str(e)}", exc_info=True)
            await ctx.send(f"Error adding song to queue: {str(e)}")
            return None

    async def process_queue(self, ctx):
        """Main queue processing loop"""
        while True:
            try:
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    logger.debug("Voice client not connected, waiting...")
                    await asyncio.sleep(1)
                    continue

                if not self.queue_manager.is_playing:
                    next_song = await self.queue_manager.get_next()
                    if (next_song):
                        logger.debug(f"Got next song: {next_song.title}")
                        
                        # Start playing if already downloaded
                        if next_song.is_downloaded:
                            await self.queue_manager.set_current(next_song)
                            success = await self.audio_player.play_next(ctx, next_song)
                            
                            if not success:
                                logger.error(f"Failed to play: {next_song.title}")
                                await self.queue_manager.clear_current()
                        else:
                            # If not downloaded, initiate download and wait
                            logger.debug(f"Waiting for download: {next_song.title}")
                            success = await self.queue_downloader.download_song(next_song)
                            if success:
                                await self.queue_manager.set_current(next_song)
                                success = await self.audio_player.play_next(ctx, next_song)
                                if not success:
                                    logger.error(f"Failed to play: {next_song.title}")
                                    await self.queue_manager.clear_current()
                            else:
                                logger.error(f"Failed to download: {next_song.title}")

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Queue processing error: {str(e)}", exc_info=True)
                await self.queue_manager.clear_current()
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