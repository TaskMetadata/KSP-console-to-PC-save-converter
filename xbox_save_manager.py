import os
import re
import json
import zipfile
import asyncio
import aiofiles
import logging
import importlib
from datetime import datetime
from typing import Any, List, Optional, Dict, Tuple
from httpx import HTTPStatusError
from pydantic import BaseModel, RootModel

from dummy_cls import GameFileTransformCls
from common import load_games_collection
from models import BlobsResponse
from auth_manager_ex import AuthenticationManagerEx
from xbox.webapi.common.exceptions import AuthenticationException
from xbox.webapi.authentication.models import OAuth2TokenResponse, XAUResponse, XADResponse, XSTSResponse
from xbox.webapi.common.signed_session import SignedSession, RequestSigner

logger = logging.getLogger(__name__)

class DiscordUserXblContext(BaseModel):
    oauth: OAuth2TokenResponse
    device_token: XADResponse
    user_token: XAUResponse
    xsts_token: XSTSResponse
    device_id: str
    signing_key: str

class UserTokenData(RootModel):
    root: Dict[str, DiscordUserXblContext]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]
    
    def __setitem__(self, key, val):
        self.root[key] = val

def get_valid_filename(name: str):
    """Borrowed from the Django project"""
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        raise Exception("Could not derive file name from '%s'" % name)
    return s

