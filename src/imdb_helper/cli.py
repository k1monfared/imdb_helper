"""CLI entry point and argument parsing."""

import argparse
import sys

from .display import format_console, format_json, format_loglog
from .menu import show_movie_menu
from .search import (
    SearchError,
    detect_imdb_id,
    get_movie_details,
    sanitize_query,
    search_movies,
    should_skip_menu,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="imdb",
        description="Quick IMDb movie lookup tool",
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="Movie name, IMDb ID (e.g. tt0133093), or IMDb URL to look up",
    )
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        help="Filter by release year",
    )

    # Output format options (mutually exclusive)
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    format_group.add_argument(
        "-t",
        "--text",
        action="store_true",
        help="Output in plain text format",
    )
    format_group.add_argument(
        "-l",
        "--loglog",
        action="store_true",
        help="Output in loglog format (default)",
    )

    parser.add_argument(
        "-n",
        "--no-menu",
        action="store_true",
        help="Auto-select first result (no interactive menu)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    query = " ".join(args.query)

    try:
        # Check if query is an IMDb ID or URL
        imdb_id = detect_imdb_id(query)

        if imdb_id:
            print(f"Fetching details for '{imdb_id}'...", file=sys.stderr)
            details = get_movie_details(imdb_id)
        else:
            query = sanitize_query(query)
            print(f"Searching for '{query}'...", file=sys.stderr)
            results = search_movies(query)

            if not results:
                print(f"No movies found for '{query}'", file=sys.stderr)
                sys.exit(1)

            # Check if we can skip the menu
            selected = None
            if args.no_menu:
                selected = results[0]
            else:
                selected = should_skip_menu(query, results, args.year)

            # Show menu if needed
            if selected is None:
                filtered_results = results
                if args.year:
                    filtered_results = [r for r in results if r.year == args.year]

                if not filtered_results:
                    print("No movies match the specified filters.", file=sys.stderr)
                    sys.exit(1)

                selected = show_movie_menu(filtered_results)

            if selected is None:
                print("No movie selected.", file=sys.stderr)
                sys.exit(0)

            print(f"Fetching details for '{selected.title}'...", file=sys.stderr)
            details = get_movie_details(selected.imdb_id)

        # Convert to dict (JSON) as intermediate format
        data = details.to_dict()

        # Output in requested format
        if args.json:
            print(format_json(data))
        elif args.text:
            print(format_console(data))
        else:
            # Default is loglog (also triggered by -l)
            print(format_loglog(data))

    except SearchError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
