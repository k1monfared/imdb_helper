"""Data models for movie information."""

from dataclasses import asdict, dataclass


@dataclass
class MovieSearchResult:
    """Represents a movie from search results (for menu display)."""

    imdb_id: str
    title: str
    year: int | None


@dataclass
class MovieDetails:
    """Complete movie details for final display."""

    imdb_id: str
    title: str
    year: int | None
    imdb_rating: float | None
    genres: list[str]
    countries: list[str]
    duration: str | None  # e.g., "142 min"
    release_date: str | None
    director: str | None
    cast: list[str]
    synopsis: str | None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
