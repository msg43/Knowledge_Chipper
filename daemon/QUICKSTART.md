# Daemon Quick Start

Get the Knowledge Chipper daemon running in 2 minutes.

## Prerequisites

```bash
# Install dependencies (if not already installed)
cd /Users/matthewgreer/Projects/Knowledge_Chipper
pip install -r requirements.txt

# The daemon requires FastAPI and Uvicorn
pip install fastapi uvicorn pydantic-settings
```

## Start the Daemon

### Option 1: Using Python Module

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m daemon.main
```

### Option 2: Using Uvicorn Directly

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
uvicorn daemon.main:app --host 127.0.0.1 --port 8765
```

You should see:

```
============================================================
Knowledge_Chipper Daemon v0.1.0 starting...
Server: http://127.0.0.1:8765
Swagger UI: http://127.0.0.1:8765/docs
CORS enabled for: ['http://localhost:3000', 'https://getreceipts.org']
============================================================
INFO:     Uvicorn running on http://127.0.0.1:8765
```

## Access the Endpoints

### 1. Health Check

```bash
curl http://localhost:8765/api/health
```

### 2. Database Viewer (NEW!)

Open in your browser:

```
http://localhost:8765/api/admin/database
```

You'll see:
- Database summary (size, table count, last modified)
- All tables with expandable views
- 100 records per table (sorted by most recent)
- "Load More" button to see next 100 records
- Manual refresh button

### 3. API Documentation

Open Swagger UI:

```
http://localhost:8765/docs
```

Interactive API docs with "Try it out" functionality.

## Configuration

### Database Path

By default, the daemon looks for the database at:

```
~/Projects/Knowledge_Chipper/knowledge_system.db
```

To use a different location:

```bash
export KC_DATABASE_PATH="/path/to/your/knowledge_system.db"
python3 -m daemon.main
```

### Port

Change the port:

```bash
export KC_PORT=9000
python3 -m daemon.main
```

### All Available Settings

Environment variables with `KC_` prefix:

- `KC_HOST` - Server host (default: 127.0.0.1)
- `KC_PORT` - Server port (default: 8765)
- `KC_DATABASE_PATH` - SQLite database path
- `KC_LOG_LEVEL` - Logging level (default: INFO)
- `KC_DEFAULT_WHISPER_MODEL` - Whisper model (default: medium)
- `KC_AUTO_UPLOAD_ENABLED` - Auto-upload to GetReceipts (default: true)

## Common Tasks

### Process a YouTube Video

```bash
curl -X POST http://localhost:8765/api/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

Returns:
```json
{
  "job_id": "abc123",
  "status": "queued",
  "message": "Job queued successfully"
}
```

### Check Job Status

```bash
curl http://localhost:8765/api/jobs/abc123
```

### List All Jobs

```bash
curl http://localhost:8765/api/jobs?limit=10
```

### Browse Database Tables

```bash
# Get database summary
curl http://localhost:8765/api/admin/database/summary

# Get records from a table
curl "http://localhost:8765/api/admin/database/table/claims?limit=100&offset=0"
```

## Troubleshooting

### Port Already in Use

```bash
# Find what's using port 8765
lsof -i :8765

# Kill the process
kill -9 PID

# Or use a different port
export KC_PORT=9000
python3 -m daemon.main
```

### Database Not Found

Check the database path:

```bash
ls -la ~/Projects/Knowledge_Chipper/knowledge_system.db
```

If it's elsewhere, set the path:

```bash
export KC_DATABASE_PATH="/actual/path/to/knowledge_system.db"
```

### Module Not Found

Make sure you're in the project root:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m daemon.main
```

Install missing dependencies:

```bash
pip install fastapi uvicorn pydantic-settings
```

## Development Mode

Enable auto-reload on code changes:

```bash
export KC_RELOAD=true
python3 -m daemon.main
```

Or with uvicorn directly:

```bash
uvicorn daemon.main:app --reload --host 127.0.0.1 --port 8765
```

## Production Use

For production deployment, use a process manager:

```bash
# Using systemd (Linux)
sudo systemctl start knowledge-chipper-daemon

# Using launchd (macOS)
launchctl load ~/Library/LaunchAgents/org.getreceipts.daemon.plist

# Using PM2 (Node.js process manager)
pm2 start "python3 -m daemon.main" --name knowledge-chipper-daemon
```

## Next Steps

- **Web UI**: The daemon is designed to work with GetReceipts.org website
- **Local Processing**: All heavy lifting (Whisper, LLM) happens on your Mac
- **Database Viewer**: Browse your local database at `/api/admin/database`
- **API Docs**: Explore all endpoints at `/docs`

---

**Need Help?**

- Check logs: `~/Library/Logs/KnowledgeChipper/daemon.log`
- View API docs: `http://localhost:8765/docs`
- Database viewer: `http://localhost:8765/api/admin/database`

