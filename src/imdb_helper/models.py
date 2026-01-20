"""Data models for movie information."""

from dataclasses import dataclass


@dataclass
class MovieSearchResult:
    """Represents a movie from search results (for menu display)."""

    imdb_id: str
    title: str
    year: int | None
    director: str | None
    cast_preview: list[str]  # First 2 main characters
    synopsis_brief: str | None  # Short synopsis for menu


@dataclass
class MovieDetails:
    """Complete movie details for final display."""

    imdb_id: str
    title: str
    year: int | None
    rating: float | None
    genres: list[str]
    countries: list[str]
    duration: str | None  # e.g., "142 min"
    release_date: str | None
    director: str | None
    cast: list[str]
    synopsis: str | None
