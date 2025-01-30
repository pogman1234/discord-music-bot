import asyncio
import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from services.queue_manager import QueueManager
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class DownloadStatus:
    """Tracks download status for queue items"""
    guild_id: int
    is_downloading: bool = False
    current_downloads: List[str] = None  # List of video_ids currently downloading
    max_concurrent: int = 2  # Number of songs to preload
    
    def __post_init__(self):
        self.current_downloads = []

class QueueDownloader:
    def __init__(self, music_bot, youtube, get_queue_manager, guilds):
        self.music_bot = music_bot
        self.youtube = youtube
        self.get_queue_manager = get_queue_manager
        self.guilds = guilds
        
        cwd = os.getcwd()
        self.download_dir = os.path.abspath(os.path.join(cwd, "music"))
        os.makedirs(self.download_dir, exist_ok=True)

        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.statuses = {}  # guild_id -> DownloadStatus
        self._download_tasks = {}  # guild_id -> Task
        self.cache = {"queries": {}, "videos": {}}  # Initialize cache
        self.max_retries = 3  # Define max_retries attribute
        self.download_lock = asyncio.Lock()  # Define download_lock attribute

        # Define ytdl_opts attribute
        self.ytdl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.download_dir, '%(id)s'),  # Change extension here
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'logger': logging.getLogger('ytdl'),
            'quiet': False,
            'extract_flat': False,
            'no_warnings': True
        }

    async def start(self):
        for guild in self.guilds:
            guild_id = int(guild["id"])
            self.statuses[guild_id] = DownloadStatus(guild_id=guild_id)
            self._download_tasks[guild_id] = asyncio.create_task(self._monitor_queue(guild_id))
            logger.info(f"Started download monitor for guild {guild_id}")

    async def stop(self):
        """Stop all download monitoring processes"""
        for guild_id, task in self._download_tasks.items():
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Stopped download monitor for guild {guild_id}")
        self._download_tasks.clear()
        self.statuses.clear()

    async def cleanup_guild(self, guild_id: int):
        """Cleanup resources for specific guild"""
        if guild_id in self._download_tasks:
            self._download_tasks[guild_id].cancel()
            try:
                await self._download_tasks[guild_id]
            except asyncio.CancelledError:
                pass
            del self._download_tasks[guild_id]
            del self.statuses[guild_id]
            logger.info(f"Cleaned up download monitor for guild {guild_id}")

    async def _monitor_queue(self, guild_id: int):
        queue_manager = self.get_queue_manager(guild_id)
        while True:
            try:
                # Use get_queue_info and handle it as a list
                queue_info = queue_manager.get_queue_info()
                for info in queue_info:
                    # Check if 'is_downloading' key exists
                    if not info.get('is_downloading', False):
                        # Correct usage of queue_info attributes
                        logger.debug(f"Queue info for guild {guild_id}: {info}")
                await self._process_downloads(queue_manager)  # Ensure downloads are processed
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in queue download monitor: {str(e)}", exc_info=True)
                await asyncio.sleep(5)

    async def _process_downloads(self, queue_manager):
        """Process downloads for upcoming songs in queue"""
        guild_id = queue_manager.guild_id
        if guild_id not in self.statuses:
            logger.warning(f"No download status found for guild {guild_id}")
            return
            
        status = self.statuses[guild_id]
        if status.is_downloading:
            return

        # Get next few songs that need downloading
        upcoming_songs = await self._get_upcoming_songs(queue_manager)
        if not upcoming_songs:
            return

        status.is_downloading = True
        try:
            download_tasks = []
            for song in upcoming_songs:
                # Check if song needs downloading and isn't already being downloaded
                if (not song.is_downloaded and 
                    song.video_id not in status.current_downloads):
                    status.current_downloads.append(song.video_id)
                    download_tasks.append(self._download_song(song))
            await asyncio.gather(*download_tasks)
        finally:
            status.is_downloading = False

    async def _get_upcoming_songs(self, queue_manager) -> List:
        """Get the next few songs from queue that need downloading"""
        guild_id = queue_manager.guild_id
        if guild_id not in self.statuses:
            return []
            
        queue_state = queue_manager.get_state()
        upcoming = []
        
        # Get songs from queue up to max_concurrent
        status = self.statuses[guild_id]
        for song in list(queue_state.queue)[:status.max_concurrent]:
            if not song.is_downloaded:
                upcoming.append(song)
                
        return upcoming

    async def _download_song(self, song) -> bool:
        """Download a single song"""
        try:
            logger.debug(f"Starting download for upcoming song: {song.title}")
            success = await self.download_song(song)
            
            if success:
                logger.info(f"Successfully pre-downloaded: {song.title}")
            else:
                logger.error(f"Failed to pre-download: {song.title}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error downloading song {song.title}: {e}")
            return False
        finally:
            # Remove from all guild download statuses
            for status in self.statuses.values():
                if song.video_id in status.current_downloads:
                    status.current_downloads.remove(song.video_id)

    async def download_song(self, song) -> bool:
        """Download a song to the music directory"""
        filepath = os.path.join(self.download_dir, f"{song.video_id}.mp3")
        
        # Check if already downloaded first
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            logger.info(f"Using cached file: {filepath}")
            song.set_downloaded(filepath)
            return True

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Starting download attempt {attempt + 1} for: {song.title}")
                logger.info(f"Download path: {filepath}")
                
                async with self.download_lock:
                    with yt_dlp.YoutubeDL(self.ytdl_opts) as ytdl:
                        try:
                            def _download():
                                return ytdl.download([song.webpage_url])
                            
                            result = await asyncio.get_event_loop().run_in_executor(
                                self.thread_pool, _download
                            )
                            
                            # Wait a bit for file system
                            await asyncio.sleep(0.5)
                            
                            # Verify download succeeded
                            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                                song.set_downloaded(filepath)
                                logger.info(f"Successfully downloaded to: {filepath}")
                                return True
                            
                            logger.error(f"Download failed with result: {result}")
                        except Exception as e:
                            logger.error(f"Download failed: {e}")
                            raise
                            
                logger.error(f"File not found or empty after download: {filepath}")
                                
            except Exception as e:
                logger.error(f"Download attempt {attempt + 1} failed for {song.title}: {e}")
                if attempt == self.max_retries - 1:
                    return False
                await asyncio.sleep(1)
                    
        return False

    async def search_video(self, query: str) -> Optional[str]:
        """Search for a video on YouTube"""
        # Check cache first
        for cached_query, data in self.cache["queries"].items():
            if SequenceMatcher(None, query, cached_query).ratio() > 0.8:
                return data["video_id"]

        # Perform search using YouTube API
        search_response = self.youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=1
        ).execute()

        if not search_response["items"]:
            return None

        video_id = search_response["items"][0]["id"]["videoId"]
        self.cache["queries"][query] = {"video_id": video_id}
        return video_id

    async def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed video information"""
        try:
            video_request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            
            video_response = await asyncio.get_event_loop().run_in_executor(
                None, video_request.execute
            )

            if not video_response.get('items'):
                return None

            video_info = video_response['items'][0]
            duration = self._parse_duration(video_info['contentDetails']['duration'])

            return {
                'snippet': video_info['snippet'],
                'duration': duration  # Duration in seconds
            }
            
        except Exception as e:
            logger.error(f"Error getting video details: {e}")
            return None

    def _parse_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration to seconds"""
        try:
            # Remove PT from start
            duration = duration.replace('PT', '')
            
            seconds = 0
            # Handle hours
            if 'H' in duration:
                hours = int(duration.split('H')[0])
                seconds += hours * 3600
                duration = duration.split('H')[1]
            
            # Handle minutes
            if 'M' in duration:
                minutes = int(duration.split('M')[0])
                seconds += minutes * 60
                duration = duration.split('M')[1]
            
            # Handle seconds
            if 'S' in duration:
                seconds += int(duration.split('S')[0])
                
            return seconds
            
        except Exception as e:
            logger.error(f"Error parsing duration: {e}")
            return 0

    async def extract_info(self, url: str) -> Optional[Dict]:
        """Extract video information using yt-dlp"""
        try:
            with yt_dlp.YoutubeDL(self.ytdl_opts) as ytdl:
                def _get_info():
                    info = ytdl.extract_info(url, download=False)
                    logger.debug(f"Raw video info: {info}")
                    return info
                    
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool, _get_info
                )
                
                if info:
                    # Handle playlists and single videos
                    if 'entries' in info:
                        video_info = info['entries'][0]  # Get first video from playlist
                    else:
                        video_info = info  # Single video

                    duration = int(video_info.get('duration', 0))  # Ensure int conversion

                    return {
                        'id': video_info['id'],
                        'title': video_info['title'],
                        'duration': duration,
                        'thumbnail': video_info.get('thumbnail', ''),
                        'webpage_url': video_info['webpage_url']
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            return None
