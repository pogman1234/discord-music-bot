from fastapi import APIRouter, HTTPException
from ..core.discord_bot import bot
import logging

logger = logging.getLogger("discord-music-bot")

router = APIRouter()

# Example: Endpoint to get the currently playing song
@router.get("/nowplaying")
async def get_now_playing():
    """
    Gets the currently playing song in the Discord bot.
    """
    try:
        music_bot = bot.music_bot
        logger.info("get_now_playing called")

        current_song = music_bot.get_currently_playing()
        logger.info(f"Current song: {current_song}")

        if current_song:
            return {"title": current_song}
        else:
            return {"message": "Nothing is currently playing."}

    except Exception as e:
        logger.error(f"Error in get_now_playing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting now playing: {e}")