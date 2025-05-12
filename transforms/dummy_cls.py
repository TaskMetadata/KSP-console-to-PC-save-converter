from models import BlobMetadata


class GameFileTransformCls:
    def __init__(self, filepath: str, blob_meta: BlobMetadata):
        self.filepath = filepath
        self.meta = blob_meta

    @staticmethod
    def download_filepath() -> str:
        raise NotImplementedError()

    @staticmethod
    def save_filepath() -> str:
        raise NotImplementedError()
    
    @staticmethod
    def can_download() -> bool:
        raise NotImplementedError()