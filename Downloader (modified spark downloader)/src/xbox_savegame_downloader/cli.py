import os
import asyncio
import logging
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

from .xbox_save_manager import XboxSaveManager
from .common import load_games_collection

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
XBOX_CLIENT_ID = os.getenv("XBOX_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

async def async_main():
    if not all([XBOX_CLIENT_ID, REDIRECT_URI]):
        logger.critical(
            "CRITICAL: Missing env vars. "
            "Ensure XBOX_CLIENT_ID and REDIRECT_URI are set in .env file."
        )
        return

    games = load_games_collection("games.json")
    games_list = list(games.root.items())

    # Initialize XboxSaveManager
    xbox_manager = XboxSaveManager(
        client_id=XBOX_CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        tokens_file="user_tokens.json",
        download_dir="downloads"
    )

    token_data = xbox_manager.user_tokens_data.root.get("cli_user")

    if not token_data or not token_data.xsts_token or not token_data.xsts_token.is_valid():
        # Generate auth URL
        auth_url = await xbox_manager.generate_auth_url()
        print("\nPlease authenticate with Xbox Live:")
        print(f"1. Open this URL in your browser: {auth_url}")
        print("2. Sign in with your Xbox account")
        print("3. Copy the entire URL from your browser's address bar after being redirected")
        
        # Get auth code from user
        auth_code = input("\nPaste the redirect URL here: ").strip()

        auth_code = parse_qs(urlparse(auth_code).query).get('code', [None])[0]
        
        if not auth_code:
            print("❌ Could not extract code from the URL. Please ensure you copied the entire redirect URL.")
            return

        # Process authentication
        print("\n⏳ Processing authentication...")
        if not await xbox_manager.process_auth_code(auth_code, "cli_user"):
            print("❌ Processing auth code failed.")
            return

        print("✅ Authenticated")

    # Select game version
    print("\nSelect game version:")
    for i, kvp in enumerate(games_list):
        name, _ = kvp
        print(f"{i}. {name}")

# choice was set to 0 manually, as KSP is the only game within this version's games.json
    chosen_game = None
    while True:
        try:
            choice = 0
            chosen_game = games_list[choice]
            break
        except (ValueError, IndexError):
            print(f"Invalid choice. Please enter any of the following: {', '.join([str(i) for i in range(len(games))])}.")

    game_title, game_meta = chosen_game
    print(f"Chosen game: {game_title} -> {game_meta}") 

    # Get Titlestorage context
    dl_context = await xbox_manager.get_titlestorage_context("cli_user", game_meta.scid, game_meta.pfn)

    # Download save files
    print(f"\n⏳ Downloading {game_title} saves...")
    res = await dl_context.download_save_files()
    if not res:
        print("❌ Failed downloading savegames")
        return

    download_dir, zip_filepath = res
    print(f"✅ Save files have been downloaded to: {download_dir}")
    print(f"✅ Zip: {zip_filepath}")
    
    # Ask if user wants to clean up - has been set to "n" manually.
    cleanup = "n"
    if cleanup == 'y':
        await dl_context.cleanup_files(download_dir)
        print("✅ Files cleaned up successfully.")

def main():
    asyncio.run(async_main()) 

if __name__ == "__main__":
    main()
