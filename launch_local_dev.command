#!/bin/bash
#
# Launch Local Development Environment
#
# Starts both:
# 1. Knowledge_Chipper daemon (localhost:8765)
# 2. GetReceipts web UI (localhost:3000)
#
# Usage: Double-click this file or run ./launch_local_dev.command
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
GETRECEIPTS_DIR="$SCRIPT_DIR/../GetReceipts"

echo "=========================================="
echo "  Starting Local Development Environment"
echo "=========================================="
echo ""

# Check if GetReceipts directory exists
if [ ! -d "$GETRECEIPTS_DIR" ]; then
    echo "⚠️  GetReceipts directory not found at: $GETRECEIPTS_DIR"
    echo "   Adjust GETRECEIPTS_DIR in this script if needed."
    GETRECEIPTS_DIR=""
fi

# Start daemon in background
echo "🚀 Starting Knowledge_Chipper daemon..."
cd "$SCRIPT_DIR"
source venv/bin/activate
python -m daemon.main &
DAEMON_PID=$!
echo "   Daemon PID: $DAEMON_PID"

# Wait for daemon to start
sleep 2

# Check if daemon is healthy
if curl -s "http://localhost:8765/api/health" > /dev/null 2>&1; then
    echo "✅ Daemon is running at http://localhost:8765"
    echo "   Swagger UI: http://localhost:8765/docs"
else
    echo "⚠️  Daemon may still be starting..."
fi

echo ""

# Start GetReceipts if directory exists
if [ -n "$GETRECEIPTS_DIR" ]; then
    echo "🌐 Starting GetReceipts web UI..."
    cd "$GETRECEIPTS_DIR"
    
    # Source nvm if available
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    npm run dev &
    NEXT_PID=$!
    echo "   Next.js PID: $NEXT_PID"
    
    # Wait for Next.js to start
    sleep 5
    echo "✅ GetReceipts running at http://localhost:3000"
    echo "   Contribute page: http://localhost:3000/contribute"
fi

echo ""
echo "=========================================="
echo "  Development Environment Ready!"
echo "=========================================="
echo ""
echo "📂 Double-click 'GetReceipts Local.webloc' on Desktop to open"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for user to stop
wait

