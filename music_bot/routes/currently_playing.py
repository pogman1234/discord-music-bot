from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import logging
import json
import asyncio
from typing import Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter()
_bot = None

async def get_currently_playing_data(guild_id: int) -> Dict:
    """Get current playback data for a specific guild"""
    try:
        queue_manager = _bot.music_bot.get_queue_manager(guild_id)
        current_song = queue_manager.get_currently_playing()
        
        if not current_song:
            return {
                "guild_id": guild_id,
                "is_playing": False,
                "current_song": None,
                "progress": "0:00/0:00",
                "position": 0,
                "duration": 0
            }

        # Get progress with guild_id
        current_position, duration = _bot.music_bot.audio_player.get_progress(guild_id)
        progress = _bot.music_bot.audio_player.get_progress_string(guild_id)

        return {
            "guild_id": guild_id,
            "is_playing": queue_manager.is_playing,
            "current_song": {
                "id": current_song.id,
                "title": current_song.title,
                "duration": current_song.duration,
                "thumbnail": current_song.thumbnail,
                "webpage_url": current_song.webpage_url
            },
            "progress": progress,
            "position": current_position,
            "duration": duration
        }
    except Exception as e:
        logger.error(f"Error getting currently playing data for guild {guild_id}: {e}", exc_info=True)
        raise

async def event_stream(request: Request, guild_id: int):
    """Generate SSE events for currently playing updates"""
    last_state: Optional[Dict] = None
    
    while True:
        if await request.is_disconnected():
            logger.info(f"Client disconnected from SSE stream for guild {guild_id}")
            break
            
        try:
            current_state = await get_currently_playing_data(guild_id)
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
        except Exception as e:
            logger.error(f"Error in SSE stream for guild {guild_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break
            
        await asyncio.sleep(1)

def init_router(bot):
    global _bot
    _bot = bot
    
    @router.get("/api/currently_playing/{guild_id}")
    async def get_currently_playing(guild_id: int):
        """Get information about the currently playing song for a specific guild"""
        try:
            logger.info(f"Getting currently playing data for guild {guild_id}")
            data = await get_currently_playing_data(guild_id)
            return JSONResponse(content=data)
        except Exception as e:
            logger.error(f"Error getting currently playing data for guild {guild_id}: {e}", exc_info=True)
            return JSONResponse(content={"error": str(e)}, status_code=500)
    
    @router.get("/sse/currently_playing/{guild_id}")
    async def sse_endpoint(request: Request, guild_id: int):
        """Provides the SSE endpoint for currently playing updates for a specific guild."""
        return StreamingResponse(
            event_stream(request, guild_id),
            media_type="text/event-stream"
        )
        
    return router