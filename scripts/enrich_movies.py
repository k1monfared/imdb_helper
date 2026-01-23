#!/usr/bin/env python3
"""Enrich movie entries in a loglog file with IMDb data."""

import argparse
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import loglog

# Add parent directory to path for imdb_helper imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imdb_helper.menu import show_movie_menu
from imdb_helper.models import MovieDetails
from imdb_helper.search import SearchError, get_movie_details, search_movies, should_skip_menu


@dataclass
class PropertyValue:
    """A property with its value and source annotation."""

    value: str
    source: str | None  # None = user, "IMDb" = fetched
    node: "loglog.TreeNode"  # Reference to original node


@dataclass
class MovieEntry:
    """Represents a movie entry from the loglog file."""

    node: "loglog.TreeNode"  # Reference to original node
    title: str  # Extracted from node.data
    properties: dict[str, PropertyValue]  # Parsed properties (lowercase keys)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enrich movie entries in a loglog file with IMDb data"
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path("~/public/notes/movies"),
        help="Path to movies file (default: ~/public/notes/movies)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to file",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Show selection menu for ambiguous matches",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    return parser.parse_args()


def load_movies_file(path: Path) -> "loglog.TreeNode":
    """Load and parse the movies loglog file."""
    expanded_path = path.expanduser().resolve()
    if not expanded_path.exists():
        raise FileNotFoundError(f"Movies file not found: {expanded_path}")
    return loglog.build_tree_from_file(str(expanded_path))


def is_movie_entry(node: "loglog.TreeNode") -> bool:
    """Determine if a node represents a movie entry."""
    data = node.data.strip()
    if not data:
        return False

    # Todo items (with [x], [], [-]) are likely movie entries
    if node.type == "todo":
        return True

    # Not a property line (has colon at the end, indicating a section header)
    if data.endswith(":"):
        return False

    # Not a property line (has colon early in string)
    if ":" in data:
        colon_pos = data.index(":")
        # If colon appears within first 20 chars, likely a property
        if colon_pos < 20:
            return False

    # Not a comment or section header
    if data.startswith("#") or data.startswith("//"):
        return False

    return True


def parse_property(node: "loglog.TreeNode") -> tuple[str | None, str, str | None]:
    """Parse a property node into (key, value, source)."""
    data = node.data.strip()
    if ":" not in data:
        return (None, data, None)

    # Split on first colon
    colon_pos = data.index(":")
    key = data[:colon_pos].strip()
    value = data[colon_pos + 1 :].strip()

    # Check for source annotation: "8.7 (IMDb)" -> ("8.7", "IMDb")
    source = None
    if value.endswith(")") and "(" in value:
        paren_pos = value.rfind("(")
        potential_source = value[paren_pos + 1 : -1]
        if potential_source in ("IMDb", "user"):
            source = potential_source
            value = value[:paren_pos].strip()

    # Check for key with source annotation: "Rating (IMDb): 8.7"
    if key.endswith(")") and "(" in key:
        paren_pos = key.rfind("(")
        potential_source = key[paren_pos + 1 : -1]
        if potential_source in ("IMDb", "user"):
            source = potential_source
            key = key[:paren_pos].strip()

    return (key, value, source)


def parse_movie_entry(node: "loglog.TreeNode") -> MovieEntry:
    """Parse a movie node into structured MovieEntry."""
    title = node.data.strip()
    properties = {}

    for child in node.children:
        key, value, source = parse_property(child)
        if key:
            key_lower = key.lower()
            # Handle "imdb" property which contains URL - extract ID
            if key_lower == "imdb" and "imdb.com" in value:
                # Extract IMDb ID from URL like https://www.imdb.com/title/tt0133093/
                match = re.search(r"tt\d+", value)
                if match:
                    properties["imdb id"] = PropertyValue(
                        value=match.group(), source=source, node=child
                    )
            properties[key_lower] = PropertyValue(
                value=value, source=source, node=child
            )

    return MovieEntry(node=node, title=title, properties=properties)


def extract_movie_entries(tree: "loglog.TreeNode") -> list[MovieEntry]:
    """Extract movie entries from tree, searching recursively."""
    entries = []

    def search_node(node: "loglog.TreeNode") -> None:
        """Recursively search for movie entries."""
        for child in node.children:
            if is_movie_entry(child):
                entry = parse_movie_entry(child)
                entries.append(entry)
            else:
                # Not a movie, search its children
                search_node(child)

    search_node(tree)
    return entries


def find_imdb_match(
    entry: MovieEntry, interactive: bool = False, verbose: bool = False
) -> MovieDetails | None:
    """Search IMDb and find the best match for a movie entry."""
    title = entry.title

    # Extract search hints from existing properties
    year_prop = entry.properties.get("year")
    year_int = None
    if year_prop:
        try:
            year_int = int(year_prop.value)
        except ValueError:
            pass

    director_prop = entry.properties.get("director")
    director_str = director_prop.value if director_prop else None

    # Check if we already have IMDb ID
    imdb_id_prop = entry.properties.get("imdb id")
    if imdb_id_prop:
        try:
            return get_movie_details(imdb_id_prop.value)
        except SearchError:
            if verbose:
                print(f"  IMDb ID lookup failed, falling back to search")

    # Search IMDb
    try:
        results = search_movies(title)
    except SearchError as e:
        print(f"  Warning: Search failed for '{title}': {e}")
        return None

    if not results:
        print(f"  No IMDb results found for '{title}'")
        return None

    # Try auto-selection first
    auto_match = should_skip_menu(title, results, year_int)
    if auto_match:
        if verbose:
            print(f"  Auto-matched: {auto_match.title} ({auto_match.year})")
        try:
            return get_movie_details(auto_match.imdb_id)
        except SearchError as e:
            print(f"  Warning: Failed to get details for '{auto_match.title}': {e}")
            return None

    # Ambiguous matches
    if interactive:
        print(f"\n  Multiple matches for '{title}':")
        selected = show_movie_menu(results)
        if selected:
            return get_movie_details(selected.imdb_id)
        print(f"  Skipped (no selection)")
        return None
    else:
        # Non-interactive: skip ambiguous
        print(f"  Skipped: multiple matches, use --interactive to select")
        return None


