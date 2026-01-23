#!/usr/bin/env python3
"""Find and merge duplicate movies in the movies file.

Features:
- Finds duplicate movies by normalized title
- Infers "recommended by" from parent section names
- Merges recommenders from duplicates
- Keeps the entry with most information
- Can preview or apply changes
"""

import argparse
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import loglog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find and merge duplicate movies")
    parser.add_argument(
        "-f", "--file", type=Path, default=Path("~/public/notes/movies"),
        help="Path to movies file",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview changes only")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--report-only", action="store_true",
        help="Only report duplicates, don't modify anything",
    )
    return parser.parse_args()


def normalize_title(title: str) -> str:
    """Normalize a movie title for comparison."""
    # Remove common prefixes/suffixes
    title = title.strip()

    # Remove leading "The " for comparison
    if title.lower().startswith("the "):
        title = title[4:]

    # Remove trailing year in parentheses like "(2023)"
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)

    # Remove trailing slashes and extra whitespace
    title = title.rstrip('/ ')

    # Normalize unicode and case
    title = title.lower()

    # Remove special characters for fuzzy matching
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def get_property(node: "loglog.TreeNode", key: str) -> str | None:
    """Get a property value from a movie node."""
    key_lower = key.lower()
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip().lower()
            # Handle variations like "recommender", "Recommmender" (typo)
            if k == key_lower or (key_lower == "recommender" and k.startswith("recomm")):
                return data.split(":", 1)[1].strip()
    return None


def get_all_properties(node: "loglog.TreeNode") -> dict[str, str]:
    """Get all properties from a movie node."""
    props = {}
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip()
            v = data.split(":", 1)[1].strip()
            props[k.lower()] = v
    return props


def count_properties(node: "loglog.TreeNode") -> int:
    """Count the number of properties a movie has."""
    count = 0
    for child in node.children:
        if ":" in child.data:
            count += 1
        # Count nested items too (like cast)
        count += len(child.children)
    return count


def get_recommenders(node: "loglog.TreeNode") -> list[str]:
    """Extract all recommender names from a movie node."""
    recommenders = []

    for child in node.children:
        data = child.data.strip().lower()

        # Check various recommender property names
        if data.startswith(("recommender:", "recommmender:", "recommended by:")):
            value = child.data.split(":", 1)[1].strip()
            if value:
                recommenders.append(value)

    return recommenders


def infer_section_recommender(path: list[str], verbose: bool = False) -> str | None:
    """
    Check the section path to find a parent section that looks like a recommender.

    Examples of recommender sections:
    - "TIFF 2023"
    - "Sundance 2022"
    - "Person Name"
    """
    # Known section patterns that are NOT recommenders
    non_recommender_patterns = [
        r"^watched",
        r"^to watch",
        r"^I highly recommend",
        r"^I think it",
        r"^interesting",
        r"^meh",
        r"^bad",
        r"^horror",
        r"^documentary",
        r"^animation",
        r"^nyt\s+\d+",  # NYT 2025 etc
    ]

    # Known recommender patterns
    recommender_patterns = [
        r"^tiff\s+\d+",  # TIFF 2023
        r"^sundance\s+\d+",  # Sundance 2022
        r"^[A-Z][a-z]+\s+\d{4}$",  # Festival patterns
    ]

    # Check path from most specific (last) to root (first)
    for section_name in reversed(path):
        section_lower = section_name.lower()

        # Skip non-recommender sections
        is_non_recommender = any(
            re.match(pat, section_lower) for pat in non_recommender_patterns
        )
        if is_non_recommender:
            continue

        # Check if it matches recommender patterns
        is_recommender = any(
            re.match(pat, section_lower) for pat in recommender_patterns
        )

        if is_recommender:
            return section_name

    return None


@dataclass
class MovieEntry:
    """Represents a movie entry with its metadata."""
    node: "loglog.TreeNode"
    parent: "loglog.TreeNode"  # Parent node for removal
    title: str
    normalized_title: str
    properties: dict[str, str]
    recommenders: list[str]
    inferred_recommender: str | None
    property_count: int
    path: list[str]  # Section path to this movie
    file_position: int = 0  # Order in file (for tie-breaking)

    def all_recommenders(self) -> set[str]:
        """Get all recommenders including inferred ones."""
        recs = set(self.recommenders)
        if self.inferred_recommender:
            recs.add(self.inferred_recommender)
        return recs


