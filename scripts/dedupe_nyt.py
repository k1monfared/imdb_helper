#!/usr/bin/env python3
"""Remove movies from unwatched sections that are already in the watched list."""

import argparse
import shutil
import sys
from pathlib import Path

import loglog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove movies from unwatched sections that are already watched"
    )
    parser.add_argument(
        "-f", "--file", type=Path, default=Path("~/public/notes/movies"),
        help="Path to movies file",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview changes")
    return parser.parse_args()


def normalize_title(title: str) -> str:
    """Normalize a movie title for comparison."""
    # Remove common variations
    title = title.lower().strip()
    # Remove "the " prefix for matching
    if title.startswith("the "):
        title = title[4:]
    # Remove punctuation
    for char in ".,!?':;-":
        title = title.replace(char, "")
    return title


def find_section(tree: "loglog.TreeNode", name: str) -> "loglog.TreeNode | None":
    """Find a section by name (case-insensitive partial match)."""
    name_lower = name.lower()

    def search(node):
        for child in node.children:
            if name_lower in child.data.lower():
                return child
            result = search(child)
            if result:
                return result
        return None

    return search(tree)


def is_watched_section(node: "loglog.TreeNode") -> bool:
    """Check if a node is under the watched section."""
    return "watched" in node.data.lower()


def get_watched_titles(watched_section: "loglog.TreeNode") -> set[str]:
    """Extract all movie titles from the watched section (recursively)."""
    titles = set()

    def extract(node):
        for child in node.children:
            # Movie entries are todo items
            if child.type == "todo":
                title = child.data.strip()
                titles.add(normalize_title(title))
            # Also search subsections
            extract(child)

    extract(watched_section)
    return titles


def find_unwatched_duplicates(
    tree: "loglog.TreeNode",
    watched_section: "loglog.TreeNode",
    watched_titles: set[str],
) -> list[tuple["loglog.TreeNode", "loglog.TreeNode", str]]:
    """Find movies outside watched section that are already watched.

    Returns list of (movie_node, parent_node, section_path) tuples.
    """
    duplicates = []

    def walk(node, path: list[str], in_watched: bool):
        for child in node.children:
            # Check if we're entering/in the watched section
            child_in_watched = in_watched or child is watched_section

            if child.type == "todo" and not child_in_watched:
                title = child.data.strip()
                normalized = normalize_title(title)
                if normalized in watched_titles:
                    section = path[-1] if path else "root"
                    duplicates.append((child, node, section))
            else:
                # Recurse into subsections
                child_path = path + [child.data.strip()] if child.data.strip() else path
                walk(child, child_path, child_in_watched)

    walk(tree, [], False)
    return duplicates


def main():
    args = parse_args()
    path = args.file.expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    # Find watched section
    watched_section = find_section(tree, "watched")

    if not watched_section:
        print("Error: 'watched' section not found")
        sys.exit(1)

    # Get watched titles
    watched_titles = get_watched_titles(watched_section)
    print(f"Found {len(watched_titles)} movies in watched list")

    # Find duplicates in all other sections
    duplicates = find_unwatched_duplicates(tree, watched_section, watched_titles)
    print(f"Found {len(duplicates)} movies to remove\n")

    # Group by section for display
    by_section: dict[str, list] = {}
    for movie, parent, section in duplicates:
        by_section.setdefault(section, []).append((movie, parent))

    for section, movies in sorted(by_section.items()):
        print(f"  {section}:")
        for movie, _ in movies:
            print(f"    - {movie.data.strip()}")

    if not args.dry_run and duplicates:
        for movie, parent, _ in duplicates:
            if movie in parent.children:
                parent.children.remove(movie)

        # Save
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
