import discord
import asyncio
# from discord import app_commands
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

from xbox_save_manager import XboxSaveManager
from common import load_games_collection

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
XBOX_CLIENT_ID = os.getenv("XBOX_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize XboxSaveManager
xbox_manager = XboxSaveManager(
    client_id=XBOX_CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    tokens_file="user_tokens.json",
    download_dir="downloads"
)

games = load_games_collection("games.json")
games_list = list(games.root.items())

@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")
    logger.info("------")

@bot.tree.command(name="authenticate")
async def authenticate_command(interaction: discord.Interaction):
    """Start the Xbox Live authentication process."""
    auth_url = await xbox_manager.generate_auth_url()
    logger.info(f"Generated authorization URL: {auth_url}")

    try:
        dm_channel = await interaction.user.create_dm()
        await dm_channel.send(
            "Please authenticate with Xbox Live:\n"
            f"1. Click: {auth_url}\n"
            "2. Sign in.\n"
            "3. Copy entire final URL.\n"
            "4. Paste here."
        )
        await interaction.response.send_message("📬 Check DMs!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Couldn't DM. Enable DMs.", ephemeral=True)
        return

    def check_dm(message: discord.Message):
        return message.author.id == interaction.user.id and message.guild is None

    try:
        await dm_channel.send("Waiting for redirect URL...")
        response_message = await bot.wait_for("message", check=check_dm, timeout=300)
    except asyncio.TimeoutError:
        await dm_channel.send("⏰ Auth timed out. Try `/authenticate` again.")
        return

    redirected_url = response_message.content.strip()
    auth_code = parse_qs(urlparse(redirected_url).query).get('code', [None])[0]
    if not auth_code:
        await dm_channel.send(
            "❌ Could not extract code from the URL. "
            "Please ensure you copied the *entire* redirect URL after signing in. Try again."
        )
        return

    await dm_channel.send("⏳ Processing authentication...")

    try:
        success = await xbox_manager.process_auth_code(auth_code, str(interaction.user.id))
    except Exception as e:
        logger.exception(f"process_auth_code: Failed with error: {e}")
        success = False

    if not success:
        await dm_channel.send(f"❌ Failed to process authentication. Contact an admin for assistance.")
        return

    await dm_channel.send("✅ Success! You can now use `/getsave`.")


class GameVersionSelectView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, timeout=180):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.game_version = None
        self.add_item(GameVersionSelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.interaction.edit_original_response(
                content="Timed out. Use `/getsave` again.",
                view=self
            )
        except discord.NotFound:
            pass
        except Exception as e:
            logger.warning(f"Error editing on timeout: {e}")

class GameVersionSelect(discord.ui.Select):
    def __init__(self):

        options = []

        for game in games_list:
            game_name, _ = game
            option = discord.SelectOption(
                label=game_name,
                value=game_name,
                description=f"Download {game_name} savedata"
            )
            options.append(option)
        super().__init__(
            placeholder="Select Game Version...",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=False)
        game_meta = games[self.values[0]]
        game_scid = game_meta.scid
        game_pfn = game_meta.pfn

        # Disable the select menu after selection
        for item in self.view.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        try:
            await self.view.interaction.edit_original_response(view=self.view)
        except Exception as e:
            logger.warning(f"Error disabling select menu in view: {e}")

        # Download save files
        try:
            dl_context = await xbox_manager.get_titlestorage_context(
                str(self.view.interaction.user.id),
                game_scid,
                game_pfn,
            )
        except Exception as e:
            logger.exception(f"get_titlestorage_context: Failed with error: {e}")
            await self.view.interaction.followup.send("❌ Getting authenticated context failed. Did you authentica successfully?")
            return

        success = True
        try:
            res = await dl_context.download_save_files()
        except Exception as e:
            logger.exception(f"download_save_files: Failed with error: {e}")
            success = False

        if not res or not success:
            await self.view.interaction.followup.send("❌ Downloading saves failed. Contact an admin for assistance.")
            return

        download_dir, zip_filepath = res

        try:
            await self.view.interaction.followup.send(
                file=discord.File(zip_filepath),
                content=f"✅ Savegame downlaoded successfully, Enjoy!"
            )
        finally:
            # Clean up files after sending
            await dl_context.cleanup_files(download_dir)


@bot.tree.command(name="getsave", description="Download Xbox save.")
async def get_save_command(interaction: discord.Interaction):
    """Start the save file download process."""
    view = GameVersionSelectView(interaction=interaction)
    await interaction.response.send_message(
        "**Disclaimer & Instructions:**\n"
        "1. Downloads save file from Xbox Cloud.\n"
        "2. Ensure game played on Xbox & data synced.\n"
        "3. Requires auth via `/authenticate`.\n"
        "4. Select game version below.\n\n"
        "*(Note: This attempts to access game saves via Xbox Live APIs. "
        "Success depends on API availability and whether saves are stored in a standard location.)*",
        view=view,
        ephemeral=False
    )

if __name__ == "__main__":
    if not all([DISCORD_BOT_TOKEN, XBOX_CLIENT_ID, REDIRECT_URI]):
        logger.critical(
            "CRITICAL: Missing env vars. Bot cannot start. "
            "Ensure DISCORD_BOT_TOKEN, XBOX_CLIENT_ID, and REDIRECT_URI are set."
        )
        exit(1)

    bot.run(DISCORD_BOT_TOKEN) 