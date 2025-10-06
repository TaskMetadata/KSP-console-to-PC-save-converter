#!/usr/bin/env python3
"""

(v5)

rename_folders_from_metadata_directory.py

Search a directory tree for every file named "metadata.txt", read the first
"displayName = <value>" line from each, sanitize that value, and rename the
parent folder of each metadata.txt to the sanitized displayName.

This performs renames automatically (no confirmation). If the desired name
already exists, a unique name is chosen by appending " (n)".

Supports a dry-run mode (--dry-run) which prints planned renames without
making any filesystem changes. Skips processing when the grandparent (2nd
level up) folder is named "common" (case-insensitive). It no longer skips
when the immediate parent folder is named "common".
"""

import os
import re
import sys
import argparse

_INVALID_WINDOWS_CHARS = r'<>:"/\\|?*\0'
_CONTROL_CHARS = ''.join(chr(i) for i in range(0, 32))


def sanitize_name(name: str) -> str:
    if not name:
        return "renamed_folder"
    name = name.strip()
    # remove surrounding quotes
    if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
        name = name[1:-1].strip()
    # remove trailing semicolons or commas
    name = name.rstrip(';,')
    # remove inline comments if present
    name = re.split(r'\s+#\s*|//', name, maxsplit=1)[0].strip()
    # remove control chars
    for ch in _CONTROL_CHARS:
        name = name.replace(ch, '')
    # replace invalid windows chars
    for ch in _INVALID_WINDOWS_CHARS:
        name = name.replace(ch, '_')
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return "renamed_folder"
    return name


def find_display_name_in_file(path: str) -> str:
    pattern = re.compile(r'\bdisplayName\s*=\s*(.+)', re.IGNORECASE)
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    value = m.group(1).strip()
                    # cut trailing inline comments
                    value = re.split(r'\s+#\s*|//', value, maxsplit=1)[0].strip()
                    return value.rstrip(';').strip()
    except Exception:
        return ''
    return ''


def unique_target_path(base_parent: str, desired_name: str) -> str:
    candidate = os.path.join(base_parent, desired_name)
    if not os.path.exists(candidate):
        return candidate
    n = 1
    while True:
        candidate_with_suffix = os.path.join(base_parent, f"{desired_name} ({n})")
        if not os.path.exists(candidate_with_suffix):
            return candidate_with_suffix
        n += 1


def collect_metadata_files(root: str):
    found = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower() == "metadata.txt":
                found.append(os.path.join(dirpath, fn))
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Rename parent folders of every metadata.txt in a directory tree using displayName (no confirmation)."
    )
    parser.add_argument('root', nargs='?', help="Root directory to search.")
    parser.add_argument('--dry-run', action='store_true', help="Show planned renames without performing them.")
    args = parser.parse_args()

    root = args.root
    dry_run = args.dry_run
    if not root:
        root = input("Enter the directory path to search for metadata.txt files: ").strip()

    if not root:
        print("No path provided. Exiting.")
        sys.exit(1)

    if not os.path.isdir(root):
        print(f"Path '{root}' is not an existing directory. Exiting.")
        sys.exit(1)

    root = os.path.abspath(root)
    metadata_files = collect_metadata_files(root)
    if not metadata_files:
        print(f"No metadata.txt files found under '{root}'. Nothing to do.")
        sys.exit(0)

    # Sort by depth (deepest first) so we rename inner folders before ancestors,
    # avoiding the "rename ancestor before descendant" problem.
    metadata_files.sort(
        key=lambda p: os.path.relpath(os.path.dirname(p), root).count(os.sep),
        reverse=True
    )

    renamed = 0
    planned = 0
    skipped = 0
    skipped_common_grandparent = 0
    failed = []

    for meta_path in metadata_files:
        try:
            parent_dir = os.path.abspath(os.path.dirname(meta_path))
            parent_basename = os.path.basename(parent_dir)

            # Grandparent (2nd level up)
            grandparent_dir = os.path.dirname(parent_dir)
            grandparent_basename = os.path.basename(grandparent_dir) if grandparent_dir else ''

            # Skip only if grandparent is named "common" (case-insensitive).
            if grandparent_basename.lower() == "common":
                print(f"[SKIP] Grandparent folder named 'common': {grandparent_dir} (child: {parent_dir})")
                skipped += 1
                skipped_common_grandparent += 1
                continue

            raw_value = find_display_name_in_file(meta_path)
            if not raw_value:
                print(f"[SKIP] No displayName in: {meta_path}")
                skipped += 1
                continue

            cleaned = sanitize_name(raw_value)
            current_name = parent_basename
            parent_of_parent = os.path.dirname(parent_dir) or os.path.abspath(os.sep)

            if current_name == cleaned:
                print(f"[SKIP] Already named: {parent_dir} -> {cleaned!r}")
                skipped += 1
                continue

            target_path = os.path.join(parent_of_parent, cleaned)
            if os.path.exists(target_path):
                final_target = unique_target_path(parent_of_parent, cleaned)
                print(f"[INFO] Desired name exists. Using unique: {final_target}")
            else:
                final_target = target_path

            if dry_run:
                print(f"[DRY-RUN] Would rename: {parent_dir} -> {final_target}")
                planned += 1
            else:
                os.rename(parent_dir, final_target)
                print(f"[RENAMED] {parent_dir} -> {final_target}")
                renamed += 1

        except Exception as exc:
            print(f"[ERROR] Failed to rename parent of '{meta_path}': {exc}")
            failed.append((meta_path, str(exc)))

    print()
    print("Summary:")
    print(f"  metadata files found : {len(metadata_files)}")
    if dry_run:
        print(f"  planned renames      : {planned}")
    else:
        print(f"  renamed              : {renamed}")
    print(f"  skipped (no-op)      : {skipped - skipped_common_grandparent}")
    print(f"  skipped (grandparent 'common') : {skipped_common_grandparent}")
    print(f"  failed               : {len(failed)}")
    if failed:
        for p, e in failed:
            print(f"    - {p}: {e}")


if __name__ == "__main__":
    main()