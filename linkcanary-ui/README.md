# LinkCanary UI

Web-based user interface for LinkCanary link checker.

## Features

- **Dashboard** - Quick start crawls and view recent activity
- **New Crawl** - Configure and start crawls with advanced options
- **Progress View** - Real-time crawl progress with WebSocket updates
- **Reports Library** - Browse, filter, and manage all crawl reports
- **Report Viewer** - Interactive issue viewer with filtering and search
- **Settings** - Configure default crawl settings and storage options

## Requirements

- Python 3.10+
- Redis (for Celery task queue)
- Node.js 18+ (for frontend development)

## Installation

### From PyPI (when published)

```bash
pip install linkcanary-ui
```

### From Source

```bash
cd linkcanary-ui
pip install -e .
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

To build frontend for production:

```bash
npm run build
```

## Usage

### Start the UI Server

```bash
linkcanary-ui
```

Options:
- `--host HOST` - Host to bind to (default: 127.0.0.1)
- `--port PORT` - Port to bind to (default: 3000)
- `--open` - Open browser automatically
- `--data-dir DIR` - Custom data directory
- `--debug` - Enable debug mode

### Start Celery Worker (Required for Background Crawls)

First, start Redis:

```bash
redis-server
```

Then start the Celery worker:

```bash
cd linkcanary-ui
celery -A backend.tasks.celery_app worker --loglevel=info
```

### Access the UI

Open your browser to: http://localhost:3000

## API Endpoints

### Crawls

- `POST /api/crawls` - Start new crawl
- `GET /api/crawls` - List all crawls
- `GET /api/crawls/:id` - Get crawl details
- `DELETE /api/crawls/:id` - Delete crawl
- `POST /api/crawls/:id/stop` - Stop running crawl
- `POST /api/crawls/:id/rerun` - Re-run crawl
- `GET /api/crawls/:id/report` - Get report data

### Reports

- `GET /api/reports/:id/download/csv` - Download CSV
- `GET /api/reports/:id/download/html` - Download HTML

### Other

- `GET /api/stats` - Dashboard statistics
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings
- `POST /api/crawls/validate-sitemap` - Validate sitemap URL
- `WS /ws/crawl/:id` - WebSocket for crawl progress

## Architecture

```
linkcanary-ui/
├── backend/
│   ├── api/           # FastAPI routes
│   ├── models/        # SQLAlchemy models
│   ├── services/      # Business logic
│   ├── tasks/         # Celery tasks
│   ├── static/        # Built frontend (generated)
│   ├── config.py      # Settings
│   └── main.py        # App entry point
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API client
│   │   └── App.jsx       # Main app
│   └── ...
└── pyproject.toml
```

## Data Storage

Reports and database are stored in `~/.linkcanary/` by default:

```
~/.linkcanary/
├── linkcanary.db      # SQLite database
├── settings.json      # User settings
└── crawls/
    └── [crawl_id]/
        ├── report.csv
        └── report.html
```

## License

MIT
