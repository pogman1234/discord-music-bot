import asyncio
import discord
import logging
from dataclasses import dataclass
from typing import Optional, Callable
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class PlaybackStatus:
    """Represents current playback status"""
    guild_id: int = 0
    is_playing: bool = False
    started_at: float = 0
    current_position: float = 0
    duration: int = 0
    volume: float = 0.5

class AudioPlayer:
    def __init__(self, music_bot):
        self.music_bot = music_bot
        self.voice_clients = {}  # guild_id -> voice_client
        self.statuses = {}  # guild_id -> PlaybackStatus
        self.audio_sources = {}  # guild_id -> audio_source
        self.progress_tasks = {}  # guild_id -> progress_task
        self.loop = asyncio.get_event_loop()
        
        self.ffmpeg_options = {
            'options': '-vn -b:a 192k',
        }

    async def play(self, voice_client: discord.VoiceClient, filepath: str, duration: int, 
                  volume: float = 0.5, after_callback: Callable = None) -> bool:
        guild_id = voice_client.guild.id
        try:
            if voice_client.is_playing():
                voice_client.stop()

            self.voice_clients[guild_id] = voice_client
            self.statuses[guild_id] = PlaybackStatus(
                guild_id=guild_id,
                is_playing=True,
                started_at=time.time(),
                duration=duration,
                volume=volume
            )

            audio_source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    filepath,
                    **self.ffmpeg_options
                ),
                volume=volume
            )
            self.audio_sources[guild_id] = audio_source

            # Start progress tracking
            if guild_id in self.progress_tasks:
                self.progress_tasks[guild_id].cancel()
            self.progress_tasks[guild_id] = asyncio.create_task(self._track_progress(guild_id))

            voice_client.play(
                audio_source,
                after=lambda e: self._playback_finished(guild_id, e, after_callback)
            )
            
            logger.info(f"Started playback for guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting playback for guild {guild_id}: {e}")
            if guild_id in self.statuses:
                self.statuses[guild_id].is_playing = False
            return False

    async def play_next(self, ctx, song):
        """Play next song in queue"""
        try:
            logger.info(f"Attempting to play: {song.title}")
            
            if not song.is_downloaded:
                logger.error(f"Song not downloaded: {song.title}")
                return False

            def after_callback(error):
                # Use loop.create_task instead of asyncio.create_task
                self.loop.create_task(self._handle_song_finished(ctx, error))

            success = await self.play(
                ctx.voice_client,
                song.filepath,
                song.duration,
                after_callback=after_callback
            )

            if success:
                logger.info(f"Now playing: {song.title}")
            else:
                logger.error(f"Failed to play: {song.title}")
            
            return success

        except Exception as e:
            logger.error(f"Error in play_next: {e}")
            return False

    async def _handle_song_finished(self, ctx, error):
        """Handle song finish and play next song"""
        if error:
            logger.error(f"Playback error: {error}")
        
        try:
            # Get the queue manager for the guild
            guild_id = ctx.guild.id
            queue_manager = self.music_bot.get_queue_manager(guild_id)
            
            # Clear current song and mark as not playing
            await queue_manager.clear_current()
                
            # Try to play next song if there is one
            next_song = await queue_manager.get_next()
            if next_song:
                await queue_manager.set_current(next_song)
                
                if not next_song.is_downloaded:
                    success = await self.music_bot.queue_downloader.download_song(next_song)
                    if not success:
                        logger.error(f"Failed to download next song: {next_song.title}")
                        await queue_manager.clear_current()
                        return
                        
                await self.play_next(ctx, next_song)
        except Exception as e:
            logger.error(f"Error handling song finish: {str(e)}", exc_info=True)

    def _playback_finished(self, guild_id: int, error, callback: Optional[Callable] = None):
        """Handle playback finish/cleanup for specific guild"""
        if error:
            logger.error(f"Playback error for guild {guild_id}: {error}")

        if guild_id in self.statuses:
            self.statuses[guild_id].is_playing = False
            self.statuses[guild_id].current_position = 0

        if guild_id in self.progress_tasks:
            self.progress_tasks[guild_id].cancel()

        if callback and callable(callback):
            asyncio.run_coroutine_threadsafe(
                self._run_callback(error, callback),
                self.loop
            )
        else:
            logger.debug(f"No callback provided or callback not callable for guild {guild_id}")

    async def _run_callback(self, error, callback: Callable):
        """Run callback in event loop context"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(error)
            else:
                callback(error)
        except Exception as e:
            logger.error(f"Callback error: {str(e)}", exc_info=True)

    async def _track_progress(self, guild_id: int):
        """Track playback progress for specific guild"""
        try:
            while guild_id in self.statuses and self.statuses[guild_id].is_playing:
                status = self.statuses[guild_id]
                status.current_position = time.time() - status.started_at
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error tracking progress for guild {guild_id}: {e}")

    def pause(self, guild_id: int):
        """Pause playback for specific guild"""
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
            self.voice_clients[guild_id].pause()
            if guild_id in self.statuses:
                self.statuses[guild_id].is_playing = False
            logger.info(f"Paused playback for guild {guild_id}")

    def resume(self, guild_id: int):
        """Resume playback for specific guild"""
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_paused():
            self.voice_clients[guild_id].resume()
            if guild_id in self.statuses:
                status = self.statuses[guild_id]
                status.is_playing = True
                status.started_at = time.time() - status.current_position
            logger.info(f"Resumed playback for guild {guild_id}")

    def stop(self, guild_id: int):
        """Stop playback for specific guild"""
        logger.info(f"Attempting to stop playback for guild {guild_id}")
        
        if guild_id in self.voice_clients and self.voice_clients[guild_id]:
            voice_client = self.voice_clients[guild_id]
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
                logger.info(f"Stopped playback for guild {guild_id}")

        if guild_id in self.statuses:
            self.statuses[guild_id].is_playing = False
            self.statuses[guild_id].current_position = 0

        if guild_id in self.progress_tasks:
            self.progress_tasks[guild_id].cancel()
            
        # Cleanup
        self.voice_clients.pop(guild_id, None)
        self.audio_sources.pop(guild_id, None)
        self.progress_tasks.pop(guild_id, None)

    def get_progress(self, guild_id: int) -> tuple[float, int]:
        """Get current playback position and duration for specific guild"""
        if guild_id not in self.statuses or not self.statuses[guild_id].is_playing:
            return 0, 0
        status = self.statuses[guild_id]
        return status.current_position, status.duration

    def get_progress_string(self, guild_id: int) -> str:
        """Get formatted progress string for specific guild"""
        if guild_id not in self.statuses:
            return "0:00/0:00"
        status = self.statuses[guild_id]
        pos = int(status.current_position)
        dur = status.duration
        return f"{pos//60}:{pos%60:02d}/{dur//60}:{dur%60:02d}"