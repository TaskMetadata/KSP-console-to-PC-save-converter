import pytest
from pathlib import Path
from datetime import datetime
from models import BlobMetadata, SavegameBlobType

@pytest.mark.parametrize("input_str,expected", [
    ("/assemblies/0133f6681e6df707/objectsXass,savedgame", "assemblies/0133f6681e6df707/objects.ass"),
    ("assemblies/0133f6681e6df707/objectsXass,savedgame", "assemblies/0133f6681e6df707/objects.ass"),
    ("assemblies/0133f6681e6df707/requirementsXbin,savedgame", "assemblies/0133f6681e6df707/requirements.bin"),
    ("assemblies/01872970d83c5f05/localization/stringtables/enEus/enEusXstr,savedgame", "assemblies/01872970d83c5f05/localization/stringtables/en_us/en_us.str")
])
def test_filename_sanitize(input_str: str, expected: str):
    meta = BlobMetadata(
        fileName=input_str,
        etag="",
        clientFileTime=datetime.now(),
        size=0
    )
    assert meta.normalized_filename() == Path(expected)

@pytest.mark.parametrize("input_str,expected", [
    ("/assemblies/0133f6681e6df707/objectsXass,savedgame", SavegameBlobType.Savedgame),
    ("assemblies/0133f6681e6df707/objectsXass,savedgame", SavegameBlobType.Savedgame),
    ("assemblies/0133f6681e6df707/requirementsXbin,savedgame", SavegameBlobType.Savedgame),
    ("assemblies/01872970d83c5f05/localization/stringtables/enEus/enEusXstr,savedgame", SavegameBlobType.Savedgame),
])
def test_blob_type(input_str: str, expected: SavegameBlobType):
    meta = BlobMetadata(
        fileName=input_str,
        etag="",
        clientFileTime=datetime.now(),
        size=0
    )
    assert meta.blob_type == expected