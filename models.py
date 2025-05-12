"""
Titlestorage response models
"""
import os
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class PagingInfo(BaseModel):
    totalItems: int
    continuationToken: Optional[str] = None

class BlobMetadata(BaseModel):
    fileName: str
    displayName: Optional[str] = None
    etag: str
    clientFileTime: datetime
    size: int

    def normalized_filename(self) -> str:
        fn_split = self.fileName.split("/")
        # Get last string after /
        filename = fn_split[len(fn_split) - 1]
        filename = (
            filename
                .replace(",savedgame", "")
                .replace("X", ".")
                .replace("E", "_")
        )

        localpath = os.pathsep.join(fn_split[:len(fn_split) - 2])
        localpath = (
            localpath
                .replace("X", ".")
                .replace("E", "_")
        )

        return os.path.join(localpath, filename)

class BlobsResponse(BaseModel):
    blobs: List[BlobMetadata]
    pagingInfo: PagingInfo

class SavegameAtoms(BaseModel):
    atoms: Dict[str, str]
