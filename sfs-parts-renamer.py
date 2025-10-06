#!/usr/bin/env python3
"""

(v5)

replace_sfs.py

Usage:
  replace_sfs.py INPUT_PATH         # INPUT_PATH may be a .sfs file or a directory
  replace_sfs.py --dry-run INPUT_PATH

This script performs targeted search-and-replace operations only when the
token to replace is directly preceded by the literal "name = " or "rTrf = "
(including the spaces exactly as shown). It can accept a path, and will
recursively process every .sfs file it can find under that path.

Replacements (left -> right):
  externalTankCapsule.v2 -> externalTankCapsule
  externalTankRound.v2   -> externalTankRound
  externalTankToroid.v2  -> externalTankToroid
  GrapplingDevice.v2     -> GrapplingDevice
  size3Decoupler.old     -> size3Decoupler
  vernierEngine.old      -> vernierEngine
  linearRcs.old          -> linearRcs

Note:
- This will always overwrite each input .sfs file in-place (no backups).
- Use --dry-run to see counts of replacements that would be made without writing.
"""

from __future__ import annotations
import argparse
import sys
import os
import re
from typing import Dict, List, Tuple
from collections import Counter

MAPPINGS: Dict[str, str] = {
    "externalTankCapsule.v2": "externalTankCapsule",
    "externalTankRound.v2": "externalTankRound",
    "externalTankToroid.v2": "externalTankToroid",
    "GrapplingDevice.v2": "GrapplingDevice",
    "size3Decoupler.old": "size3Decoupler",
    "vernierEngine.old": "vernierEngine",
    "linearRcs.old": "linearRcs",
}


def build_pattern(mapping_keys):
    # Build a regex that matches any of the keys when directly preceded by
    # "name = " or "rTrf = " (exact spacing). Using a fixed-width lookbehind.
    joined = "|".join(re.escape(k) for k in mapping_keys)
    # Ensure token boundary so we don't replace substrings in longer names.
    pattern = re.compile(r"(?<=name = |rTrf = )(" + joined + r")\b")
    return pattern


def process_text_and_count(text: str, pattern: re.Pattern, mapping: Dict[str, str]) -> Tuple[str, Counter]:
    """
    Return (new_text, counts) where counts is a Counter mapping original-token -> number of replacements.
    """
    counts = Counter()

    def repl(m):
        token = m.group(1)
        counts[token] += 1
        return mapping.get(token, token)

    new_text = pattern.sub(repl, text)
    return new_text, counts


def find_sfs_files(path: str) -> List[str]:
    """
    If path is a file and ends with .sfs (case-insensitive), returns [path].
    If path is a directory, walk recursively and return all .sfs files found.
    """
    path = os.path.expanduser(path)
    if os.path.isfile(path):
        if path.lower().endswith(".sfs"):
            return [os.path.abspath(path)]
        else:
            return []
    if os.path.isdir(path):
        results = []
        for root, dirs, files in os.walk(path):
            for fn in files:
                if fn.lower().endswith(".sfs"):
                    results.append(os.path.join(root, fn))
        return results
    return []


def process_file(infile: str, pattern: re.Pattern, mapping: Dict[str, str], dry_run: bool) -> Counter:
    """
    Process a single file. If dry_run is False, overwrite the file in-place when changes are made.
    Returns a Counter of replacements made (keys are original tokens).
    """
    try:
        with open(infile, "r", encoding="utf-8") as f:
            original = f.read()
    except OSError as e:
        print(f"Error reading file {infile}: {e}", file=sys.stderr)
        return Counter()

    new_text, counts = process_text_and_count(original, pattern, mapping)

    if not counts:
        return Counter()

    if dry_run:
        return counts

    try:
        with open(infile, "w", encoding="utf-8") as f:
            f.write(new_text)
    except OSError as e:
        print(f"Error writing file {infile}: {e}", file=sys.stderr)
        return Counter()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Recursively perform targeted replacements in .sfs files under a given path."
    )
    parser.add_argument("input_path", help="Input .sfs file or directory to search for .sfs files")
    parser.add_argument("--dry-run", action="store_true", help="Print summary of changes but do not write files")
    args = parser.parse_args(argv)

    input_path = args.input_path
    dry_run = args.dry_run

    files = find_sfs_files(input_path)
    if not files:
        print(f"No .sfs files found at: {input_path}", file=sys.stderr)
        return 2

    pattern = build_pattern(MAPPINGS.keys())
    total_counts = Counter()
    files_changed = []

    for fpath in files:
        counts = process_file(fpath, pattern, MAPPINGS, dry_run)
        if counts:
            total_counts.update(counts)
            files_changed.append((fpath, sum(counts.values())))

            if not dry_run:
                print(f"Edited in place: {fpath} ({sum(counts.values())} replacement(s))")

    if not total_counts:
        print("No replacements needed.")
        return 0

    # Dry-run summary or final summary
    print("Summary of replacements:")
    for src in MAPPINGS.keys():
        c = total_counts.get(src, 0)
        if c:
            print(f"  {src} -> {MAPPINGS[src]} : {c} occurrence(s)")

    print(f"Files modified: {len(files_changed)} / {len(files)}")
    if dry_run:
        print("Dry-run: no files were written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())