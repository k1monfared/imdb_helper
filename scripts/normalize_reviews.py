#!/usr/bin/env python3
"""Normalize review entries in a loglog movies file.

Finds long text entries without a key and converts them to 'review:' format.
"""

import argparse
import shutil
import sys
from pathlib import Path

import loglog

# Minimum length to consider as a review
MIN_REVIEW_LENGTH = 50


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Normalize review entries in a loglog movies file"
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


def is_unlabeled_review(node: "loglog.TreeNode") -> bool:
    """Check if a node is a long text without a property key (likely a review)."""
    data = node.data.strip()
    if not data:
        return False

    # Already has a key
    if ":" in data:
        colon_pos = data.index(":")
        # If colon is early, it's a property
        if colon_pos < 30:
            return False

    # Check length - reviews are typically long
    if len(data) < MIN_REVIEW_LENGTH:
        return False

    return True


def normalize_movie_reviews(node: "loglog.TreeNode", dry_run: bool = False) -> list[str]:
    """Normalize reviews in a movie entry. Returns list of changes."""
    changes = []

    for child in node.children:
        if is_unlabeled_review(child):
            old_data = child.data.strip()
            preview = old_data[:60] + "..." if len(old_data) > 60 else old_data
            changes.append(f"  Converting to review: \"{preview}\"")

            if not dry_run:
                child.data = f"review: {old_data}"

    return changes


def process_tree(tree: "loglog.TreeNode", dry_run: bool = False, verbose: bool = False) -> tuple[int, int]:
    """Process tree and normalize reviews. Returns (movies_checked, reviews_normalized)."""
    movies_checked = 0
    reviews_normalized = 0

    def process_node(node: "loglog.TreeNode") -> None:
        nonlocal movies_checked, reviews_normalized

        for child in node.children:
            if is_movie_entry(child):
                movies_checked += 1
                title = child.data.strip()

                changes = normalize_movie_reviews(child, dry_run)
                if changes:
                    print(f"[{movies_checked}] {title}")
                    for change in changes:
                        print(change)
                    reviews_normalized += len(changes)
                elif verbose:
                    print(f"[{movies_checked}] {title} - no changes")
            else:
                # Not a movie, search its children
                process_node(child)

    process_node(tree)
    return movies_checked, reviews_normalized


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load file
    path = args.file.expanduser().resolve()
    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    print(f"Normalizing reviews in {path}...")
    if args.dry_run:
        print("(Dry run - no changes will be written)\n")
    else:
        print()

    movies_checked, reviews_normalized = process_tree(tree, args.dry_run, args.verbose)

    print(f"\nSummary:")
    print(f"  Movies checked: {movies_checked}")
    print(f"  Reviews normalized: {reviews_normalized}")

    if not args.dry_run and reviews_normalized > 0:
        # Create backup
        backup_path = path.with_suffix(".bak")
        shutil.copy2(path, backup_path)

        # Write updated tree
        with open(path, "w") as f:
            loglog.print_tree_to_file(tree, f)

        print(f"\nChanges written to {path}")
        print(f"Backup saved to {backup_path}")
    elif args.dry_run:
        print("\nDry run complete. Use without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
