"""
Titlestorage response models
"""

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

class BlobsResponse(BaseModel):
    blobs: List[BlobMetadata]
    pagingInfo: PagingInfo

class SavegameAtoms(BaseModel):
    atoms: Dict[str, str]
