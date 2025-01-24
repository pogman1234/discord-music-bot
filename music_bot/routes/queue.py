import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import time
from typing import AsyncGenerator
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

_bot = None

async def get_queue_data():
    """Fetches queue data directly from bot instance"""
    if not _bot:
        logger.error("Bot instance not initialized")
        return None

    try:
        queue_info = _bot.music_bot.get_queue_info()  # Use the new method
        return {
            "queue": queue_info
        }
    except Exception as e:
        logger.error(f"Error getting queue data: {e}")
        return None

async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    """Generates the SSE stream for queue updates."""
    last_state = None
    while True:
        if await request.is_disconnected():
            logger.info("Client disconnected from queue stream")
            break
            
        queue_data = await get_queue_data()
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
    
    @router.get("/api/queue")
    async def get_queue():
        """Get information about all songs in the queue"""
        queue_info = bot.music_bot.get_queue_info()
        return JSONResponse(content={"queue": queue_info})
    
    @router.get("/sse/queue")
    async def sse_endpoint(request: Request):
        """Provides the SSE endpoint for queue updates."""
        generator = event_stream(request)
        return StreamingResponse(generator, media_type="text/event-stream")
        
    return router