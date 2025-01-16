from fastapi import APIRouter, HTTPException
from ..core.bot import MusicBot
from ..core.discord_bot import bot
import discord

router = APIRouter()

# Example: Endpoint to get the currently playing song
@router.get("/nowplaying")
async def get_now_playing():
    """
    Gets the currently playing song in the Discord bot.
    """
    music_bot = bot.music_bot
    try:
        current_song = music_bot.get_currently_playing()
        if current_song:
            return {"title": current_song}
        else:
            return {"message": "Nothing is currently playing."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting now playing: {e}")