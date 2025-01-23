import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import time
import aiohttp
from typing import AsyncGenerator
import os
import json

router = APIRouter()
logger = logging.getLogger(__name__)
_bot = None

async def get_bot_data():
    """Fetches data directly from bot instance"""
    if not _bot:
        logger.error("Bot instance not initialized")
        return None

    try:
        current_song = _bot.music_bot.get_current_song()
        is_playing = _bot.music_bot.is_playing
        
        return {
            "currentSong": current_song,
            "isPlaying": is_playing,
        }
    except Exception as e:
        logger.error(f"Error getting bot data: {e}")
        return None

async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    """Generates the SSE stream."""
    last_state = None
    while True:
        if await request.is_disconnected():
            logger.info("Client disconnected")
            break
            
        bot_data = await get_bot_data()
        if bot_data:
            current_state = {
                "isPlaying": bot_data["isPlaying"],
                "currentSong": bot_data["currentSong"],
                "error": None,
                "timestamp": int(time.time() * 1000),
            }
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
        await asyncio.sleep(1)

@router.get("/sse/currently-playing")
async def sse_endpoint(request: Request):
    """Provides the SSE endpoint."""
    generator = event_stream(request)
    return StreamingResponse(generator, media_type="text/event-stream")

def init_router(bot):
    global _bot
    _bot = bot
    
    @router.get("/api/currently-playing")
    async def get_currently_playing():
        """Get information about the currently playing song"""
        current_song = bot.music_bot.get_current_song()
        is_playing = bot.music_bot.is_playing
        return {
            "currentSong": current_song,
            "isPlaying": is_playing
        }
    
    return router