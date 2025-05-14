"""
Titlestorage response models
"""
from pathlib import Path
from enum import StrEnum
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

class SavegameBlobType(StrEnum):
    Unknown = "unknown"
    Savedgame = "savedgame"
    Binary = "binary"
    Json = "json"
    Config = "config"

    @staticmethod
    def get_type_for_str(input_str: str) -> "SavegameBlobType":
        for (_, enum_val) in SavegameBlobType._member_map_.items():
            if input_str.endswith(f",{enum_val.value}"):
                return enum_val
        return SavegameBlobType.Unknown

"""
Dbox API
"""

class DboxGameResponse(BaseModel):
    title_id: str
    name: str
    systems: List[str]
    bing_id: Optional[str] = None
    service_config_id: Optional[str] = None
    pfn: Optional[str] = None

"""
Titlestorage models
"""

class PagingInfo(BaseModel):
    totalItems: int
    continuationToken: Optional[str] = None

class BlobMetadata(BaseModel):
    fileName: str
    displayName: Optional[str] = None
    etag: str
    clientFileTime: datetime
    size: int

    def normalized_filepath(self) -> Path:
        filename = (
            self.fileName
                .removeprefix("/")
                .removesuffix(",savedgame")
                .replace("X", ".")
                .replace("E", "_")
        )
        return Path(filename)

    @property
    def blob_type(self) -> SavegameBlobType:
        return SavegameBlobType.get_type_for_str(self.fileName)

class BlobsResponse(BaseModel):
    blobs: List[BlobMetadata]
    pagingInfo: PagingInfo

class SavegameAtoms(BaseModel):
    atoms: Dict[str, str]
