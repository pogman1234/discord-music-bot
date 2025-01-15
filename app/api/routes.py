from fastapi import APIRouter, HTTPException, Depends
from ..core.bot import MusicBot  # Import MusicBot
from ..main import bot, get_music_bot  # Import bot from main.py
from fastapi.middleware.cors import CORSMiddleware

router = APIRouter()

@router.get("/nowplaying")
async def get_now_playing(music_bot: MusicBot = Depends(get_music_bot)):
    """
    Gets the currently playing song in the Discord bot.
    """
    try:
        current_song = music_bot.get_currently_playing()
        if current_song:
            return {"title": current_song}
        else:
            return {"message": "Nothing is currently playing."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting now playing: {e}")