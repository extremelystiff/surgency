# bot.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import asyncpg # Import asyncpg here as well

# --- Logging Setup ---
# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DISCORD_TOKEN:
    log.critical("DISCORD_TOKEN environment variable not set!")
    exit()
if not DATABASE_URL:
    log.critical("DATABASE_URL environment variable not set!")
    exit() # Or handle differently if DB is optional for some startup parts

INITIAL_EXTENSIONS = [
    "cogs.combat"
]
# --- Bot Initialization ---
# Define necessary intents. Member intent is crucial for getting user info.
intents = discord.Intents.default()
intents.members = True # Required to get member objects, display names, etc.
# intents.message_content = True # Not strictly needed for slash commands, but enable if you add text commands later

bot = commands.Bot(command_prefix="!", intents=intents) # Prefix is fallback, primarily using slash commands
bot.db_pool = None # Initialize db_pool attribute

# --- Database Connection Pool ---
async def create_db_pool():
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        log.info("Successfully connected to PostgreSQL database.")
        # Store the pool in the bot instance for easy access in cogs
        bot.db_pool = pool
        # Run DB setup (create tables if they don't exist)
        from utils import database as db_utils # Import late to avoid circular deps
        await db_utils.setup_db(pool)

    except Exception as e:
        log.critical(f"Failed to connect to database: {e}", exc_info=True)
        # Decide how to handle DB connection failure - maybe the bot shouldn't start?
        # For now, we'll let it start but commands needing DB will fail.
        bot.db_pool = None # Indicate pool is not available


@bot.event
async def on_ready():
    """Event handler for when the bot logs in and is ready."""
    log.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    log.info('------')
    # Connect to DB *before* loading cogs that might need it
    if not bot.db_pool: # Avoid creating pool multiple times on reconnect
         await create_db_pool()

    # Load cogs AFTER the bot is ready and DB pool is potentially available
    await load_extensions() # Await the helper function

    print(f"Bot is ready and connected to {len(bot.guilds)} guilds.")
    await bot.change_presence(activity=discord.Game(name="Insurgency: Sandstorm | /attack"))


# --- Load Cogs ---
# Load the combat cog automatically

async def load_extensions():
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension) # Use await here
            log.info(f"Successfully loaded extension '{extension}'")
        except Exception as e:
            log.error(f"Failed to load extension '{extension}': {e}", exc_info=True)

# --- Run the Bot ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

# --- Cleanup (Optional but recommended) ---
# async def close_db_pool():
#     if hasattr(bot, 'db_pool') and bot.db_pool:
#         await bot.db_pool.close()
#         log.info("Database connection pool closed.")

# Consider using asyncio.run or handling cleanup signals if needed
# For simple Railway deployment, this might be sufficient