def get_watched_category_priority(path: list[str]) -> tuple[int, int]:
    """
    Determine if entry is watched and its recommendation category priority.

    Returns (is_watched, category_priority).
    - is_watched: 1 if in watched section, 0 otherwise
    - category_priority: 0-4 based on recommendation category (higher = better)
    """
    path_lower = " > ".join(path).lower()

    # Check if in watched section
    is_watched = 1 if "watched" in path_lower else 0

    # Determine category priority within watched
    category_priority = 0  # Default (unwatched or uncategorized)
    if is_watched:
        if "i highly recommend" in path_lower:
            category_priority = 4
        elif "i recommend" in path_lower:
            category_priority = 3
        elif "i moderate" in path_lower or "interesting" in path_lower:
            category_priority = 2
        elif "i highly discourage" in path_lower or "meh" in path_lower:
            category_priority = 1
        else:
            category_priority = 0  # Watched but not in a specific category

    return (is_watched, category_priority)


def get_section_path(ancestors: list["loglog.TreeNode"]) -> list[str]:
    """Get the path of section names from the ancestors list."""
    path = []
    for node in ancestors:
        if node.data.strip():
            path.append(node.data.strip().rstrip(":"))
    return path


def extract_movies(tree: "loglog.TreeNode", verbose: bool = False) -> list[MovieEntry]:
    """Extract all movie entries from the tree."""
    movies = []
    position_counter = [0]  # Use list for mutable closure

    def is_movie_entry(node: "loglog.TreeNode") -> bool:
        """Check if a node looks like a movie entry."""
        if node.type != "todo":
            return False

        data = node.data.strip()
        if not data:
            return False

        # Skip if it looks like a property or section header
        if ":" in data and data.index(":") < 20:
            return False

        return True

    def walk(node: "loglog.TreeNode", ancestors: list["loglog.TreeNode"]):
        for child in node.children:
            if is_movie_entry(child):
                position_counter[0] += 1
                title = child.data.strip().rstrip("/ ")
                path = get_section_path(ancestors)
                movies.append(MovieEntry(
                    node=child,
                    parent=node,  # Track parent for removal
                    title=title,
                    normalized_title=normalize_title(title),
                    properties=get_all_properties(child),
                    recommenders=get_recommenders(child),
                    inferred_recommender=infer_section_recommender(path, verbose),
                    property_count=count_properties(child),
                    path=path,
                    file_position=position_counter[0],
                ))
            else:
                walk(child, ancestors + [child])

    walk(tree, [])
    return movies


def find_duplicates(movies: list[MovieEntry]) -> dict[str, list[MovieEntry]]:
    """Group movies by normalized title to find duplicates."""
    by_title = defaultdict(list)
    for movie in movies:
        by_title[movie.normalized_title].append(movie)

    # Only return groups with duplicates
    return {title: entries for title, entries in by_title.items() if len(entries) > 1}


def add_property(node: "loglog.TreeNode", key: str, value: str) -> None:
    """Add a property to a movie node."""
    new_node = loglog.TreeNode(data=f"{key}: {value}")
    node.add_child(new_node)


def remove_property(node: "loglog.TreeNode", key: str) -> bool:
    """Remove a property from a movie node. Returns True if removed."""
    key_lower = key.lower()
    for i, child in enumerate(node.children):
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip().lower()
            # Handle variations of recommender
            if k == key_lower or (key_lower in ("recommender", "recommended by") and k.startswith("recomm")):
                node.children.pop(i)
                return True
    return False


def update_or_add_property(node: "loglog.TreeNode", key: str, value: str) -> None:
    """Update existing property or add new one."""
    key_lower = key.lower()
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip().lower()
            if k == key_lower or (key_lower in ("recommender", "recommended by") and k.startswith("recomm")):
                child.data = f"{key}: {value}"
                return
    # Not found - add new
    add_property(node, key, value)


