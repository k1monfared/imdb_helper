#!/usr/bin/env python3
"""Remove a specific property from all movie entries."""

import argparse
import shutil
import sys
from pathlib import Path

import loglog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove a property from all movie entries")
    parser.add_argument("property", help="Property name to remove (e.g., 'IMDb ID')")
    parser.add_argument(
        "-f", "--file", type=Path, default=Path("~/public/notes/movies"),
        help="Path to movies file",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Preview changes")
    return parser.parse_args()


def remove_property_from_tree(tree: "loglog.TreeNode", prop_name: str, dry_run: bool) -> int:
    """Remove property from all nodes recursively. Returns count removed."""
    count = 0
    prop_lower = prop_name.lower()

    def process_node(node: "loglog.TreeNode") -> None:
        nonlocal count
        to_remove = []

        for child in node.children:
            data = child.data.strip()
            if ":" in data:
                key = data.split(":")[0].strip().lower()
                # Match exact key or key with source annotation like "IMDb ID (IMDb)"
                if key == prop_lower or key.startswith(prop_lower + " ("):
                    to_remove.append(child)
                    count += 1
            # Recurse into children
            process_node(child)

        if not dry_run:
            for child in to_remove:
                node.children.remove(child)

    process_node(tree)
    return count


def main() -> None:
    args = parse_args()
    path = args.file.expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)

    tree = loglog.build_tree_from_file(str(path))

    print(f"Removing '{args.property}' from {path}...")
    if args.dry_run:
        print("(Dry run)\n")

    count = remove_property_from_tree(tree, args.property, args.dry_run)

    print(f"Found {count} '{args.property}' properties to remove")

    if not args.dry_run and count > 0:
        backup_path = path.with_suffix(".bak")
        shutil.copy2(path, backup_path)
        with open(path, "w") as f:
            loglog.print_tree_to_file(tree, f)
        print(f"Changes written to {path}")
        print(f"Backup saved to {backup_path}")
    elif args.dry_run:
        print("Dry run complete. Use without --dry-run to apply.")


if __name__ == "__main__":
    main()
