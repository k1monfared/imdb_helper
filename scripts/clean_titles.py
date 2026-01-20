#!/usr/bin/env python3
"""Clean movie titles by extracting embedded metadata.

Handles patterns like:
- "Movie Title, Director Name | Countries, World Premiere"
- "Movie Title (2023)"
- "Movie Title, Director | Country, TIFF 2022"
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import loglog


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Clean movie titles by extracting embedded metadata"
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
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    return parser.parse_args()


def is_movie_entry(node: "loglog.TreeNode") -> bool:
    """Determine if a node represents a movie entry."""
    data = node.data.strip()
    if not data:
        return False
    if node.type == "todo":
        return True
    if data.endswith(":"):
        return False
    if ":" in data:
        colon_pos = data.index(":")
        if colon_pos < 20:
            return False
    if data.startswith("#") or data.startswith("//"):
        return False
    return True


def get_existing_property(node: "loglog.TreeNode", key: str) -> str | None:
    """Get value of existing property (case-insensitive)."""
    key_lower = key.lower()
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            prop_key = data.split(":")[0].strip().lower()
            if prop_key == key_lower:
                return data.split(":", 1)[1].strip()
    return None


def add_or_append_property(node: "loglog.TreeNode", key: str, value: str, dry_run: bool = False) -> str | None:
    """Add property or append to existing. Returns change description."""
    if not value:
        return None

    key_lower = key.lower()

    # Find existing property
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            prop_key = data.split(":")[0].strip().lower()
            if prop_key == key_lower:
                existing_value = data.split(":", 1)[1].strip()
                if existing_value:
                    # Check if value already present
                    if value.lower() in existing_value.lower():
                        return None
                    new_value = f"{existing_value}, {value}"
                    if not dry_run:
                        child.data = f"{key}: {new_value}"
                    return f"  + Appended to {key}: {value}"
                else:
                    if not dry_run:
                        child.data = f"{key}: {value}"
                    return f"  + Set {key}: {value}"

    # No existing property, add new one
    if not dry_run:
        new_node = loglog.TreeNode(data=f"{key}: {value}")
        node.add_child(new_node)
    return f"  + Added {key}: {value}"


def set_property_if_missing(node: "loglog.TreeNode", key: str, value: str, dry_run: bool = False) -> str | None:
    """Set property only if it doesn't exist. Returns change description."""
    if not value:
        return None

    existing = get_existing_property(node, key)
    if existing:
        return None

    if not dry_run:
        new_node = loglog.TreeNode(data=f"{key}: {value}")
        node.add_child(new_node)
    return f"  + Added {key}: {value}"


# Festival/premiere patterns to look for
FESTIVAL_PATTERNS = [
    r"World Premiere.*",
    r"North American Premiere.*",
    r"Canadian Premiere.*",
    r"International Premiere.*",
    r"Opening Night Film.*",
    r"TIFF \d{4}",
    r"Sundance \d{4}",
    r"Cannes \d{4}",
    r"Venice \d{4}",
    r"Berlin \d{4}",
]

# Country names to recognize
COUNTRIES = {
    "USA", "United States", "UK", "United Kingdom", "Canada", "France", "Germany",
    "Italy", "Spain", "Japan", "South Korea", "Korea", "China", "Australia",
    "Ireland", "Sweden", "Denmark", "Norway", "Finland", "Netherlands", "Belgium",
    "Greece", "Mexico", "Brazil", "Argentina", "India", "Russia", "Poland",
    "Czech Republic", "Hungary", "Austria", "Switzerland", "Portugal", "Turkey",
    "Iran", "Israel", "Egypt", "South Africa", "New Zealand", "Thailand",
    "Vietnam", "Indonesia", "Philippines", "Taiwan", "Hong Kong", "Singapore",
}


def is_country(text: str) -> bool:
    """Check if text looks like a country name."""
    text = text.strip()
    return text in COUNTRIES or text.upper() == text and len(text) <= 4


