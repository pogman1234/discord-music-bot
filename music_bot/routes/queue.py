from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

class SongInfo(BaseModel):
    title: str
    url: Optional[str] = None
    duration: Optional[str] = None
    thumbnail: Optional[str] = None

class QueueResponse(BaseModel):
    queue: List[SongInfo]
    current_position: int
    total_songs: int

router = APIRouter(prefix="/api/queue", tags=["queue"])

def init_router(bot):
    @router.get("/", response_model=QueueResponse)
    async def get_queue():
        try:
            queue = bot.music_bot.get_queue()
            current_pos = bot.music_bot.get_current_position()
            
            return QueueResponse(
                queue=[SongInfo(**song) for song in queue],
                current_position=current_pos,
                total_songs=len(queue)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    return router