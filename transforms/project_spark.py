from models import BlobMetadata


class GameFileTransform:
    def __init__(self, filepath: str, blob_meta: BlobMetadata):
        self.filepath = filepath
        self.meta = blob_meta

    def download_filepath(self) -> str:
        return self.meta.fileName

    def save_filepath(self) -> str:
        raise NotImplementedError()
    
    def can_download(self) -> bool:
        return not self.meta.fileName.endswith(".txt")