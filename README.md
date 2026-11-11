# RSS Reader

English | [Русский](README.ru.md)

A self-hosted RSS/Atom news aggregator with a FastAPI backend, SQLite database, and Jinja2 frontend. Users can add their own RSS/Atom feeds, read articles from multiple sources in a single timeline, mark items as read or favorite, and search across publications — all without a separate frontend build step.

## Badges

[![Python version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests: GitHub Actions](https://img.shields.io/badge/tests-GitHub%20Actions-lightgrey)](.github/workflows/tests.yml)

## Preview

The application renders a single-page interface: a sidebar with the source list and statistics, a central area with article cards, and a top bar with search and refresh controls. Dark and light themes adapt to system preferences. The layout is responsive for desktop and mobile.

## Features

- Add RSS/Atom feeds by URL with automatic validation of the feed format
- View a unified feed of articles from all added sources
- Filter articles by source, unread-only, or favorites-only
- Search by article title, summary, or source name
- Mark articles as read / unread and add to / remove from favorites
- Open the original article in a new browser tab
- Paginated article list so large feeds do not load all at once
- Refresh a single source or all sources with one click
- Statistics panel: source count, article count, unread count, favorite count, last fetch time
- Dark and light themes, adapting to system preferences
- Responsive layout for desktop and mobile
- REST API with interactive Swagger documentation at `/docs`
- SSRF protection when loading user-provided feed URLs (HTTP/HTTPS only, private/loopback/reserved addresses blocked, redirects capped, download size and timeout limited)

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Core application |
| FastAPI | Web framework and REST API |
| SQLAlchemy 2.x | ORM |
| SQLite | Local database |
| feedparser | RSS/Atom parsing |
| httpx | HTTP client for fetching feeds |
| Jinja2 | HTML templates |
| pytest | Automated testing |

## Architecture

```
RSS Reader/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # SQLAlchemy engine and session
│   ├── models/
│   │   └── __init__.py      # ORM models: Feed, Article
│   ├── schemas/
│   │   └── __init__.py      # Pydantic request/response schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── feeds.py         # Feed endpoints (/api/feeds)
│   │   ├── articles.py      # Article endpoints (/api/articles)
│   │   └── stats.py         # Statistics endpoint (/api/stats)
│   ├── services/
│   │   ├── rss_parser.py    # Feed fetching + parsing (with SSRF protection)
│   │   └── feed_service.py  # Business logic for feeds and articles
│   ├── templates/
│   │   └── index.html       # Single-page Jinja2 template
│   └── static/
│       ├── css/style.css    # Styles (dark/light theme, responsive)
│       └── js/app.js        # Frontend logic (fetch API, rendering)
├── tests/
│   └── test_rss_reader.py   # pytest suite (17 tests)
├── data/                    # SQLite database directory (created at runtime)
├── pyproject.toml           # Project metadata and dependencies
├── README.md                # This file (English)
├── README.ru.md             # Russian documentation
└── LICENSE                  # MIT License
```

### Components

- **`app/main.py`** — Creates the FastAPI app, registers routers, mounts static files, initializes the database.
- **`app/models/`** — SQLAlchemy 2.x ORM models. `Feed` (sources) and `Article` (publications) with a one-to-many relationship and a unique `feed_id + guid` constraint to prevent duplicates on refresh.
- **`app/schemas/`** — Pydantic v2 schemas for request validation and response serialization.
- **`app/api/`** — REST route handlers with proper HTTP status codes and error messages.
- **`app/services/rss_parser.py`** — Validates URLs (HTTP/HTTPS only), resolves DNS and blocks loopback/private/reserved/multicast addresses, follows redirects (max 5), caps download size at 2 MB, enforces a 15-second timeout, parses RSS 2.0 / RSS 1.0 / Atom, normalizes publication dates to UTC.
- **`app/services/feed_service.py`** — Business logic: create/refresh/delete feeds, paginated article listing with filters and search, read/favorite toggling, statistics aggregation.
- **`app/templates/index.html`** — Single HTML page with a sidebar source list, central article grid, top search/refresh bar, statistics panel, and an add-feed dialog.
- **`app/static/js/app.js`** — Vanilla JavaScript frontend that consumes the REST API; no build step required.
- **`tests/test_rss_reader.py`** — pytest suite covering feed validation, RSS/Atom parsing, invalid XML, duplicate prevention, read-status persistence, filters/search, and API endpoints. Network calls are mocked; no real RSS sites are required.

## Installation

### Requirements

- Python 3.11 or newer
- `pip` (bundled with Python)

No Docker, Node.js, or external cloud services are required.

### Windows (PowerShell)

```powershell
# Clone the repository
git clone <repository-url>
cd RSS Reader

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies (including dev dependencies for testing)
pip install -e ".[dev]"
```

### Linux / macOS

```bash
# Clone the repository
git clone <repository-url>
cd "RSS Reader"

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (including dev dependencies for testing)
pip install -e ".[dev]"
```

## Usage

### Start the server

```bash
uvicorn app.main:app --reload
```

The application will be available at http://127.0.0.1:8000.

Interactive API documentation (Swagger/OpenAPI): http://127.0.0.1:8000/docs

### Main user flows

1. Open the application in your browser.
2. Click **Добавить** (Add) in the sidebar and enter an RSS/Atom feed URL. The feed is validated before being saved.
3. Browse the unified article feed in the central area.
4. Use the filters to show only unread or favorite articles, or filter by source.
5. Use the search box to search across titles, summaries, and source names.
6. Mark articles as read/unread and add them to favorites using the buttons on each card.
7. Click **Открыть оригинал** (Open original) to open the source article in a new tab.
8. Click **Обновить всё** (Refresh all) to fetch new articles from all sources.
9. View statistics in the sidebar panel.

## Testing

The project includes 17 automated tests. Run them with:

```bash
pytest
```

Tests cover:
- URL validation (HTTP/HTTPS only, blocked schemes)
- SSRF host blocking (localhost, loopback, private addresses)
- RSS 2.0 and Atom feed parsing
- Invalid XML handling
- Feed creation and persistence
- Duplicate URL rejection
- Duplicate prevention on refresh
- Read-status persistence
- Search and filters
- API endpoints (feeds list, add feed, invalid feed, articles list, mark read, stats)

Network calls are mocked with local fixtures; no real RSS sites are required.

## Configuration

The application works without additional configuration. The SQLite database is stored in `data/rss_reader.db` and is created automatically on first run.

No `.env` file or environment variables are required for local development.

## Limitations

- No automatic background scheduler; feeds are refreshed only on user request through the interface.
- SQLite is a file-based database suitable for single-user/local deployment, not concurrent multi-user production use.
- Full-text search uses SQLite `LIKE` (FTS5 is not used).
- The frontend is a single HTML page served by FastAPI; there is no separate frontend build pipeline.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
