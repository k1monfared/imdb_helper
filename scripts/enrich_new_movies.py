#!/usr/bin/env python3
"""Enrich only newly added movie entries (from git diff) with IMDb data."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imdb_helper imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enrich_movies import (
    enrich_movie_entry,
    extract_movie_entries,
    find_imdb_match,
    load_movies_file,
    save_movies_file,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enrich only newly added movie entries with IMDb data"
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path("movies"),
        help="Path to movies file (default: movies)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    return parser.parse_args()


def get_new_movie_titles_from_diff(file_path: Path) -> set[str]:
    """Extract newly added movie titles from git staged diff."""
    try:
        # Get staged diff for the file
        result = subprocess.run(
            ["git", "diff", "--cached", "-U0", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return set()

    new_titles = set()

    # Pattern to match added lines with movie titles
    # Matches lines like: +        [x] Movie Title or +        [ ] Movie Title
    # Also matches: +    - Movie Title (for non-todo format)
    todo_pattern = re.compile(r"^\+\s*\[[ x-]\]\s*(.+?)\s*$")

    for line in result.stdout.splitlines():
        # Only look at added lines (starting with +, but not +++ header)
        if not line.startswith("+") or line.startswith("+++"):
            continue

        match = todo_pattern.match(line)
        if match:
            title = match.group(1).strip()
            # Skip if it looks like a property (contains colon early)
            if ":" in title:
                colon_pos = title.index(":")
                if colon_pos < 20:
                    continue
            new_titles.add(title.lower())

    return new_titles


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Get newly added movie titles from git diff
    new_titles = get_new_movie_titles_from_diff(args.file)

    if not new_titles:
        if args.verbose:
            print("No new movie entries detected in staged changes")
        sys.exit(0)

    if args.verbose:
        print(f"Found {len(new_titles)} new movie(s) in staged changes:")
        for title in new_titles:
            print(f"  - {title}")
        print()

    # Load file
    try:
        tree = load_movies_file(args.file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Extract all movie entries
    entries = extract_movie_entries(tree)
    if not entries:
        print("No movie entries found in file")
        sys.exit(0)

    # Filter to only new movies
    new_entries = [
        entry for entry in entries
        if entry.title.lower() in new_titles
    ]

    if not new_entries:
        if args.verbose:
            print("No matching entries found to enrich")
        sys.exit(0)

    print(f"Enriching {len(new_entries)} new movie(s)...")
    if args.dry_run:
        print("(Dry run - no changes will be written)\n")
    else:
        print()

    # Process each new movie
    enriched_count = 0

    for i, entry in enumerate(new_entries, 1):
        print(f"[{i}/{len(new_entries)}] {entry.title}")

        # Find IMDb match
        details = find_imdb_match(entry, interactive=False, verbose=args.verbose)
        if not details:
            continue

        # Enrich entry
        changes = enrich_movie_entry(entry, details, args.dry_run)
        if changes:
            for change in changes:
                print(change)
            enriched_count += 1
        else:
            print("  (already complete)")

    # Summary
    print(f"\nEnriched {enriched_count} of {len(new_entries)} new movie(s)")

    # Write back
    if not args.dry_run and enriched_count > 0:
        save_movies_file(tree, args.file)
        print(f"Changes written to {args.file}")
    elif args.dry_run:
        print("Dry run complete. Use without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
