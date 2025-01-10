import youtube_dl
import discord

class MusicBot:
    def __init__(self, bot):
        self.bot = bot
        self.queue = []  # Initialize the queue here
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
        }

        self.ffmpeg_options = {
            'options': '-vn'
        }

    async def play_youtube_url(self, ctx, url):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if voice_client is None:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()

        # Download the song
        with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            except Exception as e:
                print(f"Error downloading audio: {e}")
                return

        # Create a StreamPlayer to handle playback and queue
        player = discord.FFmpegPCMAudio(executable="ffmpeg", source=filename)

        # Add an after callback to play the next song or cleanup
        def after_playing(err):
            if err:
                print(f'Player error: {err}')
            else:
                if self.queue:
                    next_song_url = self.queue.pop(0)
                    coro = self.play_youtube_url(ctx, next_song_url)
                    fut = discord.run_coroutine_threadsafe(coro, self.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error while playing next song: {e}")
                else:
                    # Cleanup after playback if queue is empty
                    coro = voice_client.disconnect()
                    fut = discord.run_coroutine_threadsafe(coro, self.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error while disconnecting: {e}")
            try:
                os.remove(filename)  # Remove the downloaded file
            except Exception as e:
                print(f"Error removing file: {e}")

        voice_client.play(player, after=after_playing)