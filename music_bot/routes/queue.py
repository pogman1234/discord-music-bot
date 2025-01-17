from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

def init_router(bot):
    @router.get("/api/queue")
    async def get_queue():
        """Get information about all songs in the queue"""
        queue_info = bot.music_bot.get_queue_info()
        return JSONResponse(content={"queue": queue_info})
        
    return router