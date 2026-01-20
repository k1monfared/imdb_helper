#!/usr/bin/env python3
"""Parse and enrich the NYT 2025 top 100 section.

Handles format: "Movie Title (Year), Director Name"
Extracts year and director, cleans title, then enriches with IMDb data.
"""

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

import loglog

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imdb_helper.models import MovieDetails
from imdb_helper.search import SearchError, get_movie_details, search_movies, should_skip_menu


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse and enrich NYT 2025 section")
    parser.add_argument(
        "-f", "--file", type=Path, default=Path("~/public/notes/movies"),
        help="Path to movies file",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview changes")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    return parser.parse_args()


def find_nyt_section(tree: "loglog.TreeNode") -> "loglog.TreeNode | None":
    """Find the NYT 2025 top 100 section node."""
    def search(node):
        for child in node.children:
            if "NYT 2025" in child.data:
                return child
            result = search(child)
            if result:
                return result
        return None
    return search(tree)


def parse_nyt_entry(title: str) -> dict:
    """Parse 'Movie Title (Year), Director' format."""
    result = {"title": title, "year": None, "director": None}

    # Pattern: "Title (Year), Director" or "Title (Year)"
    match = re.match(r"^(.+?)\s*\((\d{4})\)(?:\s*,\s*(.+))?$", title.strip())
    if match:
        result["title"] = match.group(1).strip()
        result["year"] = match.group(2)
        if match.group(3):
            result["director"] = match.group(3).strip()

    return result


def get_property(node: "loglog.TreeNode", key: str) -> str | None:
    """Get existing property value."""
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip().lower()
            if k == key.lower():
                return data.split(":", 1)[1].strip()
    return None


def add_property(node: "loglog.TreeNode", key: str, value: str) -> None:
    """Add a property to a node."""
    new_node = loglog.TreeNode(data=f"{key}: {value}")
    node.add_child(new_node)


def enrich_movie(node: "loglog.TreeNode", title: str, year: int | None, dry_run: bool) -> list[str]:
    """Search IMDb and enrich the movie entry."""
    changes = []

    try:
        results = search_movies(title)
    except SearchError as e:
        return [f"  Warning: Search failed: {e}"]

    if not results:
        return [f"  No IMDb results found"]

    # Try to auto-match with year
    auto_match = should_skip_menu(title, results, year, None)
    if not auto_match:
        # Try first result if year matches
        for r in results:
            if r.year == year:
                auto_match = r
                break
        if not auto_match:
            auto_match = results[0]  # Fall back to first result

    try:
        details = get_movie_details(auto_match.imdb_id)
    except SearchError as e:
        return [f"  Warning: Failed to get details: {e}"]

    # Build IMDb URL
    imdb_url = f"https://www.imdb.com/title/{details.imdb_id}/"

    # Check what's missing
    if not get_property(node, "imdb"):
        changes.append(f"  + imdb: {imdb_url}")
        if not dry_run:
            add_property(node, "imdb", imdb_url)

    if not get_property(node, "Rating") and details.rating:
        changes.append(f"  + Rating: {details.rating}/10 (IMDb)")
        if not dry_run:
            add_property(node, "Rating", f"{details.rating}/10 (IMDb)")

    if not get_property(node, "Genres") and details.genres:
        genres = ", ".join(details.genres)
        changes.append(f"  + Genres: {genres} (IMDb)")
        if not dry_run:
            add_property(node, "Genres", f"{genres} (IMDb)")

    if not get_property(node, "Duration") and details.duration:
        changes.append(f"  + Duration: {details.duration} (IMDb)")
        if not dry_run:
            add_property(node, "Duration", f"{details.duration} (IMDb)")

    if not get_property(node, "Synopsis") and details.synopsis:
        changes.append(f"  + Synopsis: {details.synopsis[:60]}... (IMDb)")
        if not dry_run:
            add_property(node, "Synopsis", f"{details.synopsis} (IMDb)")

    return changes


def process_nyt_section(section: "loglog.TreeNode", dry_run: bool, verbose: bool) -> tuple[int, int]:
    """Process all movies in the NYT section."""
    processed = 0
    enriched = 0

    for i, child in enumerate(section.children, 1):
        if child.type != "todo":
            continue

        original_title = child.data.strip()
        parsed = parse_nyt_entry(original_title)

        print(f"[{i}] {original_title}")

        # Update title if we parsed out year/director
        changes = []
        if parsed["title"] != original_title:
            changes.append(f"  Title: \"{original_title}\" -> \"{parsed['title']}\"")
            if not dry_run:
                child.data = parsed["title"]

        # Add year if parsed and not present
        if parsed["year"] and not get_property(child, "Year"):
            changes.append(f"  + Year: {parsed['year']}")
            if not dry_run:
                add_property(child, "Year", parsed["year"])

        # Add director if parsed and not present
        if parsed["director"] and not get_property(child, "Director"):
            changes.append(f"  + Director: {parsed['director']}")
            if not dry_run:
                add_property(child, "Director", parsed["director"])

        # Enrich with IMDb data
        year_int = int(parsed["year"]) if parsed["year"] else None

        # Small delay to avoid rate limiting
        if i > 1:
            time.sleep(0.5)

        imdb_changes = enrich_movie(child, parsed["title"], year_int, dry_run)
        changes.extend(imdb_changes)

        for change in changes:
            print(change)

        processed += 1
        if changes:
            enriched += 1

    return processed, enriched


def main():
    args = parse_args()
    path = args.file.expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    section = find_nyt_section(tree)
    if not section:
        print("Error: NYT 2025 section not found")
        sys.exit(1)

    print(f"Processing NYT 2025 top 100 section...")
    if args.dry_run:
        print("(Dry run)\n")
    else:
        print()

    processed, enriched = process_nyt_section(section, args.dry_run, args.verbose)

    print(f"\nSummary:")
    print(f"  Movies processed: {processed}")
    print(f"  Movies enriched: {enriched}")

    if not args.dry_run and enriched > 0:
        backup_path = path.with_suffix(".bak")
        shutil.copy2(path, backup_path)
        with open(path, "w") as f:
            loglog.print_tree_to_file(tree, f)
        print(f"\nChanges written to {path}")
        print(f"Backup saved to {backup_path}")
    elif args.dry_run:
        print("\nDry run complete. Use without --dry-run to apply.")


if __name__ == "__main__":
    main()
