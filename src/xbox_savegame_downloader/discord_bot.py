from typing import Optional
import discord
import asyncio
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
import httpx
import random
from mega.client import Mega

from .xbox_save_manager import XboxSaveManager
from .common import load_games_collection
from .models import DboxGameResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_FILESIZE_FOR_DISCORD = (8 * 1024 * 1024) # 8MB

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
XBOX_CLIENT_ID = os.getenv("XBOX_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ALLOW_CUSTOM_FETCH = os.getenv("ALLOW_CUSTOM_FETCH")

# MEGA.NZ ACC (optional)
MEGA_NZ_LOGIN = os.getenv("MEGA_NZ_LOGIN")
MEGA_NZ_PASSWD = os.getenv("MEGA_NZ_PASSWD")

if ALLOW_CUSTOM_FETCH:
    logger.info("[NOTE] Custom fetch is enabled via env")

mega = Mega(use_progress_bar=False)

# Initialize bot with required intents
intents = discord.Intents()
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
#intents.members = True  # Required for some interactions
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

async def ensure_mega_logged_in() -> bool:
    if MEGA_NZ_LOGIN and MEGA_NZ_PASSWD:
        if mega.logged_in:
            return True

        try:
            await mega.login(MEGA_NZ_LOGIN, MEGA_NZ_PASSWD)
            logger.info("Refreshed login to MEGA.NZ")
            return True
        except Exception as e:
            logger.exception("Failed logging in to MEGA.NZ account")
    return False

async def download_savedata(interaction: discord.Interaction, scid: str, pfn: str):
    # Download save files
    try:
        dl_context = await xbox_manager.get_titlestorage_context(
            str(interaction.user.id),
            scid,
            pfn,
        )
    except Exception as e:
        logger.error(f"get_titlestorage_context: Failed with error: {e}")
        await interaction.followup.send("❌ Getting authenticated context failed. Did you authenticate successfully?")
        return

    success = True
    try:
        res = await dl_context.download_save_files()
    except httpx.HTTPStatusError as http_ex:
        status_code = http_ex.response.status_code
        if status_code == 404:
            details = f"Savegames for title '{pfn}' not found"
        else:
            details = f"HTTP Code {status_code}"
        logger.error(f"download_save_files: Failure with error: {details}, err: {http_ex}")
        success = False
    except Exception as e:
        details = "Contact an admin for assistance"
        logger.exception(f"download_save_files: Failed with error: {e}")
        success = False

    if not success:
        await interaction.followup.send(f"❌ Downloading saves failed. {details}")
        return

    download_dir, zip_filepath = res
    uploaded_link: Optional[str] = None

    if await ensure_mega_logged_in():
        try:
            await interaction.followup.send(
                content="Just one more moment..."
            )
            logger.info(f"Uploading file {zip_filepath} to MEGA.NZ")
            uploaded = await mega.upload(str(zip_filepath))
            uploaded_link = await mega.get_upload_link(uploaded)
        except Exception as e:
            logger.error(f"Failed uploading to MEGA.NZ, error: {e}")

    if zip_filepath.stat().st_size > MAX_FILESIZE_FOR_DISCORD:
        await interaction.followup.send(
            content=f"⚠️ Zip file is too large to be uploaded to Discord"
        )
        if uploaded_link:
            await interaction.followup.send(
                content=f"Here is a MEGA.NZ link instead: {uploaded_link}"
            )
    else:
        try:
            await interaction.followup.send(
                file=discord.File(zip_filepath),
                content=f"✅ Savegame downloaded successfully, Enjoy!"
            )
        except Exception as e:
            logger.error(f"Failed sending file attachment to discord, error: {e}")

    # Clean up files after sending
    await dl_context.cleanup_files(download_dir)

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
    if MEGA_NZ_LOGIN and MEGA_NZ_PASSWD:
        logger.info("MEGA.NZ credentials were provided, logging in...")
        await ensure_mega_logged_in()

@bot.event
async def on_guild_join(guild):
    """Send a welcome message when the bot joins a new server."""
    try:
        # Find the first channel where the bot can send messages
        welcome_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                welcome_channel = channel
                break
        
        if welcome_channel:
            embed = discord.Embed(
                title="🎮 Xbox Save Manager Bot",
                description="Thanks for adding me to your server! I can help you download your Xbox game saves.",
                color=discord.Color.blue()
            )
            
            command_list = ""
            command_list += "`/authenticate` - Start the Xbox Live authentication process\n"
            command_list += "`/getsave` - Download your Xbox game saves\n"
            if ALLOW_CUSTOM_FETCH:
                command_list += "`/fetchcustom scid:<ServiceConfigurationId> pfn:<PackageFamilyName>` - Fetch saves for arbitrary game\n"
                command_list += "`/search name:<Game Name>` - Search for games\n"
            command_list += "`/help` - Show this help message"

            embed.add_field(
                name="📝 Available Commands",
                value=command_list,
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Important Notes",
                value=(
                    "• You need to authenticate with Xbox Live first using `/authenticate`\n"
                    "• Make sure you've played the game on Xbox and your saves are synced\n"
                    "• The bot will DM you during the authentication process"
                ),
                inline=False
            )
            
            embed.set_footer(text="For support, contact the server administrator")
            
            await welcome_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send welcome message to guild {guild.name}: {e}")

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
        return message.author.id == interaction.user.id and message.channel == dm_channel

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
        await interaction.response.send_message("Please wait a bit...")
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

        await download_savedata(self.view.interaction, game_scid, game_pfn)

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

@bot.tree.command(name="help", description="Show information about the bot and its commands")
async def help_command(interaction: discord.Interaction):
    """Show help information about the bot."""
    embed = discord.Embed(
        title="🎮 Xbox Save Manager Bot Help",
        description="I can help you download your Xbox game saves. Here's how to use me:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="1️⃣ Authentication",
        value=(
            "First, you need to authenticate with Xbox Live:\n"
            "• Use `/authenticate` to start the process\n"
            "• Follow the instructions in your DMs\n"
            "• You only need to do this once"
        ),
        inline=False
    )
    
    embed.add_field(
        name="2️⃣ Downloading Saves",
        value=(
            "To download your game saves:\n"
            "• Use `/getsave` to start the process\n"
            "• Select your game from the dropdown menu\n"
            "• The bot will download and send your saves"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Requirements",
        value=(
            "• You must have played the game on Xbox\n"
            "• Your saves must be synced to Xbox Cloud\n"
            "• You need to complete authentication first"
        ),
        inline=False
    )
    
    embed.add_field(
        name="❓ Need Help?",
        value="If you encounter any issues, please contact the server administrator.",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

if ALLOW_CUSTOM_FETCH:
    @bot.tree.command(name="fetchcustom", description="Download Xbox save for a custom game using SCID and PFN.", )
    async def fetch_custom_command(
        interaction: discord.Interaction,
        scid: str,
        pfn: str
    ):
        """Start the save file download process for a custom game."""
        await interaction.response.defer(thinking=True, ephemeral=False)
        await download_savedata(interaction, scid, pfn)

    @bot.tree.command(name="search", description="Search for Xbox games by name.")
    async def search_command(interaction: discord.Interaction, name: str):
        """Search for Xbox games by name."""
        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://dbox.tools/api/title_ids/",
                    params={
                        "name": name,
                        "system": ["XBOXONE"],
                        "limit": 100,
                        "offset": 0
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("count") == 0 or not data.get("items"):
                    await interaction.followup.send(f"❌ No games found matching '{name}'")
                    return

                # Create an embed with the search results
                embed = discord.Embed(
                    title=f"🔍 Search Results for '{name}'",
                    color=discord.Color.blue()
                )

                for game in data["items"]:
                    game_info = DboxGameResponse.model_validate(game)
                    value = (
                        f"**Title ID:** `{game_info.title_id}`\n"
                        f"**Systems:** {', '.join(game_info.systems)}\n"
                        f"**SCID:** `{game_info.service_config_id}`\n"
                        f"**PFN:** `{game_info.pfn}`"
                    )

                    if game_info.scid and game_info.pfn:
                        value += "\n\nClick the button below to download savedata"

                    embed.add_field(
                        name=game_info.name,
                        value=value,
                        inline=False
                    )

                # Create a view with a button for each game
                view = discord.ui.View()
                for game in data["items"]:
                    game_info = DboxGameResponse.model_validate(game)
                    if not game_info.pfn or not game_info.service_config_id:
                        # Only savegames of titles with PFN/SCID can be downloaded, skip others
                        continue

                    button = discord.ui.Button(
                        label=f"Download saves for {game_info.name}",
                        custom_id=f"{game_info.title_id}_{random.randint(0, 9999)}",
                        style=discord.ButtonStyle.primary
                    )
                    
                    async def button_callback(interaction: discord.Interaction, scid=game_info.service_config_id, pfn=game_info.pfn):
                        # Get the command from the tree
                        command = bot.tree.get_command("fetchcustom")
                        if command:
                            # Create a new interaction context
                            # ctx = await bot.get_application_context(interaction)
                            # Execute the command
                            await command.callback(interaction, scid=scid, pfn=pfn)
                        else:
                            await interaction.response.send_message("❌ Command not found", ephemeral=True)
                    
                    button.callback = button_callback
                    view.add_item(button)

                await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.exception(f"search_command: Failed with error: {e}")
            await interaction.followup.send("❌ Failed to search for games. Please try again later.")

def main():
    if not all([DISCORD_BOT_TOKEN, XBOX_CLIENT_ID, REDIRECT_URI]):
        logger.critical(
            "CRITICAL: Missing env vars. Bot cannot start. "
            "Ensure DISCORD_BOT_TOKEN, XBOX_CLIENT_ID, and REDIRECT_URI are set."
        )
        exit(1)

    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
