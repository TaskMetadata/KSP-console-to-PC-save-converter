#!/usr/bin/env python3
"""

(v4)

replace_craft.py

Usage:
    python replace_craft.py path/to/file_or_directory [--dry-run]

If the path is a file, it will be processed (must be a .craft file to be modified).
If the path is a directory, every .craft file contained within that directory (recursively)
will be processed.

By default the script modifies files in place (atomic replace). Use --dry-run to see what
would change without writing any files.

Selective search-and-replace mappings:
  externalTankCapsule.v2 -> externalTankCapsule
  externalTankRound.v2   -> externalTankRound
  externalTankToroid.v2  -> externalTankToroid
  GrapplingDevice.v2     -> GrapplingDevice
  size3Decoupler.old     -> size3Decoupler
  vernierEngine.old      -> vernierEngine
  linearRcs.old          -> linearRcs

A replacement for a matched substring is performed only when, somewhere earlier on
the same line (i.e. before the match position), that line contains one of:
  "link = ", "part = ", or "srfN = "

Examples:
  python replace_craft.py ./ship.craft
  python replace_craft.py ./crafts_dir --dry-run
"""

from pathlib import Path
from typing import Dict, List, Tuple
import argparse
import sys
import tempfile

# Define mappings: "search_term" -> "replacement"
MAPPINGS: List[Tuple[str, str]] = [
    ("externalTankCapsule.v2", "externalTankCapsule"),
    ("externalTankRound.v2", "externalTankRound"),
    ("externalTankToroid.v2", "externalTankToroid"),
    ("GrapplingDevice.v2", "GrapplingDevice"),
    ("size3Decoupler.old", "size3Decoupler"),
    ("vernierEngine.old", "vernierEngine"),
    ("linearRcs.old", "linearRcs"),
]

# Prefix tokens that must appear earlier on the same line (before the match)
PREFIXES = ["link = ", "part = ", "srfN = "]

# Sort search terms by descending length so longer matches take precedence
MAPPINGS.sort(key=lambda x: len(x[0]), reverse=True)
SEARCH_TERMS = [m[0] for m in MAPPINGS]
REPLACEMENTS = {m[0]: m[1] for m in MAPPINGS}


def should_replace_at(original_line: str, match_pos: int) -> bool:
    """Return True if any prefix appears somewhere in original_line before match_pos."""
    for p in PREFIXES:
        if original_line.rfind(p, 0, match_pos) != -1:
            return True
    return False


def process_line(original_line: str) -> Tuple[str, Dict[str, int]]:
    """
    Process a single line, replacing matches when the rule is satisfied.
    Returns the new line and a dict of replacement counts for this line.
    """
    out_chars: List[str] = []
    i = 0
    n = len(original_line)
    counts: Dict[str, int] = {k: 0 for k in SEARCH_TERMS}

    while i < n:
        matched = False
        # Try each search term (ordered by length desc)
        for term in SEARCH_TERMS:
            term_len = len(term)
            if i + term_len <= n and original_line.startswith(term, i):
                if should_replace_at(original_line, i):
                    out_chars.append(REPLACEMENTS[term])
                    counts[term] += 1
                    i += term_len
                    matched = True
                    break
                else:
                    # Do not replace here; allow fallback to append a single character
                    matched = False
                    # continue trying other (shorter) terms in case of overlap
        if not matched:
            out_chars.append(original_line[i])
            i += 1

    return "".join(out_chars), counts


def process_lines(lines: List[str]) -> Tuple[List[Tuple[int, str, str, Dict[str, int]]], Dict[str, int]]:
    """
    Process list of lines.
    Returns:
      - changes: list of tuples (line_no (1-based), original_line, new_line, counts)
      - totals: dict of totals per search term
    """
    changes = []
    totals: Dict[str, int] = {k: 0 for k in SEARCH_TERMS}
    for idx, line in enumerate(lines, start=1):
        new_line, counts = process_line(line)
        if new_line != line:
            changes.append((idx, line, new_line, counts))
        for k, v in counts.items():
            totals[k] += v
    return changes, totals