class XboxSaveManager:
    def __init__(self, client_id: str, redirect_uri: str, tokens_file: str = "user_tokens.json", download_dir: str = "downloads"):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.tokens_file = tokens_file
        self.download_dir = download_dir
        # Tokens
        self.user_tokens_data: UserTokenData = self.load_user_tokens(self.tokens_file)
        # Gamefile transform functions
        self.transform: Dict[str, GameFileTransformCls] = self.load_transform_cls("games.json")

    @staticmethod
    def load_transform_cls(games_file: str) -> Dict[str, Any]:
        num = 0
        res = {}
        collection = load_games_collection(games_file)
        for game_name, meta in collection.root.items():
            if not meta.get_files_cls:
                continue

            logger.debug(f"Importing get_files_cls for {game_name} ({meta.pfn})")
            # Import respective cls from module
            imported = importlib.import_module(meta.get_files_cls)
            res[meta.pfn] = imported
            num += 1

        logger.info(f"Imported {num} file transform classes")
        return res

    @staticmethod
    def load_user_tokens(tokens_file: str) -> UserTokenData:
        """Load user tokens from the tokens file."""
        if os.path.exists(tokens_file):
            try:
                with open(tokens_file, 'rt') as f:
                    data = f.read()
                    if not data:
                        return UserTokenData({})
                    res = UserTokenData.model_validate_json(data)
                logger.info(f"Loaded {len(res.root.items())} user tokens.")
                return res
            except json.JSONDecodeError:
                logger.error(f"Error decoding {tokens_file}. Starting empty.")
                return UserTokenData({})
        else:
            logger.info(f"{tokens_file} not found. Starting empty.")
            return UserTokenData({})

    def save_user_tokens(self) -> None:
        """Save user tokens to the tokens file."""
        try:
            with open(self.tokens_file, 'wt') as f:
                data = self.user_tokens_data.model_dump_json(indent=2)
                f.write(data)
            logger.info(f"Saved {len(self.user_tokens_data.root.items())} user tokens.")
        except Exception as e:
            logger.error(f"Error saving user tokens: {e}")

    async def generate_auth_url(self) -> str:
        """Generate the Xbox Live authentication URL."""
        async with SignedSession() as session:
            return (
                # No need for signed session here, we are not doing any web requests
                AuthenticationManagerEx(session, self.client_id, None, self.redirect_uri)
                    .generate_authorization_url()
            )

    async def process_auth_code(self, auth_code: str, user_id: str) -> bool:
        """Process the authentication code and store tokens."""
        try:
            async with SignedSession() as session:
                auth_mgr = AuthenticationManagerEx(session, self.client_id, None, self.redirect_uri)
                await auth_mgr.request_tokens(auth_code)

                if not auth_mgr.xsts_token or not auth_mgr.xsts_token.xuid:
                    logger.warning("Authentication failed (XSTS/XUID missing)")
                    return False

                token_data = self._convert_tokens_to_dict(auth_mgr)
                self.user_tokens_data[user_id] = token_data
                self.save_user_tokens()

                gamertag = auth_mgr.xsts_token.gamertag or f"User_{auth_mgr.xsts_token.xuid}"
                logger.info(f"Authenticated user as {gamertag}")
                return True

        except (AuthenticationException, HTTPStatusError) as e:
            error_msg = str(e)
            if isinstance(e, HTTPStatusError) and e.response is not None:
                response_text = e.response.text
                error_msg += f" (Server: {response_text[min(len(response_text), 200)]})"
            logger.error(f"Xbox Authentication Error: {type(e).__name__} - {error_msg}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error: {type(e).__name__} - {e}")
            return False

    def _convert_tokens_to_dict(self, auth_mgr: AuthenticationManagerEx) -> DiscordUserXblContext:
        """Convert authentication tokens to a dictionary format for storage."""
        return DiscordUserXblContext(
            oauth=auth_mgr.oauth,
            device_token=auth_mgr.device_token,
            user_token=auth_mgr.user_token,
            xsts_token=auth_mgr.xsts_token,
            device_id=auth_mgr.device_id,
            signing_key=auth_mgr.session.request_signer.export_signing_key()
        )

    async def get_auth_manager_and_session(self, user_id: str) -> Optional[Tuple[AuthenticationManagerEx, SignedSession]]:
        """Get an authenticated session for a user."""
        if user_id not in self.user_tokens_data:
            logger.info(f"No tokens found for user {user_id}")
            return None

        token_info_dict = self.user_tokens_data[user_id]
        session = SignedSession.from_pem_signing_key(token_info_dict.signing_key)
        try:
            # Construct AuthenticationManager with previously saved values / tokens
            auth_mgr = AuthenticationManagerEx(session, self.client_id, None, self.redirect_uri, device_id=token_info_dict.device_id)
            auth_mgr.oauth = OAuth2TokenResponse.model_validate(token_info_dict.oauth)
            auth_mgr.device_token = XADResponse.model_validate(token_info_dict.device_token)
            auth_mgr.user_token = XAUResponse.model_validate(token_info_dict.user_token)
            auth_mgr.xsts_token = XSTSResponse.model_validate(token_info_dict.xsts_token)

            await auth_mgr.refresh_tokens()

            if not auth_mgr.xsts_token or not auth_mgr.xsts_token.xuid:
                logger.warning(f"After refresh_tokens, XSTS/XUID still missing for {user_id}")
                if user_id in self.user_tokens_data:
                    del self.user_tokens_data[user_id]
                    self.save_user_tokens()
                await session.aclose()
                return None

            logger.info(f"Tokens refreshed for {user_id}. Gamertag: {auth_mgr.xsts_token.gamertag}")

            # Save refreshed tokens
            refreshed_token_data = self._convert_tokens_to_dict(auth_mgr)
            self.user_tokens_data[user_id] = refreshed_token_data
            self.save_user_tokens()

            return auth_mgr, session

        except Exception as e:
            logger.error(f"Error in get_auth_manager_and_session for {user_id}: {e}")
            if user_id in self.user_tokens_data:
                del self.user_tokens_data[user_id]
                self.save_user_tokens()
            await session.aclose()
            # Re-raise exception
            raise

    @staticmethod
    def _titlestorage_common_headers(authorization_header: str, pfn: str):
        return {
            "Authorization": authorization_header,
            "x-xbl-contract-version": "107",
            "x-xbl-pfn": pfn,
            "Accept-Language": "en-US"
        }

    async def _download_blob_list(self, session: SignedSession, authorization_header: str, xuid: str, scid: str, pfn: str) -> BlobsResponse:
        # List saves
        download_url = f"https://titlestorage.xboxlive.com/connectedstorage/users/xuid({xuid})/scids/{scid}"
        headers = self._titlestorage_common_headers(authorization_header, pfn)

        resp = await session.send_signed("GET", download_url, headers=headers)
        resp.raise_for_status()
        blobs_response = BlobsResponse.model_validate_json(resp.content)

        while blobs_response.pagingInfo.continuationToken is not None:
            # There are more items to fetch, indicated by continuationToken
            params = {
                "skipItems": len(blobs_response.blobs),
                "continuationToken": blobs_response.pagingInfo.continuationToken
            }
            resp = await session.send_signed("GET", download_url, headers=headers, params=params)
            tmp = BlobsResponse.model_validate_json(resp.content)
            # Append blobs to initial response object, overwrite pagingInfo with current version
            blobs_response.blobs.append(tmp.blobs)
            blobs_response.pagingInfo = tmp.pagingInfo

        return blobs_response

    async def _download_blob_file(
            self,
            session: SignedSession,
            authorization_header: str,
            xuid: str,
            scid: str,
            pfn: str,
            download_path: str,
            filename: str,
            local_filename: Optional[str] = None
    ) -> str:
        """Returns filepath"""
        # Download files
        logger.debug(f"Downloading file {filename}")
        download_url = f"https://titlestorage.xboxlive.com/connectedstorage/users/xuid({xuid})/scids/{scid}/{filename}"
        headers = self._titlestorage_common_headers(authorization_header, pfn)

        resp = await session.send_signed("GET", download_url, headers=headers)
        resp.raise_for_status()
        contents = await resp.aread()
        if not local_filename:
            # Normalize filename (remove invalid chars)
            local_filename = get_valid_filename(filename)

        filepath = os.path.join(download_path, local_filename)
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(contents)
        return filepath

    async def download_save_files(self, user_id: str, scid: str, pfn: str) -> Optional[str]:
        """Download save files for a specific game version."""
        auth_session_tuple = await self.get_auth_manager_and_session(user_id)
        if not auth_session_tuple:
            logger.warning("Failed to get auth manager and session")
            return None

        auth_mgr, active_session = auth_session_tuple
        xuid = auth_mgr.xsts_token.xuid
        gamertag = auth_mgr.xsts_token.gamertag or f"User_{xuid}"

        request_id = f"{user_id}_{int(datetime.now().timestamp())}"
        download_path = os.path.join(self.download_dir, request_id)
        os.makedirs(download_path, exist_ok=True)
        zip_filename = f"{pfn}_Saves_{gamertag.replace(' ', '_')}_{request_id}.zip"
        zip_filepath = os.path.join(download_path, zip_filename)
        blobs_list_filepath = os.path.join(download_path, "blobs_list.json")
        blobs_filemapping = os.path.join(download_path, "filemap.json")

        logger.info("Downloading list of blobs...")
        blobs_response = await self._download_blob_list(
            active_session,
            auth_mgr.xsts_token.authorization_header_value,
            xuid,
            scid,
            pfn
        )

        # Write out the json response to a file (for debugging and completeness)
        with open(blobs_list_filepath, "wt") as f:
            data = blobs_response.model_dump_json(indent=2)
            f.write(data)

        downloaded_files_paths = await asyncio.gather(
            *(self._download_blob_file(
                active_session,
                auth_mgr.xsts_token.authorization_header_value,
                xuid,
                scid,
                pfn,
                download_path,
                blob.fileName
            ) for blob in blobs_response.blobs)
        )

        if not downloaded_files_paths:
            logger.warning("Failed to download any save files")
            return None

        # Create a mapping of actual filepath and BlobMetadata
        filepath_map = list(zip(downloaded_files_paths, blobs_response.blobs))

        with open(blobs_filemapping, "wt") as f:
            json.dump(f, filepath_map, indent=2)

        # Assemble list of files to download / transform
        to_transform: List[GameFileTransformCls] = []
        transform_cls = self.transform.get(pfn)
        if transform_cls:
            logger.info(f"Title {pfn} requires transformation of blob files")
            for filepath, blob_meta in filepath_map:
                to_transform.append(transform_cls(filepath, blob_meta))

            to_download = [(tt.download_filepath(), tt.save_filepath()) for tt in to_transform if tt.can_download()]
            transformed_downloaded = await asyncio.gather(
                *(self._download_blob_file(
                    active_session,
                    auth_mgr.xsts_token.authorization_header_value,
                    xuid,
                    scid,
                    pfn,
                    download_path,
                    dl_filepath,
                    local_filepath
                ) for (dl_filepath, local_filepath) in to_download)
            )
            logger.info(f"Downloaded {len(transformed_downloaded)} transformed files")

        # Create zip file
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in downloaded_files_paths:
                if os.path.exists(file_path):
                    zf.write(file_path, os.path.basename(file_path))

        if os.path.exists(zip_filepath) and os.path.getsize(zip_filepath) > 0:
            logger.info(f"Successfully downloaded {len(downloaded_files_paths)} files")
        return downloaded_files_paths

    async def cleanup_files(self, zip_filepath: str, download_path: str) -> None:
        """Clean up downloaded files and directories."""
        try:
            if os.path.exists(zip_filepath):
                os.remove(zip_filepath)
                logger.info(f"Cleaned up zip file: {zip_filepath}")

            if os.path.isdir(download_path):
                for file in os.listdir(download_path):
                    file_path = os.path.join(download_path, file)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up downloaded file: {file_path}")
                if not os.listdir(download_path):
                    os.rmdir(download_path)
                    logger.info(f"Cleaned up download directory: {download_path}")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
