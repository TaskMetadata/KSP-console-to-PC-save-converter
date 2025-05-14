import collections
import os
import re
import json
import zipfile
import asyncio
import aiofiles
import logging
import shutil
import jsonpath_ng
from pathlib import Path
from datetime import datetime
from typing import Any, Iterable, List, Optional, Dict, Tuple
from httpx import HTTPStatusError
from pydantic import BaseModel, RootModel

from xbox.webapi.common.exceptions import AuthenticationException
from xbox.webapi.authentication.models import OAuth2TokenResponse, XAUResponse, XADResponse, XSTSResponse
from xbox.webapi.common.signed_session import SignedSession, RequestSigner

from .common import GameMetadata, GameMetadataCollection, SaveMethod, load_games_collection
from .models import BlobsResponse
from .auth_manager_ex import AuthenticationManagerEx

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

class TitleStorageContext:
    def __init__(
        self,
        user_id: str,
        session: SignedSession,
        auth_mgr_ex: AuthenticationManagerEx,
        pfn: str,
        scid: str,
        jsonpath_expr: jsonpath_ng.JSONPath,
        save_method: SaveMethod,
        download_dir_root: Path
    ):
        self.user_id = user_id
        self.session = session
        self.xtoken = auth_mgr_ex.xsts_token
        self.auth_header_value = self.xtoken.authorization_header_value
        self.xuid = self.xtoken.xuid
        self.gamertag = self.xtoken.gamertag or f"User_{self.xuid}"
        self.pfn = pfn
        self.scid = scid
        self.jsonpath_expr = jsonpath_expr
        self.save_method = save_method
        self.download_dir_root = download_dir_root

    @property
    def common_headers(self) -> Dict[str, Any]:
        return {
            "Authorization": self.auth_header_value,
            "x-xbl-contract-version": "107",
            "x-xbl-pfn": self.pfn,
            "Accept-Language": "en-US"
        }

    async def _download_blob_list(self) -> BlobsResponse:
        # List saves
        download_url = f"https://titlestorage.xboxlive.com/connectedstorage/users/xuid({self.xuid})/scids/{self.scid}"

        resp = await self.session.send_signed("GET", download_url, headers=self.common_headers)
        resp.raise_for_status()
        blobs_response = BlobsResponse.model_validate_json(resp.content)

        while blobs_response.pagingInfo.continuationToken is not None:
            # There are more items to fetch, indicated by continuationToken
            params = {
                "skipItems": len(blobs_response.blobs),
                "continuationToken": blobs_response.pagingInfo.continuationToken
            }
            resp = await self.session.send_signed("GET", download_url, headers=self.common_headers, params=params)
            tmp = BlobsResponse.model_validate_json(resp.content)
            # Append blobs to initial response object, overwrite pagingInfo with current version
            blobs_response.blobs.extend(tmp.blobs)
            blobs_response.pagingInfo = tmp.pagingInfo

        return blobs_response

    async def _download_blob_file(
        self,
        filename: str,
        target_localpath: Path,
    ) -> Path:
        """Returns filepath"""
        # Download files
        logger.debug(f"Downloading file {filename}")
        download_url = f"https://titlestorage.xboxlive.com/connectedstorage/users/xuid({self.xuid})/scids/{self.scid}/{filename}"
        resp = await self.session.send_signed("GET", download_url, headers=self.common_headers)
        resp.raise_for_status()
        contents = await resp.aread()

        if not target_localpath.parent.exists():
            target_localpath.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(target_localpath, 'wb') as f:
            await f.write(contents)
        return target_localpath

    async def download_save_files(self) -> Optional[Tuple[Path, Path]]:
        """
        Download save files for a specific game version.
        
        Returns:
            tuple of (download_dir, zip_filename)
        """

        # Create unique dir/filenames for this invocation
        request_id = f"{self.user_id}_{int(datetime.now().timestamp())}"
        zip_filename = f"{self.pfn}_Saves_{self.gamertag.replace(' ', '_')}_{request_id}.zip"
        download_dir = self.download_dir_root.joinpath(request_id)
        zip_filepath = download_dir.joinpath(zip_filename)

        metadata_dl_path = download_dir.joinpath("_meta")
        # also creates the parent `download_path`
        metadata_dl_path.mkdir(parents=True, exist_ok=True)
        
        """
        1. Download metadata (List of blobs)
        """
        logger.info("Downloading list of blobs...")
        blobs_response = await self._download_blob_list()

        # Write out the json response to a file (for debugging and completeness)
        blobs_filepath = metadata_dl_path.joinpath("blobs_list.json")
        with open(blobs_filepath, "wt") as f:
            data = blobs_response.model_dump_json(indent=2)
            f.write(data)

        logger.info(f"Downloaded blob-metadata with {len(blobs_response.blobs)} entries")

        """
        2. Download metadata (List of available atoms for each blob)
        """
        # Create list of atom metadata to download: remote filename and their local filepath
        to_download: List[Tuple[str, Path]] = []
        for blob in blobs_response.blobs:
            normalized_filepath = blob.normalized_filepath()
            localpath = (
                metadata_dl_path
                    .joinpath(normalized_filepath.parent, normalized_filepath.name + ".meta.json")
            )
            to_download.append((blob.fileName, localpath))

        downloaded_metadata_files = await asyncio.gather(
            *(self._download_blob_file(remote_filename, local_filepath)
                for (remote_filename, local_filepath) in to_download)
        )

        if not downloaded_metadata_files:
            logger.warning("Failed to download any atom-metadata files")
            return None

        logger.info(f"Downloaded {len(downloaded_metadata_files)} atom-metadata files")

        """
        3. Download binaries (Actual atom binaries, filtered to grab only non-metadata ones)

        NOTE: There are atoms for binary files and ones for timestamps and other metadata.
              We only care about the binary files, returned by the jsonpath-filter!
        """
        # Create a mapping of actual filepath and BlobMetadata
        filepath_map = list(zip(downloaded_metadata_files, blobs_response.blobs))

        #with open(blobs_filemapping, "wt") as f:
        #    json.dump(f, filepath_map, indent=2)

        # Assemble list of files to download / transform
        to_download.clear()

        for filepath, blob_meta in filepath_map:
            with open(filepath, "rt") as f:
                data = json.load(f)
            res: Iterable[jsonpath_ng.DatumInContext] = self.jsonpath_expr.find(data)

            if not len(res):
                logger.error(f"Failed parsing file {filepath} with filter: {self.jsonpath_expr}")
                continue

            normalized_filename = blob_meta.normalized_filepath()
            
            if self.save_method == SaveMethod.AtomFilename:
                # Use the atom's key as filename for saving locally
                for a in res:
                    local_filename = str(a.path)
                    remote_filename = a.value
                    local_filepath = download_dir.joinpath(normalized_filename, local_filename)
                    logger.debug(f"Adding {remote_filename} -> {local_filepath} to queue")
                    to_download.append((remote_filename, local_filepath))
            
            elif self.save_method == SaveMethod.BlobFilename:
                # Use the fileName from BlobMetadata for saving locally
                assert len(res) == 1, "Save-method 'BlobFilename' only expects a single remote filepath!"
                remote_filename = res[0].value
                local_filepath = download_dir.joinpath(normalized_filename)
                to_download.append((remote_filename, local_filepath))
            else:
                raise Exception(f"Unhandled save-method: {self.save_method}")

        downloaded_binary_files = await asyncio.gather(
            *(self._download_blob_file(remote_filename, local_filepath)
                for (remote_filename, local_filepath) in to_download)
        )

        logger.info(f"Downloaded {len(downloaded_binary_files)} binary savedata files")

        downloaded_files = downloaded_metadata_files
        downloaded_files.extend(downloaded_binary_files)
        downloaded_files.append(blobs_filepath)

        """
        Zip the files up 
        """
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in downloaded_files:
                if file_path.exists():
                    zf.write(file_path, file_path.relative_to(download_dir))

        if zip_filepath.exists() and zip_filepath.stat().st_size > 0:
            logger.info(f"Successfully downloaded a total of {len(downloaded_files)} files")

        return (download_dir, zip_filepath)

    @staticmethod
    async def cleanup_files(download_dir: Path) -> None:
        """Clean up downloaded files and directories."""
        try:
            if download_dir.is_dir():
                shutil.rmtree(download_dir)
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

