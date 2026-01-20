# IMDb Helper

A command-line tool for quick IMDb movie lookups using the OMDb API.

## Features

- Search for movies by title with an interactive terminal menu
- Filter results by year or director
- Automatic movie selection when the query is unambiguous
- Display movie details including rating, genre, duration, release date, director, cast, and synopsis
- Multiple output formats: console (default), JSON, and loglog

## Requirements

- Python 3.9 or higher
- An OMDb API key (free tier available at https://www.omdbapi.com/apikey.aspx)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd imdb_helper

# Install the package
pip install .

# Or install in development mode
pip install -e .
```

## Getting an OMDb API Key

1. Go to https://www.omdbapi.com/apikey.aspx
2. Select "FREE! (1,000 daily limit)" for the free tier
3. Enter your email address and a description (e.g., "personal movie lookup")
4. Click "Submit"
5. Check your email for the API key (check spam folder if not received)
6. Click the activation link in the email to activate your key

### Rate Limits

| Plan | Daily Requests | Cost |
|------|----------------|------|
| Free | 1,000 | $0 |
| Patron | 100,000 | $1/month |

The free tier is sufficient for personal use. If you exceed the daily limit, requests will fail until the next day (resets at midnight UTC).

## Configuration

Set your OMDb API key as an environment variable:

```bash
export OMDB_API_KEY="your_api_key_here"
```

Add this to your shell profile (`.bashrc`, `.zshrc`, etc.) for persistence.

## Usage

### Basic Search

```bash
imdb "The Matrix"
```

This searches for "The Matrix" and displays an interactive menu if multiple results are found. Use arrow keys to navigate and Enter to select.

### Filter by Year

```bash
imdb "The Matrix" -y 1999
```

### Filter by Director

```bash
imdb "Inception" -d "Christopher Nolan"
```

### Skip Interactive Menu

```bash
imdb "The Matrix" -n
```

Automatically selects the first result without showing the menu.

### Output Formats

Console output (default):
```bash
imdb "The Matrix"
```

JSON output:
```bash
imdb "The Matrix" -j
```

Loglog format:
```bash
imdb "The Matrix" -l
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `query` | Movie name to search for (required) |
| `-y, --year` | Filter by release year |
| `-d, --director` | Filter by director name |
| `-j, --json` | Output in JSON format |
| `-l, --loglog` | Output in loglog format |
| `-n, --no-menu` | Auto-select first result |

## Output Fields

The tool retrieves and displays the following information:

- Title and year
- IMDb rating (out of 10)
- Genres
- Countries
- Duration
- Release date
- Director
- Main cast
- IMDb link
- Synopsis

## Example Output

Console format:
```
============================================================
  The Matrix (1999)
============================================================
  Rating:    8.7/10
  Genres:    Action, Sci-Fi
  Country:   United States, Australia
  Duration:  136 min
  Released:  31 Mar 1999
  Director:  Lana Wachowski, Lilly Wachowski
  Cast:      Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss
  IMDb:      https://www.imdb.com/title/tt0133093/

  Synopsis:
  When a beautiful stranger leads computer hacker Neo to a
  forbidding underworld, he discovers the shocking truth...
============================================================
```

## Dependencies

- `requests` - HTTP library for API calls
- `simple-term-menu` - Interactive terminal menu

## License

See LICENSE file for details.
