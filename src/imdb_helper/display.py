"""Output formatting for JSON, console, and loglog formats."""

import json


def _imdb_url(imdb_id: str) -> str:
    """Generate IMDb URL from movie ID."""
    return f"https://www.imdb.com/title/{imdb_id}/"


def format_json(data: dict) -> str:
    """Format movie data as JSON."""
    output = data.copy()
    output["imdb_url"] = _imdb_url(data["imdb_id"])
    return json.dumps(output, indent=4)


def format_console(data: dict) -> str:
    """Format movie data for console display."""
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append(f"  {data['title']} ({data['year'] or 'N/A'})")
    lines.append(f"{'=' * 60}")
    lines.append(f"  IMDB Rating: {data['imdb_rating'] or 'N/A'}/10")
    lines.append(f"  Genres:      {', '.join(data['genres']) if data['genres'] else 'N/A'}")
    lines.append(f"  Country:     {', '.join(data['countries']) if data['countries'] else 'N/A'}")
    lines.append(f"  Duration:    {data['duration'] or 'N/A'}")
    lines.append(f"  Released:    {data['release_date'] or 'N/A'}")
    lines.append(f"  Director:    {data['director'] or 'N/A'}")
    lines.append(f"  Cast:        {', '.join(data['cast'][:5]) if data['cast'] else 'N/A'}")
    lines.append(f"  IMDb:        {_imdb_url(data['imdb_id'])}")
    lines.append("")
    lines.append("  Synopsis:")

    synopsis = data["synopsis"] or "No synopsis available."
    # Wrap long synopsis
    words = synopsis.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 58:
            lines.append(line)
            line = "  " + word
        else:
            line = line + " " + word if line != "  " else line + word
    if line.strip():
        lines.append(line)
    lines.append(f"{'=' * 60}\n")

    return "\n".join(lines)


def format_loglog(data: dict) -> str:
    """Format movie data in loglog format."""
    lines = [
        f"- {data['title']}",
        f"    - Year: {data['year'] or 'N/A'}",
        f"    - IMDB Rating: {data['imdb_rating'] or 'N/A'}/10",
        f"    - Genres: {', '.join(data['genres']) if data['genres'] else 'N/A'}",
        f"    - Country: {', '.join(data['countries']) if data['countries'] else 'N/A'}",
        f"    - Duration: {data['duration'] or 'N/A'}",
        f"    - Released: {data['release_date'] or 'N/A'}",
        f"    - Director: {data['director'] or 'N/A'}",
        f"    - Cast:",
    ]
    for actor in (data["cast"] or [])[:5]:
        lines.append(f"        - {actor}")
    lines.append(f"    - Synopsis: {data['synopsis'] or 'N/A'}")
    lines.append(f"    - IMDb: {_imdb_url(data['imdb_id'])}")
    return "\n".join(lines)