def get_property_with_children(node: "loglog.TreeNode", key: str) -> tuple[str | None, list[str]]:
    """Get a property value and any child items (for multi-line values like reviews)."""
    key_lower = key.lower()
    for child in node.children:
        data = child.data.strip()
        if ":" in data:
            k = data.split(":")[0].strip().lower()
            if k == key_lower:
                value = data.split(":", 1)[1].strip()
                # Get any child items (for multi-line reviews)
                children = [c.data.strip() for c in child.children if c.data.strip()]
                return (value, children)
    return (None, [])


def merge_recommenders(entries: list[MovieEntry]) -> set[str]:
    """Collect all recommenders from a list of duplicate entries."""
    all_recs = set()
    for entry in entries:
        all_recs.update(entry.all_recommenders())
    return all_recs


def collect_all_reviews(entries: list[MovieEntry]) -> list[str]:
    """Collect all unique reviews from a list of entries."""
    reviews = []
    seen = set()

    for entry in entries:
        # Get review from properties
        value, children = get_property_with_children(entry.node, "review")

        if value and value not in seen:
            reviews.append(value)
            seen.add(value)

        # Also check children (multi-line reviews)
        for child_text in children:
            if child_text and child_text not in seen:
                reviews.append(child_text)
                seen.add(child_text)

    return reviews


def merge_all_properties(
    best: MovieEntry,
    others: list[MovieEntry],
    dry_run: bool = False
) -> dict[str, list[str]]:
    """
    Merge properties from other entries into best entry.

    Rules:
    - recommender: combine with comma if different
    - review: if multiple different, keep as sub-items
    - all others: if different, keep both; if same, keep one

    Returns dict of property_key -> list of changes made.
    """
    changes = {}
    all_entries = [best] + others

    # Collect all properties from all entries
    all_props: dict[str, list[str]] = defaultdict(list)
    for entry in all_entries:
        for key, value in entry.properties.items():
            if value and value not in all_props[key]:
                all_props[key].append(value)

    # Handle recommenders specially
    recommender_keys = {"recommender", "recommended by", "recommmender"}
    all_recommenders: set[str] = set()
    for entry in all_entries:
        all_recommenders.update(entry.all_recommenders())

    if all_recommenders:
        existing_recs = best.all_recommenders()
        merged_recs = ", ".join(sorted(all_recommenders))

        if all_recommenders != existing_recs:
            changes["recommender"] = [f"Merged: {merged_recs}"]
            if not dry_run:
                # Remove existing recommender properties
                for key in recommender_keys:
                    remove_property(best.node, key)
                # Add merged recommender
                add_property(best.node, "recommended by", merged_recs)

    # Handle reviews specially
    all_reviews = collect_all_reviews(all_entries)
    if len(all_reviews) > 1:
        changes["review"] = [f"Merged {len(all_reviews)} reviews as sub-items"]
        if not dry_run:
            # Remove existing review
            remove_property(best.node, "review")
            # Create review node with sub-items
            review_node = loglog.TreeNode(data="review:")
            for review_text in all_reviews:
                sub_node = loglog.TreeNode(data=review_text)
                review_node.add_child(sub_node)
            best.node.add_child(review_node)

    # Handle other properties
    skip_keys = recommender_keys | {"review"}
    for key, values in all_props.items():
        if key in skip_keys:
            continue

        existing = best.properties.get(key)
        unique_values = list(dict.fromkeys(values))  # Preserve order, remove dupes

        if len(unique_values) == 1:
            # All same value - ensure it exists on best entry
            if not existing and not dry_run:
                add_property(best.node, key, unique_values[0])
                changes[key] = [f"Added: {unique_values[0]}"]
        else:
            # Multiple different values - keep all
            changes[key] = [f"Merged {len(unique_values)} values"]
            if not dry_run:
                # Remove existing property
                remove_property(best.node, key)
                # Add all unique values
                for value in unique_values:
                    add_property(best.node, key, value)

    return changes


def select_best_entry(entries: list[MovieEntry]) -> MovieEntry:
    """Select the highest-priority entry to keep.

    Priority order:
    1. Watched entries over unwatched
    2. Within watched: "I highly recommend" > "I recommend" > etc.
    3. Earlier position in file (lower file_position = higher priority)
    """
    def priority_score(entry: MovieEntry) -> tuple:
        is_watched, category_priority = get_watched_category_priority(entry.path)
        # Use negative file_position so lower position = higher score
        return (is_watched, category_priority, -entry.file_position)

    return max(entries, key=priority_score)