def is_festival_info(text: str) -> bool:
    """Check if text is festival/premiere information."""
    for pattern in FESTIVAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def parse_title_metadata(title: str) -> dict:
    """Parse a movie title and extract embedded metadata."""
    result = {
        "title": title,
        "director": None,
        "countries": [],
        "year": None,
        "festival": None,
    }

    # Extract year from end: "Movie (2023)"
    year_match = re.search(r"\s*\((\d{4})\)\s*$", title)
    if year_match:
        result["year"] = year_match.group(1)
        title = title[:year_match.start()].strip()

    # Check for pipe separator: "Title, Director | Countries, Premiere"
    if "|" in title:
        parts = title.split("|", 1)
        title_part = parts[0].strip()
        meta_part = parts[1].strip() if len(parts) > 1 else ""

        # Parse title part: may be "Title, Director" or just "Title"
        if "," in title_part:
            # Check if last comma-separated part looks like a director name
            comma_parts = [p.strip() for p in title_part.split(",")]

            # Last part might be director if it's a name (not a subtitle)
            potential_director = comma_parts[-1]
            # Director names are typically 2-3 words, not too long
            if (len(potential_director.split()) <= 4 and
                len(potential_director) < 40 and
                not any(c in potential_director for c in [":", "?", "!"])):
                result["director"] = potential_director
                title_part = ", ".join(comma_parts[:-1])

        result["title"] = title_part.rstrip(",").strip()

        # Parse metadata part: "Countries, Premiere Info"
        if meta_part:
            meta_items = [p.strip() for p in meta_part.split(",")]
            countries = []
            festival_parts = []

            for item in meta_items:
                if is_festival_info(item):
                    festival_parts.append(item)
                elif is_country(item):
                    countries.append(item)
                else:
                    # Could be part of festival info
                    festival_parts.append(item)

            if countries:
                result["countries"] = countries
            if festival_parts:
                result["festival"] = " ".join(festival_parts).strip()

    else:
        result["title"] = title.rstrip(",").strip()

    return result


def clean_movie_entry(node: "loglog.TreeNode", dry_run: bool = False) -> list[str]:
    """Clean a movie entry by extracting metadata from title. Returns changes."""
    changes = []
    original_title = node.data.strip()

    # Parse the title
    parsed = parse_title_metadata(original_title)

    # Check if anything was extracted
    if (parsed["title"] == original_title and
        not parsed["director"] and
        not parsed["countries"] and
        not parsed["year"] and
        not parsed["festival"]):
        return []

    # Update title if changed
    if parsed["title"] != original_title:
        changes.append(f"  Title: \"{original_title}\" -> \"{parsed['title']}\"")
        if not dry_run:
            node.data = parsed["title"]

    # Add extracted metadata
    if parsed["year"]:
        change = set_property_if_missing(node, "Year", parsed["year"], dry_run)
        if change:
            changes.append(change)

    if parsed["director"]:
        change = set_property_if_missing(node, "Director", parsed["director"], dry_run)
        if change:
            changes.append(change)

    if parsed["countries"]:
        country_str = ", ".join(parsed["countries"])
        change = set_property_if_missing(node, "Country", country_str, dry_run)
        if change:
            changes.append(change)

    if parsed["festival"]:
        change = add_or_append_property(node, "Recommender", parsed["festival"], dry_run)
        if change:
            changes.append(change)

    return changes


def process_tree(tree: "loglog.TreeNode", dry_run: bool = False, verbose: bool = False) -> tuple[int, int]:
    """Process tree and clean titles. Returns (movies_checked, movies_cleaned)."""
    movies_checked = 0
    movies_cleaned = 0

    def process_node(node: "loglog.TreeNode") -> None:
        nonlocal movies_checked, movies_cleaned

        for child in node.children:
            if is_movie_entry(child):
                movies_checked += 1
                title = child.data.strip()

                changes = clean_movie_entry(child, dry_run)
                if changes:
                    print(f"[{movies_checked}] {title}")
                    for change in changes:
                        print(change)
                    movies_cleaned += 1
                elif verbose:
                    print(f"[{movies_checked}] {title} - no changes")
            else:
                process_node(child)

    process_node(tree)
    return movies_checked, movies_cleaned


def main() -> None:
    """Main entry point."""
    args = parse_args()

    path = args.file.expanduser().resolve()
    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    print(f"Cleaning movie titles in {path}...")
    if args.dry_run:
        print("(Dry run - no changes will be written)\n")
    else:
        print()

    movies_checked, movies_cleaned = process_tree(tree, args.dry_run, args.verbose)

    print(f"\nSummary:")
    print(f"  Movies checked: {movies_checked}")
    print(f"  Movies cleaned: {movies_cleaned}")

    if not args.dry_run and movies_cleaned > 0:
        backup_path = path.with_suffix(".bak")
        shutil.copy2(path, backup_path)

        with open(path, "w") as f:
            loglog.print_tree_to_file(tree, f)

        print(f"\nChanges written to {path}")
        print(f"Backup saved to {backup_path}")
    elif args.dry_run:
        print("\nDry run complete. Use without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
