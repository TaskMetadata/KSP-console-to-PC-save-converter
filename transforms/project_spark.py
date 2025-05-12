import json
import os
from models import BlobMetadata

class GameFileTransform:
    def __init__(self, filepath: str, blob_meta: BlobMetadata):
        self.filepath = filepath
        self.meta = blob_meta

        with open(filepath, "rt") as f:
            self.data = json.load(f)

    def download_filepath(self) -> str:
        return self.data["atoms"]["Data"]

    def save_filepath(self) -> str:
        fn_split = self.meta.fileName.split("/")
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
    
    def can_download(self) -> bool:
        return not self.meta.fileName.endswith(".txt")