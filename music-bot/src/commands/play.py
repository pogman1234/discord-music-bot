from discord.ext import commands
import discord
import youtube_dl
import validators

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def play(self, ctx, *, arg):
        """Plays audio from a YouTube URL or search term."""
        print("play command used")  # Debug print
        await ctx.defer()

        if not ctx.author.voice:
            await ctx.followup.send("You are not connected to a voice channel!")
            return

        # Check if the argument is a URL or a search term
        if not validators.url(arg):
            # Search for the song on YouTube
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'default_search': 'auto',
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch:{arg}", download=False)
                    if 'entries' in info:
                        entry = info['entries'][0]
                        url = entry['webpage_url']
                    else:
                        await ctx.followup.send("Could not find any results for your query.")
                        return
                except Exception as e:
                    await ctx.followup.send(f"An error occurred while searching: {e}")
                    return
        else:
            url = arg

        await ctx.followup.send(f"Playing {url}")

        # Add to queue and play
        if self.is_playing(ctx):
            self.bot.music_bot.queue.append(url)
            await ctx.followup.send(f"Added to queue: {url}")
        else:
            await self.bot.music_bot.play_youtube_url(ctx, url)

    def is_playing(self, ctx):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_playing()

async def setup(bot):
    print("loading play cog")  # Debug print
    await bot.add_cog(Play(bot))