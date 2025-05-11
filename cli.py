import os
import asyncio
import logging
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from xbox_save_manager import XboxSaveManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
XBOX_CLIENT_ID = os.getenv("XBOX_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

async def main():
    if not all([XBOX_CLIENT_ID, REDIRECT_URI]):
        logger.critical(
            "CRITICAL: Missing env vars. "
            "Ensure XBOX_CLIENT_ID and REDIRECT_URI are set in .env file."
        )
        return

    # Initialize XboxSaveManager
    xbox_manager = XboxSaveManager(
        client_id=XBOX_CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        tokens_file="user_tokens.json",
        download_dir="downloads"
    )

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
    print("1. Disney Infinity 2.0")
    print("2. Disney Infinity 3.0")
    
    while True:
        choice = input("Enter your choice (1 or 2): ").strip()
        if choice == "1":
            game_version = "2.0"
            break
        elif choice == "2":
            game_version = "3.0"
            break
        print("Invalid choice. Please enter 1 or 2.")

    # Download save files
    print(f"\n⏳ Downloading DI {game_version} saves...")
    zip_filepath = await xbox_manager.download_save_files("cli_user", game_version)
    if not zip_filepath:
        print("❌ Failed downloading savegames")
        return

    print(f"✅ Save files have been downloaded to: {zip_filepath}")
    
    # Ask if user wants to clean up
    cleanup = input("\nDo you want to clean up the downloaded files? (y/n): ").strip().lower()
    if cleanup == 'y':
        download_path = os.path.dirname(zip_filepath)
        await xbox_manager.cleanup_files(zip_filepath, download_path)
        print("✅ Files cleaned up successfully.")


if __name__ == "__main__":
    asyncio.run(main()) 