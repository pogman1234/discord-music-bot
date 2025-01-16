from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

def init_router(bot):
    @router.get("/api/currently-playing")
    async def currently_playing():
        """Get information about the currently playing song"""
        song_info = bot.music_bot.get_currently_playing()
        return JSONResponse(content={"song": song_info})
    
    return router