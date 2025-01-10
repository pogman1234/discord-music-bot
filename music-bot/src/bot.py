import discord
import yt_dlp as youtube_dl
import logging

logger = logging.getLogger('discord')

class MusicBot:
    def __init__(self, bot):
        self.bot = bot
        self.queue = []  # Song queue for each guild
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
            'source_address': '0.0.0.0'  # Bind to ipv4 since ipv6 addresses cause issues sometimes
        }
        self.ffmpeg_options = {
            'options': '-vn',  # No video
        }

    async def play_song(self, ctx, song_info):
        """Plays a song from the queue."""
        voice_client = ctx.voice_client

        if voice_client is None:
            logger.error("Voice client is None in play_song.")
            return

        try:
            # Download the song (you might want to implement a separate download function later)
            with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
                info = ydl.extract_info(song_info['url'], download=True)
                filename = ydl.prepare_filename(info)

            # Play the song
            player = discord.FFmpegPCMAudio(filename, **self.ffmpeg_options)
            voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next_song(ctx)))
            logger.info(f"Playing '{song_info['title']}' in {ctx.guild.name}")

            # Send a message to the text channel
            embed = discord.Embed(title="Now Playing", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.blue())
            embed.set_thumbnail(url=song_info.get('thumbnail'))
            await ctx.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in play_song: {e}")
            await ctx.channel.send("An error occurred while trying to play the song.")

    async def play_next_song(self, ctx):
        """Plays the next song in the queue."""
        if self.queue:
            next_song_info = self.queue.pop(0)
            await self.play_song(ctx, next_song_info)
        else:
            logger.info(f"Queue is empty in {ctx.guild.name}. Disconnecting.")
            if ctx.voice_client:
                await ctx.voice_client.disconnect()

    async def add_to_queue(self, ctx, url):
        """Adds a song to the queue."""
        with youtube_dl.YoutubeDL(self.ytdl_options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                song_info = {
                    'url': url,
                    'title': info.get('title', url),
                    'thumbnail': info.get('thumbnail', None)
                }
                self.queue.append(song_info)
                logger.info(f"Added '{song_info['title']}' to the queue in {ctx.guild.name}")

                if not ctx.voice_client or not ctx.voice_client.is_playing():
                    await self.play_song(ctx, self.queue.pop(0))
                else:
                    # Send a message to the text channel
                    embed = discord.Embed(title="Added to Queue", description=f"[{song_info['title']}]({song_info['url']})", color=discord.Color.green())
                    embed.set_thumbnail(url=song_info.get('thumbnail'))
                    await ctx.channel.send(embed=embed)

            except Exception as e:
                logger.error(f"Error in add_to_queue: {e}")
                await ctx.channel.send("An error occurred while adding the song to the queue.")