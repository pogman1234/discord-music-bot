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
    is_playing: bool = False
    started_at: float = 0
    current_position: float = 0
    duration: int = 0
    volume: float = 0.5

class AudioPlayer:
    def __init__(self, music_bot):
        self.music_bot = music_bot
        self.status = PlaybackStatus()
        self.current_voice_client: Optional[discord.VoiceClient] = None
        self.current_audio_source: Optional[discord.PCMVolumeTransformer] = None
        self.progress_task: Optional[asyncio.Task] = None
        self.loop = asyncio.get_event_loop()
        
        # FFMPEG settings that work well
        self.ffmpeg_options = {
            'options': '-vn -b:a 192k',
            #'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }

    async def play(self, voice_client: discord.VoiceClient, filepath: str, duration: int, 
                  volume: float = 0.5, after_callback: Callable = None) -> bool:
        """
        Start playing an audio file
        
        Args:
            voice_client: Discord voice client to play audio through
            filepath: Path to audio file
            duration: Duration of song in seconds
            volume: Playback volume (0.0-1.0)
            after_callback: Callback to run when song finishes
        """
        try:
            if voice_client.is_playing():
                voice_client.stop()

            self.current_voice_client = voice_client
            self.status = PlaybackStatus(
                is_playing=True,
                started_at=time.time(),
                duration=duration,
                volume=volume
            )

            # Create audio source
            audio_source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    filepath,
                    **self.ffmpeg_options
                ),
                volume=volume
            )
            self.current_audio_source = audio_source

            # Start progress tracking
            self.progress_task = asyncio.create_task(self._track_progress())

            # Play with wrapped callback
            voice_client.play(
                audio_source,
                after=lambda e: self._playback_finished(e, after_callback)
            )
            
            return True

        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            self.status.is_playing = False
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
            # Clear current song and mark as not playing
            if self.music_bot.queue_manager:
                await self.music_bot.queue_manager.clear_current()
                
                # Try to play next song if there is one
                next_song = await self.music_bot.queue_manager.get_next()
                if next_song:
                    await self.music_bot.queue_manager.set_current(next_song)
                    
                    if not next_song.is_downloaded:
                        success = await self.music_bot.queue_downloader.download_song(next_song)
                        if not success:
                            logger.error(f"Failed to download next song: {next_song.title}")
                            await self.music_bot.queue_manager.clear_current()
                            return
                            
                    await self.play_next(ctx, next_song)
            else:
                logger.error("Queue manager not initialized")
        except Exception as e:
            logger.error(f"Error handling song finish: {str(e)}", exc_info=True)

    def _playback_finished(self, error, callback: Optional[Callable] = None):
        """Handle playback finish/cleanup"""
        if error:
            logger.error(f"Playback error: {error}")

        # Reset state
        self.status.is_playing = False
        self.status.current_position = 0
        
        if self.progress_task:
            self.progress_task.cancel()
        
        # Only run callback if it's actually callable
        if callback and callable(callback):
            asyncio.run_coroutine_threadsafe(
                self._run_callback(error, callback), 
                self.loop
            )
        else:
            logger.debug("No callback provided or callback not callable")

    async def _run_callback(self, error, callback: Callable):
        """Run callback in event loop context"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(error)
            else:
                callback(error)
        except Exception as e:
            logger.error(f"Callback error: {str(e)}", exc_info=True)

    async def _track_progress(self):
        """Track playback progress"""
        try:
            while self.status.is_playing:
                self.status.current_position = time.time() - self.status.started_at
                await asyncio.sleep(0.1)  # Update 10 times per second
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error tracking progress: {e}")

    def pause(self):
        """Pause playback"""
        if self.current_voice_client and self.current_voice_client.is_playing():
            self.current_voice_client.pause()
            self.status.is_playing = False

    def resume(self):
        """Resume playback"""
        if self.current_voice_client and self.current_voice_client.is_paused():
            self.current_voice_client.resume()
            self.status.is_playing = True
            self.status.started_at = time.time() - self.status.current_position

    def stop(self):
        """Stop playback"""
        if self.current_voice_client:
            self.current_voice_client.stop()
            self.status.is_playing = False
            self.status.current_position = 0

    def get_progress(self) -> tuple[float, int]:
        """Get current playback position and total duration"""
        if not self.status.is_playing:
            return 0, self.status.duration
        return self.status.current_position, self.status.duration

    def get_progress_string(self) -> str:
        """Get formatted progress string"""
        pos = int(self.status.current_position)
        dur = self.status.duration
        return f"{pos//60}:{pos%60:02d}/{dur//60}:{dur%60:02d}"