def normalize_value(value: str) -> str:
    """Normalize value for comparison."""
    return value.lower().strip()


def add_property(
    node: "loglog.TreeNode", key: str, value: str, source: str | None = None
) -> None:
    """Add a new property to a movie node."""
    formatted_value = f"{value} ({source})" if source else value
    new_node = loglog.TreeNode(data=f"{key}: {formatted_value}")
    node.add_child(new_node)


def add_conflict_property(
    node: "loglog.TreeNode", key: str, imdb_value: str
) -> None:
    """Add IMDb value as separate property when conflict exists."""
    new_node = loglog.TreeNode(data=f"{key} (IMDb): {imdb_value}")
    node.add_child(new_node)


def add_cast_property(node: "loglog.TreeNode", cast: list[str]) -> None:
    """Add cast as a property with child nodes for each actor."""
    cast_node = loglog.TreeNode(data="Cast (IMDb):")
    for actor in cast:
        actor_node = loglog.TreeNode(data=actor)
        cast_node.add_child(actor_node)
    node.add_child(cast_node)


def enrich_movie_entry(
    entry: MovieEntry, details: MovieDetails, dry_run: bool = False
) -> list[str]:
    """
    Enrich a movie entry with IMDb data.

    Returns list of changes made (for reporting).
    Modifies entry.node in place unless dry_run.
    """
    changes = []

    # Mapping of property keys to (display_name, extractor)
    field_mapping = {
        "year": ("Year", lambda d: str(d.year) if d.year else None),
        "rating": ("Rating", lambda d: f"{d.rating}/10" if d.rating else None),
        "genres": ("Genres", lambda d: ", ".join(d.genres) if d.genres else None),
        "country": (
            "Country",
            lambda d: ", ".join(d.countries) if d.countries else None,
        ),
        "duration": ("Duration", lambda d: d.duration),
        "released": ("Released", lambda d: d.release_date),
        "director": ("Director", lambda d: d.director),
        "synopsis": ("Synopsis", lambda d: d.synopsis),
        "imdb id": ("IMDb ID", lambda d: d.imdb_id),
    }

    for prop_key, (display_name, extractor) in field_mapping.items():
        imdb_value = extractor(details)
        if not imdb_value:
            continue

        existing = entry.properties.get(prop_key)

        if existing is None:
            # Property doesn't exist - add it with IMDb source
            changes.append(f"  + {display_name}: {imdb_value} (IMDb)")
            if not dry_run:
                add_property(entry.node, display_name, imdb_value, source="IMDb")

        elif existing.source == "IMDb":
            # Already from IMDb - skip (don't update)
            pass

        else:
            # User-provided value exists
            if normalize_value(existing.value) != normalize_value(imdb_value):
                # Conflict - add IMDb value alongside
                changes.append(
                    f"  ! {display_name}: user='{existing.value}' vs IMDb='{imdb_value}'"
                )
                if not dry_run:
                    add_conflict_property(entry.node, display_name, imdb_value)

    # Handle Cast specially (list property)
    if details.cast and "cast" not in entry.properties:
        cast_display = details.cast[:5]  # Limit to 5 actors
        changes.append(f"  + Cast: {', '.join(cast_display)} (IMDb)")
        if not dry_run:
            add_cast_property(entry.node, cast_display)

    return changes


def save_movies_file(tree: "loglog.TreeNode", path: Path) -> None:
    """Write the updated tree back to the file."""
    expanded_path = path.expanduser().resolve()

    # Create backup first
    backup_path = expanded_path.with_suffix(".bak")
    if expanded_path.exists():
        shutil.copy2(expanded_path, backup_path)

    # Write new content
    with open(expanded_path, "w") as f:
        loglog.print_tree_to_file(tree, f)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load file
    try:
        tree = load_movies_file(args.file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Extract movie entries
    entries = extract_movie_entries(tree)
    if not entries:
        print("No movie entries found in file")
        sys.exit(0)

    print(f"Enriching movies in {args.file.expanduser()}...")
    if args.dry_run:
        print("(Dry run - no changes will be written)\n")
    else:
        print()

    # Process each movie
    enriched_count = 0
    skipped_count = 0

    for i, entry in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] {entry.title}")

        # Small delay to avoid rate limiting
        if i > 1:
            time.sleep(0.3)

        # Find IMDb match
        details = find_imdb_match(entry, args.interactive, args.verbose)
        if not details:
            skipped_count += 1
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
    print(f"\nSummary:")
    print(f"  Movies processed: {len(entries)}")
    print(f"  Movies enriched: {enriched_count}")
    print(f"  Movies skipped: {skipped_count}")

    # Write back
    if not args.dry_run and enriched_count > 0:
        save_movies_file(tree, args.file)
        print(f"\nChanges written to {args.file.expanduser()}")
        print(f"Backup saved to {args.file.expanduser().with_suffix('.bak')}")
    elif args.dry_run:
        print("\nDry run complete. Use without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