class XboxSaveManager:
    def __init__(self, client_id: str, redirect_uri: str, tokens_file: str = "user_tokens.json", download_dir: str = "downloads"):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.tokens_file = tokens_file
        self.download_dir = Path(download_dir)
        # Tokens
        self.user_tokens_data = self.load_user_tokens(self.tokens_file)
        self.games_meta = self.load_game_meta_dict("games.json")
        # Gamefile transform functions
        self.jsonpath_exprs = self.load_jsonpath_filters(self.games_meta)

    @staticmethod
    def load_game_meta_dict(filepath: str) -> Dict[str, GameMetadata]:
        res = load_games_collection(filepath)
        # Transform into a dict of PFN -> GameMetadata
        return {metadata.pfn: metadata for (_, metadata) in res.root.items()}

    @staticmethod
    def load_jsonpath_filters(collection: GameMetadataCollection) -> Dict[str, jsonpath_ng.JSONPath]:
        res = {}
        for game_name, meta in collection.items():
            logger.debug(f"Importing jsonpath_filter for {game_name} ({meta.pfn})")
            # Prepare jsonpath expressions
            res[meta.pfn] = jsonpath_ng.parse(meta.jsonpath_filter)

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

    async def get_titlestorage_context(self, user_id: str, scid: str, pfn: str) -> TitleStorageContext:
        auth_session_tuple = await self.get_auth_manager_and_session(user_id)
        if not auth_session_tuple:
            raise Exception("Failed to get auth manager and session")

        auth_mgr, session = auth_session_tuple
        if pfn in self.games_meta:
            # Title configured via games.json
            save_method = self.games_meta.get(pfn).save_method
            jsonpath_expr = self.jsonpath_exprs.get(pfn)
        else:
            logger.warning("Using default values, as game was not configured via games.json")
            save_method = SaveMethod.AtomFilename
            jsonpath_expr = jsonpath_ng.parse("atoms.*")

        return TitleStorageContext(
            user_id=user_id,
            session=session,
            auth_mgr_ex=auth_mgr,
            pfn=pfn,
            scid=scid,
            jsonpath_expr=jsonpath_expr,
            save_method=save_method,
            download_dir_root=self.download_dir
        )
