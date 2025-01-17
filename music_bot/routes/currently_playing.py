from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Optional, Dict

router = APIRouter()

def init_router(bot):
    @router.get("/api/currently-playing")
    async def currently_playing() -> Dict:
        """Get detailed information about the currently playing song"""
        song_info = bot.music_bot.get_current_song()
        
        response = {
            "isPlaying": bot.music_bot.is_playing,
            "currentSong": song_info if song_info else None
        }

        # When song_info is present, it will include:
        # - url: YouTube URL
        # - title: Song title
        # - duration: Song duration
        # - thumbnail: Thumbnail URL
        # - video_id: YouTube video ID
        # - filepath: Local file path
        # - is_downloaded: Download status

        return JSONResponse(content=response)
    
    return router