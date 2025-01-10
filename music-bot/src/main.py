import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from bot import MusicBot
import logging

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Configure logging
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)  # Set the minimum level of logs to capture
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    bot.music_bot = MusicBot(bot)
    logger.info(f"Bot started and logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

# Test command (directly in main.py)
@bot.command()
async def ping(ctx):
    print("Ping command received!")
    logger.info("Ping command received!")
    await ctx.send("Pong!")

async def load_extensions():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    commands_dir = os.path.join(base_dir, "commands")

    print(f"Attempting to load extensions from: {commands_dir}")  # Debug print
    logger.debug(f"Attempting to load extensions from: {commands_dir}")

    for filename in os.listdir(commands_dir):
        if filename.endswith(".py"):
            module_name = f"commands.{filename[:-3]}"
            print(f"Trying to load: {module_name}")  # Debug print
            logger.debug(f"Trying to load: {module_name}")
            try:
                await bot.load_extension(module_name)
                print(f"Successfully loaded extension: {module_name}")
                logger.info(f"Successfully loaded extension: {module_name}")
            except Exception as e:
                print(f"Failed to load extension {module_name}: {e}")
                logger.error(f"Failed to load extension {module_name}: {e}")
        else:
            print(f"Skipping non-python file: {filename}")  # Debug print
            logger.debug(f"Skipping non-python file: {filename}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        #await ctx.send("Invalid command used.")
        logger.warning(f"Invalid command used in {ctx.guild}: {ctx.message.content}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument.")
        logger.warning(f"Missing argument in {ctx.guild}: {ctx.message.content}")
    else:
        #await ctx.send("An error occurred while processing your command.")
        logger.error(f"An error occurred in {ctx.guild}: {error}")

async def main():
    await load_extensions()
    try:
        await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())