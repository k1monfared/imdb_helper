"""Interactive terminal menu for movie selection."""

from simple_term_menu import TerminalMenu

from .models import MovieSearchResult


def _imdb_url(imdb_id: str) -> str:
    return f"https://www.imdb.com/title/{imdb_id}/"


def format_menu_entry(movie: MovieSearchResult) -> str:
    """Format a movie for menu display."""
    year = f"({movie.year})" if movie.year else ""
    link = _imdb_url(movie.imdb_id)
    return f"{movie.title} {year} - {link}".strip()


def show_movie_menu(movies: list[MovieSearchResult]) -> MovieSearchResult | None:
    """
    Display interactive menu for movie selection.

    Args:
        movies: List of movies to display

    Returns:
        Selected MovieSearchResult or None if cancelled
    """
    if not movies:
        return None

    menu_entries = [format_menu_entry(m) for m in movies]

    terminal_menu = TerminalMenu(
        menu_entries,
        title="Select a movie (ESC to cancel):",
    )

    selected_index = terminal_menu.show()

    if selected_index is None:
        return None
    return movies[selected_index]
