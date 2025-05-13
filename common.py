from enum import StrEnum
from typing import Dict, Optional
from pydantic import BaseModel, RootModel

class SaveMethod(StrEnum):
    AtomFilename = "atom_filename"
    BlobFilename = "blob_filename"

class GameMetadata(BaseModel):
    title_id: int
    scid: str
    pfn: str
    jsonpath_filter: str
    save_method: SaveMethod

class GameMetadataCollection(RootModel):
    root: Dict[str, GameMetadata]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]
    
    def __setitem__(self, key, val):
        self.root[key] = val
    
    def __len__(self):
        return len(self.root.items())

def load_games_collection(filepath: str) -> GameMetadataCollection:
    """Load user tokens from the tokens file."""
    with open(filepath, 'rt') as f:
        data = f.read()
        return GameMetadataCollection.model_validate_json(data)
