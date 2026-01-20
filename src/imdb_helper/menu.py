"""Interactive terminal menu for movie selection."""

from simple_term_menu import TerminalMenu

from .models import MovieSearchResult


def format_menu_entry(movie: MovieSearchResult) -> str:
    """Format a movie for menu display."""
    year = f"({movie.year})" if movie.year else ""
    director = f"Dir: {movie.director}" if movie.director else ""
    cast = ", ".join(movie.cast_preview) if movie.cast_preview else ""

    parts = [f"{movie.title} {year}".strip()]
    if director:
        parts.append(director)
    if cast:
        parts.append(cast)

    return " | ".join(parts)


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

    def preview_command(selected_index: str) -> str:
        """Show synopsis in preview."""
        if selected_index is None or selected_index == "":
            return ""
        try:
            idx = int(selected_index)
            movie = movies[idx]
            return movie.synopsis_brief or "No synopsis available"
        except (ValueError, IndexError):
            return ""

    terminal_menu = TerminalMenu(
        menu_entries,
        title="Select a movie (ESC to cancel):",
        preview_command=preview_command,
        preview_size=0.3,
        preview_title="Synopsis",
    )

    selected_index = terminal_menu.show()

    if selected_index is None:
        return None
    return movies[selected_index]
