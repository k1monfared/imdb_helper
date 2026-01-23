#!/usr/bin/env python3
"""Parse and enrich the NYT 2025 top 100 section.

Handles format: "Movie Title (Year), Director Name"
Extracts year and director, cleans title, then enriches with IMDb data.

Features:
- Skips movies that already have IMDb data (no wasted API calls)
- Caches API results to avoid duplicate calls between dry-run and real run
- Configurable delay between API calls to avoid rate limiting
"""

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import loglog

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imdb_helper.models import MovieDetails
from imdb_helper.search import SearchError, get_movie_details, search_movies, should_skip_menu

# Cache file location
CACHE_FILE = Path(__file__).parent / ".nyt_imdb_cache.json"

# Default delay between API calls (seconds)
DEFAULT_DELAY = 3.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse and enrich NYT 2025 section")
    parser.add_argument(
        "-f", "--file", type=Path, default=Path("~/public/notes/movies"),
        help="Path to movies file",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview changes (uses cache)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help=f"Delay between API calls in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--clear-cache", action="store_true",
        help="Clear the API cache before running",
    )
    parser.add_argument(
        "--cache-only", action="store_true",
        help="Only use cached data, don't make new API calls",
    )
    return parser.parse_args()


def load_cache() -> dict:
    """Load cached API results."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache: dict) -> None:
    """Save API results to cache."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def clear_cache() -> None:
    """Clear the cache file."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print(f"Cache cleared: {CACHE_FILE}")


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


def has_imdb_data(node: "loglog.TreeNode") -> bool:
    """Check if a movie node already has IMDb data."""
    return get_property(node, "imdb") is not None


def add_property(node: "loglog.TreeNode", key: str, value: str) -> None:
    """Add a property to a node."""
    new_node = loglog.TreeNode(data=f"{key}: {value}")
    node.add_child(new_node)


def make_cache_key(title: str, year: int | None) -> str:
    """Create a cache key from title and year."""
    return f"{title.lower().strip()}|{year or 'unknown'}"


def fetch_movie_details(
    title: str,
    year: int | None,
    cache: dict,
    cache_only: bool = False,
    verbose: bool = False
) -> dict | None:
    """
    Fetch movie details from IMDb, using cache when available.

    Returns a dict with movie details or None if not found.
    """
    cache_key = make_cache_key(title, year)

    # Check cache first
    if cache_key in cache:
        cached = cache[cache_key]
        if cached.get("error"):
            if verbose:
                print(f"  (cached error: {cached['error']})")
            return None
        if verbose:
            print(f"  (using cached data)")
        return cached

    # If cache-only mode, don't make API calls
    if cache_only:
        if verbose:
            print(f"  (not in cache, skipping)")
        return None

    # Search IMDb
    try:
        results = search_movies(title)
    except SearchError as e:
        cache[cache_key] = {"error": str(e)}
        save_cache(cache)
        return None

    if not results:
        cache[cache_key] = {"error": "No results found"}
        save_cache(cache)
        return None

    # Try to auto-match with year
    auto_match = should_skip_menu(title, results, year)
    if not auto_match:
        # Try first result if year matches
        for r in results:
            if r.year == year:
                auto_match = r
                break
        if not auto_match:
            auto_match = results[0]  # Fall back to first result

    # Get full details
    try:
        details = get_movie_details(auto_match.imdb_id)
    except SearchError as e:
        cache[cache_key] = {"error": str(e)}
        save_cache(cache)
        return None

    # Cache the result
    result = {
        "imdb_id": details.imdb_id,
        "title": details.title,
        "year": details.year,
        "rating": details.rating,
        "genres": details.genres,
        "duration": details.duration,
        "synopsis": details.synopsis,
        "director": details.director,
    }
    cache[cache_key] = result
    save_cache(cache)

    return result


def enrich_movie(
    node: "loglog.TreeNode",
    title: str,
    year: int | None,
    cache: dict,
    dry_run: bool,
    cache_only: bool = False,
    verbose: bool = False
) -> list[str]:
    """Enrich a movie entry with IMDb data."""
    changes = []

    details = fetch_movie_details(title, year, cache, cache_only, verbose)
    if not details:
        if cache_only:
            return [f"  (not in cache)"]
        return [f"  Warning: Could not fetch IMDb data"]

    # Build IMDb URL
    imdb_url = f"https://www.imdb.com/title/{details['imdb_id']}/"

    # Check what's missing and add
    if not get_property(node, "imdb"):
        changes.append(f"  + imdb: {imdb_url}")
        if not dry_run:
            add_property(node, "imdb", imdb_url)

    if not get_property(node, "Rating") and details.get("rating"):
        changes.append(f"  + Rating: {details['rating']}/10 (IMDb)")
        if not dry_run:
            add_property(node, "Rating", f"{details['rating']}/10 (IMDb)")

    if not get_property(node, "Genres") and details.get("genres"):
        genres = ", ".join(details["genres"])
        changes.append(f"  + Genres: {genres} (IMDb)")
        if not dry_run:
            add_property(node, "Genres", f"{genres} (IMDb)")

    if not get_property(node, "Duration") and details.get("duration"):
        changes.append(f"  + Duration: {details['duration']} (IMDb)")
        if not dry_run:
            add_property(node, "Duration", f"{details['duration']} (IMDb)")

    if not get_property(node, "Synopsis") and details.get("synopsis"):
        synopsis = details["synopsis"]
        changes.append(f"  + Synopsis: {synopsis[:60]}... (IMDb)")
        if not dry_run:
            add_property(node, "Synopsis", f"{synopsis} (IMDb)")

    return changes


def process_nyt_section(
    section: "loglog.TreeNode",
    cache: dict,
    dry_run: bool,
    verbose: bool,
    delay: float,
    cache_only: bool = False
) -> tuple[int, int, int]:
    """Process all movies in the NYT section.

    Returns: (processed, enriched, skipped)
    """
    processed = 0
    enriched = 0
    skipped = 0
    need_delay = False  # Track if we made an API call

    for i, child in enumerate(section.children, 1):
        if child.type != "todo":
            continue

        original_title = child.data.strip()
        parsed = parse_nyt_entry(original_title)

        # Check if already has IMDb data - skip entirely
        if has_imdb_data(child):
            if verbose:
                print(f"[{i}] {original_title} (already has IMDb data, skipping)")
            skipped += 1
            continue

        print(f"[{i}] {original_title}")

        # Delay between API calls (only if we made one previously)
        if need_delay and not cache_only:
            cache_key = make_cache_key(parsed["title"], int(parsed["year"]) if parsed["year"] else None)
            if cache_key not in cache:
                time.sleep(delay)

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
        cache_key = make_cache_key(parsed["title"], year_int)

        # Track if this will be an API call (not cached)
        will_call_api = cache_key not in cache and not cache_only

        imdb_changes = enrich_movie(
            child, parsed["title"], year_int, cache,
            dry_run, cache_only, verbose
        )
        changes.extend(imdb_changes)

        for change in changes:
            print(change)

        processed += 1
        if changes and not any("Warning" in c or "not in cache" in c for c in changes):
            enriched += 1

        # Set flag if we made an API call
        if will_call_api:
            need_delay = True

    return processed, enriched, skipped


def main():
    args = parse_args()

    # Handle cache clearing
    if args.clear_cache:
        clear_cache()

    path = args.file.expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    section = find_nyt_section(tree)
    if not section:
        print("Error: NYT 2025 section not found")
        sys.exit(1)

    # Load cache
    cache = load_cache()
    cache_count = len([k for k, v in cache.items() if not v.get("error")])

    print(f"Processing NYT 2025 top 100 section...")
    print(f"Cache: {cache_count} movies cached, delay: {args.delay}s between API calls")
    if args.dry_run:
        print("Mode: Dry run (will cache results for later use)")
    elif args.cache_only:
        print("Mode: Cache only (no new API calls)")
    print()

    processed, enriched, skipped = process_nyt_section(
        section, cache, args.dry_run, args.verbose, args.delay, args.cache_only
    )

    print(f"\nSummary:")
    print(f"  Movies processed: {processed}")
    print(f"  Movies enriched: {enriched}")
    print(f"  Movies skipped (already have IMDb): {skipped}")
    print(f"  Cache size: {len([k for k, v in cache.items() if not v.get('error')])} movies")

    if not args.dry_run and enriched > 0:
        backup_path = path.with_suffix(".bak")
        shutil.copy2(path, backup_path)
        with open(path, "w") as f:
            loglog.print_tree_to_file(tree, f)
        print(f"\nChanges written to {path}")
        print(f"Backup saved to {backup_path}")
    elif args.dry_run:
        print(f"\nDry run complete. Results cached to {CACHE_FILE}")
        print("Run without --dry-run to apply changes using cached data.")


if __name__ == "__main__":
    main()
