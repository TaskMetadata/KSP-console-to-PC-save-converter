from typing import Dict, List, Optional
from pydantic import BaseModel, RootModel

class GameMetadata(BaseModel):
    title_id: int
    scid: str
    pfn: str
    get_files_cls: Optional[str] = None

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
