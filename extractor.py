"""

(v6)

Extracts individual files from KSP Xbox Savegame blobs.

This updated version accepts either a single input file or an input directory.
If a directory is provided, it will recursively run the extractor on every
regular file under that directory. For each input file, a corresponding output
subfolder is created inside the user-provided output directory using the input
file's name. Extracted files from that input file go into that subfolder.

NOTE: It was originally designed to work with the --dry parameter, but I asked an AI to change it to --dry-run to keep it consistent with the other programs. It said it preserved the variable names though, so thats why it might look a little weird. -Task_Metadata (on github)
"""
import io
import os
import argparse
import pathlib
import struct
import lzma

from dissect import cstruct

TYPES = cstruct.cstruct()
TYPES.load("""
struct KSP_BLOB_ENTRY {
  UINT EntryLen;
  BYTE Padding;
  BYTE FilenameLen;
  BYTE Padding2;
  BYTE LastFileMarker;
  CHAR Filename[FilenameLen];
  BYTE Data[EntryLen];
};
""")

def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack("<I", data[offset:offset+4])[0]

def decompress(data: bytes) -> bytes:
    context = lzma.LZMADecompressor(
        format=lzma.FORMAT_RAW,
        filters=[
            {"id": lzma.FILTER_LZMA1},
        ]
    )
    return context.decompress(data)

def extract_file(inputfile: io.BufferedReader, outputdir: pathlib.Path, dryrun: bool) -> None:
    """
    Extract all entries from the file-like `inputfile` into the `outputdir` root.
    `outputdir` is the root directory for this single input file's extractions
    (i.e. outputdir/<extracted paths>).
    """
    inputfile.seek(0, os.SEEK_END)
    total_filesize = inputfile.tell()
    inputfile.seek(0, os.SEEK_SET)

    while True:
        parsed = TYPES.KSP_BLOB_ENTRY(inputfile)

        # Did we reach EOF yet?
        if parsed.LastFileMarker:
            assert parsed.Filename == b""
            assert inputfile.tell() == total_filesize
            break

        # Strip leading "\" of filename and null terminator
        filename = parsed.Filename.decode('utf-8').strip()[1:-1]

        compressed = False
        if filename.endswith(".cmp"):
            compressed = True
            filename = filename[:-4]

        target_filepath = outputdir.joinpath(pathlib.PureWindowsPath(filename))

        if not target_filepath.parent.exists() and not dryrun:
            target_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if not dryrun:
            compressed_data = parsed.Data.dumps()

            if compressed:
                compressed_length = len(compressed_data)
                uncompressed_length = read_u32(compressed_data, 5)

                print(f"{target_filepath} ({compressed_length=:X} {uncompressed_length=:X})")

                without_header = compressed_data[9:]
                data = decompress(without_header)

                assert len(data) == uncompressed_length, "Mismatch of decompressed data size"
            else:
                data = compressed_data

            with io.open(target_filepath, "wb") as f:
                f.write(data)
        else:
            # In dry-run show where the file would be extracted
            print(target_filepath)

def main() -> None:
    parser = argparse.ArgumentParser("KSP Savegame blob extractor")
    parser.add_argument("inputpath", help="Input file or directory", type=pathlib.Path)
    parser.add_argument("outputdir", help="Output directory root", type=pathlib.Path)
    parser.add_argument("--dry-run", dest="dry", action="store_true", help="Dry-Run (no extraction, no folder/file creation)")
    args = parser.parse_args()

    inputpath: pathlib.Path = args.inputpath
    outputroot: pathlib.Path = args.outputdir
    dry = args.dry

    # Ensure output root exists when not a dry run (so subfolders can be created)
    if not dry:
        outputroot.mkdir(parents=True, exist_ok=True)

    if inputpath.is_file():
        # Single file: create an output subfolder named after the input file
        out_subdir = outputroot / inputpath.name
        if not dry:
            out_subdir.mkdir(parents=True, exist_ok=True)
        with inputpath.open("rb") as fh:
            print(f"Processing file: {inputpath} -> {out_subdir}")
            extract_file(fh, out_subdir, dry)
    elif inputpath.is_dir():
        # Directory: process all files recursively
        files = list(inputpath.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            out_subdir = outputroot / f.name
            if not dry:
                out_subdir.mkdir(parents=True, exist_ok=True)
            with f.open("rb") as fh:
                print(f"Processing file: {f} -> {out_subdir}")
                extract_file(fh, out_subdir, dry)
    else:
        raise SystemExit(f"Input path '{inputpath}' does not exist or is not a file/directory")

if __name__ == '__main__':
    main()