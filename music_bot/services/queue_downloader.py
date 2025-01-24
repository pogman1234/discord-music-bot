import asyncio
import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from .queue_manager import QueueManager
import logging
import json
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class DownloadStatus:
    """Tracks download status for queue items"""
    is_downloading: bool = False
    current_downloads: List[str] = None  # List of video_ids currently downloading
    max_concurrent: int = 2  # Number of songs to preload
    
    def __post_init__(self):
        self.current_downloads = []

class QueueDownloader:
    def __init__(self, queue_manager: QueueManager, youtube, music_bot):
        self.queue_manager = queue_manager
        self.youtube = youtube
        
        # Set up download directory
        cwd = os.getcwd()
        self.download_dir = os.path.abspath(os.path.join(cwd, "music"))
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.status = DownloadStatus()
        self.download_lock = asyncio.Lock()
        self._download_task = None
        self.max_retries = 3
        
        # Modified ytdl_opts - removed skip_download flag
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
        self.cache_file = "song_cache.json"
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load or create cache file"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            cache = {"queries": {}, "videos": {}}
            self._save_cache(cache)
            return cache
            
    def _save_cache(self, cache: dict):
        """Save cache to file"""
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
            
    def _similarity_score(self, a: str, b: str) -> float:
        """Calculate string similarity"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    async def start(self):
        """Start the download monitoring process"""
        if not self._download_task:
            self._download_task = asyncio.create_task(self._monitor_queue())
            logger.info("Queue download monitor started")

    async def stop(self):
        """Stop the download monitoring process"""
        if self._download_task:
            self._download_task.cancel()
            try:
                await self._download_task
            except asyncio.CancelledError:
                pass
            self._download_task = None
            logger.info("Queue download monitor stopped")

    async def _monitor_queue(self):
        """Monitor queue and initiate downloads for upcoming songs"""
        while True:
            try:
                await self._process_downloads()  # Remove the is_downloading check
                await asyncio.sleep(0.5)  # Check more frequently
            except Exception as e:
                logger.error(f"Error in queue download monitor: {e}")
                await asyncio.sleep(1)

    async def _process_downloads(self):
        """Process downloads for upcoming songs in queue"""
        if self.status.is_downloading:
            return

        # Get next few songs that need downloading
        upcoming_songs = await self._get_upcoming_songs()
        if not upcoming_songs:
            return

        self.status.is_downloading = True
        try:
            download_tasks = []
            for song in upcoming_songs:
                # Check if song needs downloading and isn't already being downloaded
                if (not song.is_downloaded and 
                    song.video_id not in self.status.current_downloads and
                    len(download_tasks) < self.status.max_concurrent):
                        
                    self.status.current_downloads.append(song.video_id)
                    # Create a task for the download
                    task = asyncio.create_task(self._download_song(song))
                    download_tasks.append(task)

            if download_tasks:
                # Run downloads concurrently and wait for them to complete
                await asyncio.gather(*download_tasks)

        except Exception as e:
            logger.error(f"Error processing downloads: {e}")
        finally:
            self.status.is_downloading = False
            self.status.current_downloads.clear()

    async def _get_upcoming_songs(self) -> List:
        """Get the next few songs from queue that need downloading"""
        queue_state = self.queue_manager.get_state()
        upcoming = []
        
        # Get songs from queue up to max_concurrent
        for song in list(queue_state.queue)[:self.status.max_concurrent]:
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
            if song.video_id in self.status.current_downloads:
                self.status.current_downloads.remove(song.video_id)

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
        """Tiered search: Cache -> yt-dlp -> YouTube API"""
        # 1. Check cache with fuzzy matching
        normalized_query = query.lower().strip()
        best_match = None
        best_score = 0
        
        for cached_query, data in self.cache["queries"].items():
            score = self._similarity_score(normalized_query, cached_query)
            if score > 0.9 and score > best_score:  # 90% similarity threshold
                best_score = score
                best_match = data["video_id"]
                
        if best_match:
            logger.info(f"Cache hit for query: {query}")
            return best_match

        # 2. Try yt-dlp
        try:
            with yt_dlp.YoutubeDL(self.ytdl_opts) as ytdl:
                def _search():
                    return ytdl.extract_info(f"ytsearch1:{query}", download=False)
                
                info = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool, _search
                )
                
                if info and info.get('entries'):
                    video = info['entries'][0]
                    # Cache the result
                    self.cache["queries"][normalized_query] = {
                        "video_id": video['id'],
                        "title": video['title'],
                        "duration": int(video.get('duration', 0)),
                        "thumbnail": video.get('thumbnail', ''),
                        "webpage_url": f"https://www.youtube.com/watch?v={video['id']}"
                    }
                    self.cache["videos"][video['id']] = self.cache["queries"][normalized_query]
                    self._save_cache(self.cache)
                    return video['id']
                    
        except Exception as e:
            logger.error(f"yt-dlp search error: {e}")

        # 3. Fallback to YouTube API
        try:
            video_id = await self._youtube_api_search(query)
            if video_id:
                # Cache the result if found
                video_info = await self.get_video_details(video_id)
                if video_info:
                    self.cache["queries"][normalized_query] = {
                        "video_id": video_id,
                        "title": video_info['snippet']['title'],
                        "duration": video_info['duration'],
                        "thumbnail": video_info['snippet']['thumbnails']['default']['url'],
                        "webpage_url": f"https://www.youtube.com/watch?v={video_id}"
                    }
                    self.cache["videos"][video_id] = self.cache["queries"][normalized_query]
                    self._save_cache(self.cache)
                return video_id
                
        except Exception as e:
            logger.error(f"YouTube API search error: {e}")
            
        return None

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