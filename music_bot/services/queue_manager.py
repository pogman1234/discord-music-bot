from collections import deque
import asyncio
from typing import Optional, List, Dict
import logging
from dataclasses import dataclass, field
from models.song import Song
import logging

logger = logging.getLogger(__name__)

@dataclass
class QueueState:
    """Represents the current state of the music queue"""
    current_song: Optional[Song] = None
    is_playing: bool = False
    queue: deque = field(default_factory=deque)

class QueueManager:
    def __init__(self, music_bot):
        self.music_bot = music_bot
        self.queue = deque()
        self.queue_lock = asyncio.Lock()
        self.current_song: Optional[Song] = None
        self.is_playing: bool = False

    async def add(self, song: Song) -> bool:
        """Add a song to the queue"""
        try:
            async with self.queue_lock:
                self.queue.append(song)
                logger.info(f"Added song to queue: {song.title} (Queue size: {len(self.queue)})")
                return True
        except Exception as e:
            logger.error(f"Error adding song to queue: {e}")
            return False

    async def remove(self, index: int) -> Optional[Song]:
        """Remove a song from the queue at given index"""
        try:
            async with self.queue_lock:
                if 0 <= index < len(self.queue):
                    return self.queue.pop(index)
                return None
        except Exception as e:
            logger.error(f"Error removing song from queue: {e}")
            return None

    async def get_next(self) -> Optional[Song]:
        """Get next song from queue"""
        try:
            async with self.queue_lock:
                if not self.queue:
                    logger.debug("Queue is empty")
                    return None
                next_song = self.queue.popleft()
                logger.info(f"Getting next song: {next_song.title} (Remaining: {len(self.queue)})")
                return next_song
        except Exception as e:
            logger.error(f"Error getting next song: {e}")
            return None

    async def set_current(self, song: Song) -> None:
        """Set currently playing song"""
        try:
            async with self.queue_lock:
                old_song = self.current_song
                self.current_song = song
                self.is_playing = True
                logger.info(f"Now playing: {song.title} (Previous: {old_song.title if old_song else 'None'})")
        except Exception as e:
            logger.error(f"Error setting current song: {e}")
            self.is_playing = False
            self.current_song = None

    async def clear_current(self) -> None:
        """Clear currently playing song"""
        try:
            async with self.queue_lock:
                old_song = self.current_song
                self.current_song = None
                self.is_playing = False
                logger.info(f"Cleared current song: {old_song.title if old_song else 'None'}")
        except Exception as e:
            logger.error(f"Error clearing current song: {e}")

    async def clear(self) -> None:
        """Clear entire queue"""
        async with self.queue_lock:
            self.queue.clear()
            logger.info("Queue cleared")

    def get_queue_info(self) -> List[Dict]:
        """Get queue information for display"""
        return [song.to_dict() for song in self.queue]

    def get_state(self) -> QueueState:
        """Get current queue state"""
        try:
            return QueueState(
                current_song=self.current_song,
                is_playing=self.is_playing,
                queue=self.queue.copy()
            )
        except Exception as e:
            logger.error(f"Error getting queue state: {e}")
            return QueueState()

    def get_queue_length(self) -> int:
        """Get current queue length"""
        return len(self.queue)