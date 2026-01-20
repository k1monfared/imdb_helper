"""Movie search and data retrieval using OMDb API."""

import os
from urllib.parse import quote

import requests

from .models import MovieDetails, MovieSearchResult


class SearchError(Exception):
    """Raised when movie search or retrieval fails."""

    pass


OMDB_API_URL = "http://www.omdbapi.com/"


def _get_api_key() -> str:
    """Get OMDb API key from environment variable."""
    api_key = os.environ.get("OMDB_API_KEY")
    if not api_key:
        raise SearchError(
            "OMDB_API_KEY environment variable not set. "
            "Get a free API key at https://www.omdbapi.com/apikey.aspx"
        )
    return api_key


def search_movies(query: str, max_results: int = 10) -> list[MovieSearchResult]:
    """
    Search for movies matching the query.

    Args:
        query: Movie name to search for
        max_results: Maximum number of results to return

    Returns:
        List of MovieSearchResult for menu display
    """
    api_key = _get_api_key()

    try:
        # OMDb search endpoint
        params = {"apikey": api_key, "s": query, "type": "movie"}
        response = requests.get(OMDB_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("Response") == "False":
            error = data.get("Error", "Unknown error")
            if "not found" in error.lower():
                return []
            raise SearchError(f"OMDb API error: {error}")

        search_results = []
        for item in data.get("Search", [])[:max_results]:
            # Fetch additional details for each result
            details = _fetch_movie_by_id(item["imdbID"], api_key)
            if details:
                search_results.append(_to_search_result(details))

        return search_results

    except requests.RequestException as e:
        raise SearchError(f"Network error: {e}") from e


def get_movie_details(imdb_id: str) -> MovieDetails:
    """
    Fetch complete movie details by IMDb ID.

    Args:
        imdb_id: The IMDb movie ID (e.g., "tt0133093")

    Returns:
        MovieDetails with all available information
    """
    api_key = _get_api_key()

    # Ensure imdb_id has the 'tt' prefix
    if not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"

    details = _fetch_movie_by_id(imdb_id, api_key)
    if not details:
        raise SearchError(f"Movie not found: {imdb_id}")

    return _to_movie_details(details)


def _fetch_movie_by_id(imdb_id: str, api_key: str) -> dict | None:
    """Fetch movie data by IMDb ID."""
    try:
        params = {"apikey": api_key, "i": imdb_id, "plot": "short"}
        response = requests.get(OMDB_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("Response") == "False":
            return None

        return data

    except requests.RequestException:
        return None


def should_skip_menu(
    query: str,
    results: list[MovieSearchResult],
    year: int | None = None,
    director: str | None = None,
) -> MovieSearchResult | None:
    """
    Determine if we can skip the interactive menu.

    Skip conditions:
    1. Only one result returned
    2. First result is exact title match (case-insensitive)
    3. Year and/or director provided and matches exactly one result

    Args:
        query: Original search query
        results: Search results to evaluate
        year: Optional year filter
        director: Optional director filter

    Returns:
        The auto-selected movie, or None if menu needed
    """
    if not results:
        return None

    # Condition 1: Only one result
    if len(results) == 1:
        return results[0]

    # Condition 2: Exact title match
    exact_matches = [r for r in results if r.title.lower() == query.lower()]
    if len(exact_matches) == 1:
        return exact_matches[0]

    # Condition 3: Additional filters narrow to one result
    filtered = results
    if year:
        filtered = [r for r in filtered if r.year == year]
    if director:
        filtered = [
            r
            for r in filtered
            if r.director and director.lower() in r.director.lower()
        ]

    if len(filtered) == 1:
        return filtered[0]

    return None  # Show menu


def _to_search_result(data: dict) -> MovieSearchResult:
    """Convert OMDb response to MovieSearchResult."""
    # Parse year (may be "2010" or "2010-2015" for series)
    year_str = data.get("Year", "")
    year = None
    if year_str:
        try:
            year = int(year_str.split("–")[0].split("-")[0])
        except ValueError:
            pass

    # Get cast preview (first 2 actors)
    actors = data.get("Actors", "")
    cast_preview = [a.strip() for a in actors.split(",")[:2]] if actors and actors != "N/A" else []

    # Get plot
    plot = data.get("Plot", "")
    synopsis_brief = None
    if plot and plot != "N/A":
        synopsis_brief = plot[:100] + "..." if len(plot) > 100 else plot

    # Get director
    director = data.get("Director", "")
    director = director if director and director != "N/A" else None

    return MovieSearchResult(
        imdb_id=data.get("imdbID", ""),
        title=data.get("Title", "Unknown"),
        year=year,
        director=director,
        cast_preview=cast_preview,
        synopsis_brief=synopsis_brief,
    )


def _to_movie_details(data: dict) -> MovieDetails:
    """Convert OMDb response to MovieDetails."""
    # Parse year
    year_str = data.get("Year", "")
    year = None
    if year_str:
        try:
            year = int(year_str.split("–")[0].split("-")[0])
        except ValueError:
            pass

    # Parse rating
    rating_str = data.get("imdbRating", "")
    rating = None
    if rating_str and rating_str != "N/A":
        try:
            rating = float(rating_str)
        except ValueError:
            pass

    # Parse genres
    genres_str = data.get("Genre", "")
    genres = [g.strip() for g in genres_str.split(",")] if genres_str and genres_str != "N/A" else []

    # Parse countries
    country_str = data.get("Country", "")
    countries = [c.strip() for c in country_str.split(",")] if country_str and country_str != "N/A" else []

    # Parse runtime
    runtime = data.get("Runtime", "")
    duration = runtime if runtime and runtime != "N/A" else None

    # Get director
    director = data.get("Director", "")
    director = director if director and director != "N/A" else None

    # Get cast
    actors = data.get("Actors", "")
    cast = [a.strip() for a in actors.split(",")] if actors and actors != "N/A" else []

    # Get plot
    plot = data.get("Plot", "")
    synopsis = plot if plot and plot != "N/A" else None

    # Get release date
    release_date = data.get("Released", "")
    release_date = release_date if release_date and release_date != "N/A" else None

    return MovieDetails(
        imdb_id=data.get("imdbID", ""),
        title=data.get("Title", "Unknown"),
        year=year,
        rating=rating,
        genres=genres,
        countries=countries,
        duration=duration,
        release_date=release_date,
        director=director,
        cast=cast,
        synopsis=synopsis,
    )
