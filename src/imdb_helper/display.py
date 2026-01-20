"""Output formatting for console and loglog formats."""

from .models import MovieDetails


def display_movie_console(movie: MovieDetails) -> None:
    """Print movie details to console in human-readable format."""
    print(f"\n{'=' * 60}")
    print(f"  {movie.title} ({movie.year or 'N/A'})")
    print(f"{'=' * 60}")
    print(f"  Rating:    {movie.rating or 'N/A'}/10")
    print(f"  Genres:    {', '.join(movie.genres) if movie.genres else 'N/A'}")
    print(f"  Country:   {', '.join(movie.countries) if movie.countries else 'N/A'}")
    print(f"  Duration:  {movie.duration or 'N/A'}")
    print(f"  Released:  {movie.release_date or 'N/A'}")
    print(f"  Director:  {movie.director or 'N/A'}")
    print(f"  Cast:      {', '.join(movie.cast[:5]) if movie.cast else 'N/A'}")
    print()
    print(f"  Synopsis:")
    synopsis = movie.synopsis or "No synopsis available."
    # Wrap long synopsis
    words = synopsis.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 58:
            print(line)
            line = "  " + word
        else:
            line = line + " " + word if line != "  " else line + word
    if line.strip():
        print(line)
    print(f"{'=' * 60}\n")


def format_movie_loglog(movie: MovieDetails) -> str:
    """Format movie details in loglog format."""
    lines = [
        f"- {movie.title}",
        f"    - Year: {movie.year or 'N/A'}",
        f"    - Rating: {movie.rating or 'N/A'}/10",
        f"    - Genres: {', '.join(movie.genres) if movie.genres else 'N/A'}",
        f"    - Country: {', '.join(movie.countries) if movie.countries else 'N/A'}",
        f"    - Duration: {movie.duration or 'N/A'}",
        f"    - Released: {movie.release_date or 'N/A'}",
        f"    - Director: {movie.director or 'N/A'}",
        f"    - Cast:",
    ]
    for actor in (movie.cast or [])[:5]:
        lines.append(f"        - {actor}")
    lines.append(f"    - Synopsis: {movie.synopsis or 'N/A'}")
    return "\n".join(lines)
