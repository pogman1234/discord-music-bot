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
    """Represents the current state of the music queue for a guild"""
    guild_id: int
    current_song: Optional[Song] = None
    is_playing: bool = False
    queue: deque = field(default_factory=deque)

class QueueManager:
    def __init__(self, music_bot, guild_id: int):
        self.music_bot = music_bot
        self.guild_id = guild_id
        self.queue = []
        self.current_song = None
        self.is_playing = False
        logger.info(f"Initialized queue manager for guild {guild_id}")

    async def add(self, song: Song) -> bool:
        """Add a song to the queue"""
        try:
            self.queue.append(song)
            logger.info(f"Added song to queue for guild {self.guild_id}: {song.title} (Queue size: {len(self.queue)})")
            return True
        except Exception as e:
            logger.error(f"Error adding song to queue for guild {self.guild_id}: {e}")
            return False

    async def remove(self, index: int) -> Optional[Song]:
        """Remove a song from the queue at given index"""
        try:
            if 0 <= index < len(self.queue):
                removed = self.queue.pop(index)
                logger.info(f"Removed song from queue for guild {self.guild_id}: {removed.title}")
                return removed
            return None
        except Exception as e:
            logger.error(f"Error removing song from queue for guild {self.guild_id}: {e}")
            return None

    async def get_next(self) -> Optional[Song]:
        """Get next song from queue"""
        try:
            if not self.queue:
                logger.debug(f"Queue is empty for guild {self.guild_id}")
                return None
            next_song = self.queue.pop(0)
            logger.info(f"Getting next song for guild {self.guild_id}: {next_song.title} (Remaining: {len(self.queue)})")
            return next_song
        except Exception as e:
            logger.error(f"Error getting next song for guild {self.guild_id}: {e}")
            return None

    async def set_current(self, song: Song) -> None:
        """Set currently playing song"""
        try:
            old_song = self.current_song
            self.current_song = song
            self.is_playing = True
            logger.info(f"Now playing in guild {self.guild_id}: {song.title} (Previous: {old_song.title if old_song else 'None'})")
        except Exception as e:
            logger.error(f"Error setting current song for guild {self.guild_id}: {e}")
            self.is_playing = False
            self.current_song = None

    async def clear_current(self) -> None:
        """Clear currently playing song"""
        try:
            old_song = self.current_song
            self.current_song = None
            self.is_playing = False
            logger.info(f"Cleared current song for guild {self.guild_id}: {old_song.title if old_song else 'None'}")
        except Exception as e:
            logger.error(f"Error clearing current song for guild {self.guild_id}: {e}")

    async def clear(self) -> None:
        """Clear entire queue"""
        self.queue.clear()
        logger.info(f"Queue cleared for guild {self.guild_id}")

    def get_queue_info(self) -> List[Dict]:
        """Get queue information for display"""
        return [song.to_dict() for song in self.queue]

    def get_state(self) -> QueueState:
        """Get current queue state"""
        try:
            return QueueState(
                guild_id=self.guild_id,
                queue=deque(self.queue),
                current_song=self.current_song,
                is_playing=self.is_playing                
            )
        except Exception as e:
            logger.error(f"Error getting queue state for guild {self.guild_id}: {e}")
            return QueueState(guild_id=self.guild_id)

    def get_queue_length(self) -> int:
        """Get current queue length"""
        return len(self.queue)

    def get_currently_playing(self):
        """Return the currently playing song"""
        return self.current_song

    async def cleanup(self):
        """Cleanup resources for this guild"""
        try:
            await self.clear()
            await self.clear_current()
            logger.info(f"Cleaned up queue manager for guild {self.guild_id}")
        except Exception as e:
            logger.error(f"Error cleaning up queue manager for guild {self.guild_id}: {e}")