def write_in_place(input_path: Path, out_text: str) -> None:
    """
    Atomically overwrite input_path with out_text by writing to a temp file in the same directory and replacing.
    """
    dirpath = input_path.parent
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(dirpath), prefix=".tmp_replace_craft_") as tf:
        tf_name = Path(tf.name)
        tf.write(out_text)
    # Atomic replace
    tf_name.replace(input_path)


def find_craft_files(path: Path) -> List[Path]:
    """
    If path is a file, return it if it's a .craft file.
    If path is a directory, return a list of all .craft files under it (recursive).
    """
    if path.is_file():
        if path.suffix.lower() == ".craft":
            return [path]
        else:
            return []
    files = list(path.rglob("*.craft"))
    return files


def process_file(path: Path, dry_run: bool) -> Tuple[int, Dict[str, int]]:
    """
    Process a single .craft file.
    Returns (replacements_made_count, totals_per_term)
    If dry_run is True, file is not written.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changes, totals = process_lines(lines)
    total_replacements = sum(totals.values())

    if dry_run:
        if total_replacements:
            print(f"\n[DRY RUN] {path} - {total_replacements} replacement(s) would be made:")
            for term, count in totals.items():
                if count:
                    print(f"  {term} -> {REPLACEMENTS[term]} : {count}")
            print("  Changed lines:")
            for line_no, orig, new, counts in changes:
                orig_display = orig.rstrip("\r\n")
                new_display = new.rstrip("\r\n")
                print(f"    {line_no}:")
                print(f"      - {orig_display!r}")
                print(f"      + {new_display!r}")
        else:
            print(f"\n[DRY RUN] {path} - no replacements would be performed.")
        return total_replacements, totals

    # Not a dry run: perform in-place write only if there are replacements
    if total_replacements == 0:
        print(f"{path} - no replacements. File left unchanged.")
        return 0, totals

    # Build final text
    processed_lines = []
    for line in lines:
        new_line, _ = process_line(line)
        processed_lines.append(new_line)
    final_text = "".join(processed_lines)

    try:
        write_in_place(path, final_text)
    except Exception as exc:
        print(f"Error writing file '{path}' in place: {exc}", file=sys.stderr)
        return 0, totals

    print(f"{path} - {total_replacements} replacement(s) applied.")
    return total_replacements, totals


def main(argv):
    ap = argparse.ArgumentParser(description="Selective search-and-replace for .craft files (file or directory).")
    ap.add_argument("path", help="Path to a .craft file or a directory containing .craft files (recursive)")
    ap.add_argument("--dry-run", action="store_true", help="Show changes that would be made, do not write to files")
    args = ap.parse_args(argv)

    input_path = Path(args.path)
    if not input_path.exists():
        print(f"Error: path '{input_path}' does not exist.", file=sys.stderr)
        return 2

    craft_files = find_craft_files(input_path)
    if not craft_files:
        if input_path.is_file():
            print(f"Error: '{input_path}' is not a .craft file.", file=sys.stderr)
            return 2
        print(f"No .craft files found under '{input_path}'.")
        return 0

    overall_totals: Dict[str, int] = {k: 0 for k in SEARCH_TERMS}
    files_processed = 0
    total_replacements_all = 0

    for cf in sorted(craft_files):
        files_processed += 1
        replacements, totals = process_file(cf, args.dry_run)
        total_replacements_all += replacements
        for k, v in totals.items():
            overall_totals[k] += v

    # Summary
    print("\nSummary:")
    print(f"  Files considered: {len(craft_files)}")
    print(f"  Files processed:  {files_processed}")
    print(f"  Total replacements: {total_replacements_all}")
    if total_replacements_all:
        print("  Breakdown by term:")
        for term, count in overall_totals.items():
            if count:
                print(f"    {term} -> {REPLACEMENTS[term]} : {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))