def process_duplicates(
    duplicates: dict[str, list[MovieEntry]],
    dry_run: bool = True,
    verbose: bool = False
) -> list[dict]:
    """Process duplicates: merge recommenders, mark for removal."""
    changes = []

    for norm_title, entries in duplicates.items():
        # Select best entry to keep
        best = select_best_entry(entries)
        others = [e for e in entries if e is not best]

        # Collect all recommenders
        all_recommenders = merge_recommenders(entries)
        existing_recommenders = best.all_recommenders()
        new_recommenders = all_recommenders - existing_recommenders

        change = {
            "normalized_title": norm_title,
            "keep": best,
            "remove": others,
            "add_recommenders": list(new_recommenders),
        }
        changes.append(change)

        # Apply changes if not dry run
        if not dry_run:
            # Add missing recommenders to best entry
            for rec in new_recommenders:
                add_property(best.node, "recommended by", rec)

            # Remove duplicate entries from tree
            for entry in others:
                if entry.parent and entry.node in entry.parent.children:
                    entry.parent.children.remove(entry.node)

    return changes


def print_report(
    duplicates: dict[str, list[MovieEntry]],
    changes: list[dict],
    verbose: bool = False
):
    """Print a report of duplicates and planned changes."""
    print(f"\n{'='*60}")
    print(f"DUPLICATE MOVIES REPORT")
    print(f"{'='*60}\n")

    print(f"Found {len(duplicates)} sets of duplicate movies:\n")

    for change in changes:
        norm_title = change["normalized_title"]
        keep = change["keep"]
        remove = change["remove"]
        add_recs = change["add_recommenders"]

        print(f"  {keep.title}")
        print(f"    Normalized: {norm_title}")
        print(f"    Keep: {keep.path[-1] if keep.path else 'root'} ({keep.property_count} properties)")

        if keep.all_recommenders():
            print(f"    Existing recommenders: {', '.join(keep.all_recommenders())}")

        for entry in remove:
            print(f"    Remove: {entry.path[-1] if entry.path else 'root'} ({entry.property_count} properties)")
            if entry.all_recommenders():
                print(f"      - Recommenders to merge: {', '.join(entry.all_recommenders())}")

        if add_recs:
            print(f"    New recommenders to add: {', '.join(add_recs)}")

        print()


def main():
    args = parse_args()
    path = args.file.expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    # Load file
    tree = loglog.build_tree_from_file(str(path))

    # Extract movies
    print(f"Scanning {path}...")
    movies = extract_movies(tree, args.verbose)
    print(f"Found {len(movies)} movies total")

    # Find duplicates
    duplicates = find_duplicates(movies)

    if not duplicates:
        print("No duplicates found!")
        sys.exit(0)

    # Process and report
    changes = process_duplicates(
        duplicates,
        dry_run=(args.dry_run or args.report_only),
        verbose=args.verbose
    )

    print_report(duplicates, changes, args.verbose)

    if args.report_only:
        print("Report only mode - no changes made.")
        sys.exit(0)

    if args.dry_run:
        print("Dry run - no changes written.")
        print("Run without --dry-run to apply changes.")
        sys.exit(0)

    # Apply changes
    print(f"\nApplying changes...")
    changes = process_duplicates(duplicates, dry_run=False, verbose=args.verbose)

    # Save file
    backup_path = path.with_suffix(".bak")
    shutil.copy2(path, backup_path)

    with open(path, "w") as f:
        loglog.print_tree_to_file(tree, f)

    print(f"Changes written to {path}")
    print(f"Backup saved to {backup_path}")

    # Summary
    total_removed = sum(len(c["remove"]) for c in changes)
    total_recs_added = sum(len(c["add_recommenders"]) for c in changes)
    print(f"\nSummary:")
    print(f"  Duplicate sets processed: {len(changes)}")
    print(f"  Entries removed: {total_removed}")
    print(f"  Recommenders merged: {total_recs_added}")


if __name__ == "__main__":
    main()
