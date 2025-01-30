import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import time
from typing import AsyncGenerator
import json

logger = logging.getLogger(__name__)
router = APIRouter()

_bot = None

async def get_queue_data(guild_id: int):
    """Fetches queue data directly from bot instance for a specific guild"""
    if not _bot:
        logger.error("Bot instance not initialized")
        return None

    try:
        queue_manager = _bot.music_bot.get_queue_manager(guild_id)
        queue_info = queue_manager.get_queue_info()
        return {
            "queue": queue_info
        }
    except Exception as e:
        logger.error(f"Error getting queue data for guild {guild_id}: {e}")
        return None

async def event_stream(request: Request, guild_id: int) -> AsyncGenerator[str, None]:
    """Generates the SSE stream for queue updates for a specific guild."""
    last_state = None
    while True:
        if await request.is_disconnected():
            logger.info(f"Client disconnected from queue stream for guild {guild_id}")
            break
            
        queue_data = await get_queue_data(guild_id)
        if queue_data:
            current_state = {
                "queue": queue_data["queue"],
                "error": None,
                "timestamp": int(time.time() * 1000)
            }
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
        await asyncio.sleep(1)

def init_router(bot):
    global _bot
    _bot = bot
    
    @router.get("/api/queue/{guild_id}")
    async def get_queue(guild_id: int):
        """Get information about all songs in the queue for a specific guild"""
        queue_data = await get_queue_data(guild_id)
        if queue_data:
            return JSONResponse(content=queue_data)
        return JSONResponse(content={"error": "Failed to get queue data"}, status_code=500)
    
    @router.get("/sse/queue/{guild_id}")
    async def sse_endpoint(request: Request, guild_id: int):
        """Provides the SSE endpoint for queue updates for a specific guild."""
        generator = event_stream(request, guild_id)
        return StreamingResponse(generator, media_type="text/event-stream")
        
    return router