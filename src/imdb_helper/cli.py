"""CLI entry point and argument parsing."""

import argparse
import sys

from .display import display_movie_console, format_movie_loglog
from .menu import show_movie_menu
from .search import SearchError, get_movie_details, search_movies, should_skip_menu


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="imdb",
        description="Quick IMDb movie lookup tool",
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="Movie name to search for",
    )
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        help="Filter by release year",
    )
    parser.add_argument(
        "-d",
        "--director",
        type=str,
        help="Filter by director name",
    )
    parser.add_argument(
        "-l",
        "--loglog",
        action="store_true",
        help="Output in loglog format",
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
        # Search for movies
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
            selected = should_skip_menu(query, results, args.year, args.director)

        # Show menu if needed
        if selected is None:
            # Apply filters for menu display if provided
            filtered_results = results
            if args.year:
                filtered_results = [r for r in results if r.year == args.year]
            if args.director:
                filtered_results = [
                    r
                    for r in filtered_results
                    if r.director and args.director.lower() in r.director.lower()
                ]

            if not filtered_results:
                print("No movies match the specified filters.", file=sys.stderr)
                sys.exit(1)

            selected = show_movie_menu(filtered_results)

        if selected is None:
            print("No movie selected.", file=sys.stderr)
            sys.exit(0)

        # Fetch and display full details
        print(f"Fetching details for '{selected.title}'...", file=sys.stderr)
        details = get_movie_details(selected.imdb_id)

        if args.loglog:
            print(format_movie_loglog(details))
        else:
            display_movie_console(details)

    except SearchError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
