import logging
import requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

_bot = None
_token = None

def get_all_guilds():
    """Fetch guilds from Discord"""
    headers = {"Authorization": f"Bot {_token}"}
    response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    response.raise_for_status()
    return response.json()

def init_router(bot, token):
    global _bot, _token
    _bot = bot
    _token = token
    
    @router.get("/api/guilds")
    async def get_guilds():
        try:
            guilds = get_all_guilds()
            
            # Extract only id and name fields
            filtered_guilds = [{"id": guild["id"], "name": guild["name"]} for guild in guilds]
            
            return JSONResponse(content=filtered_guilds)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch bot guilds: {e}", exc_info=True)
            return JSONResponse(content={"error": "Failed to fetch bot guilds"}, status_code=500)
    
    return router