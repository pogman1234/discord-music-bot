from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
import requests
import logging
import os
from typing import Dict, List, Optional
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DISCORD_API_URL = "https://discord.com/api/v10"
BOT_TOKEN = None
_bot = None

class DiscordOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = "identify guilds"
        self.sessions: Dict[str, Dict] = {}

    def get_oauth_url(self) -> str:
        """Generate OAuth2 URL for Discord login"""
        encoded_redirect_uri = urllib.parse.quote(self.redirect_uri, safe='')
        encoded_scope = urllib.parse.quote(self.scope, safe='')
        oauth_url = f"{DISCORD_API_URL}/oauth2/authorize?client_id={self.client_id}&redirect_uri={encoded_redirect_uri}&response_type=code&scope={encoded_scope}"
        logger.debug(f"Generated OAuth URL: {oauth_url}")
        return oauth_url

    async def exchange_code(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        logger.debug(f"Exchanging code with data: {data}")
        
        try:
            response = requests.post(f'{DISCORD_API_URL}/oauth2/token', data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {e}", exc_info=True)
            return None

    async def get_user_data(self, access_token: str) -> Optional[Dict]:
        """Get user data from Discord"""
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f'{DISCORD_API_URL}/users/@me', headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user data: {e}", exc_info=True)
            return None

    async def get_user_guilds(self, access_token: str) -> List[Dict]:
        """Get user's guilds from Discord"""
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f'{DISCORD_API_URL}/users/@me/guilds', headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user guilds: {e}", exc_info=True)
            return []

def init_router(bot, token):
    oauth = DiscordOAuth(
        client_id=os.getenv("DISCORD_CLIENT_ID"),
        client_secret=os.getenv("DISCORD_CLIENT_SECRET"),
        redirect_uri=os.getenv("DISCORD_REDIRECT_URI")
    )

    @router.get("/auth/discord/login")
    async def discord_login():
        """Initialize Discord OAuth2 flow"""
        return RedirectResponse(url=oauth.get_oauth_url())

    @router.get("/auth/discord/callback")
    async def discord_callback(code: str, response: Response):
        """Handle Discord OAuth2 callback"""
        try:
            token_data = await oauth.exchange_code(code)
            if not token_data:
                return JSONResponse(content={"error": "Failed to exchange code"}, status_code=400)

            user_data = await oauth.get_user_data(token_data['access_token'])
            if not user_data:
                return JSONResponse(content={"error": "Failed to get user data"}, status_code=400)

            user_guilds = await oauth.get_user_guilds(token_data['access_token'])
            bot_guilds = get_bot_guilds(token)
            common_guilds = filter_common_guilds(user_guilds, bot_guilds)

            session_id = create_session(oauth, user_data, token_data)
            response.set_cookie(key="session_id", value=session_id, httponly=True, secure=True)

            return JSONResponse(content={
                "user": user_data,
                "guilds": common_guilds
            })

        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)
            return JSONResponse(content={"error": "Authentication failed"}, status_code=500)

    @router.get("/api/me/guilds")
    async def get_user_guilds_endpoint(request: Request):
        """Get guilds where both user and bot are present"""
        session_id = request.cookies.get("session_id")
        if not session_id or session_id not in oauth.sessions:
            return JSONResponse(content={"error": "Unauthorized"}, status_code=401)

        session = oauth.sessions[session_id]
        user_guilds = await oauth.get_user_guilds(session['access_token'])
        bot_guilds = get_bot_guilds(token)
        common_guilds = filter_common_guilds(user_guilds, bot_guilds)

        return JSONResponse(content=common_guilds)

    return router

def get_bot_guilds(token: str) -> List[Dict]:
    """Get bot's guilds using bot token"""
    headers = {"Authorization": f"Bot {token}"}
    try:
        response = requests.get(f"{DISCORD_API_URL}/users/@me/guilds", headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get bot guilds: {e}", exc_info=True)
        return []

def filter_common_guilds(user_guilds: List[Dict], bot_guilds: List[Dict]) -> List[Dict]:
    """Filter guilds where both user and bot are present"""
    bot_guild_ids = {g['id'] for g in bot_guilds}
    return [
        {"id": guild["id"], "name": guild["name"]}
        for guild in user_guilds
        if guild["id"] in bot_guild_ids
    ]

def create_session(oauth: DiscordOAuth, user_data: Dict, token_data: Dict) -> str:
    """Create a new session for the user"""
    import uuid
    session_id = str(uuid.uuid4())
    oauth.sessions[session_id] = {
        "user": user_data,
        "access_token": token_data["access_token"]
    }
    return session_id