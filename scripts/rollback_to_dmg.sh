#!/bin/bash
# Emergency rollback script to restore DMG workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")") && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚨 Rolling back to DMG workflow..."

# Find most recent backup
BACKUP_DIR=$(ls -1t "$PROJECT_ROOT"/scripts_backup_* 2>/dev/null | head -1)

if [ -z "$BACKUP_DIR" ]; then
    echo "❌ No backup found - cannot rollback"
    exit 1
fi

echo "📦 Restoring from: $BACKUP_DIR"

# Restore updated scripts
if [ -d "$BACKUP_DIR/updated" ]; then
    cp "$BACKUP_DIR/updated"/* "$SCRIPT_DIR/" 2>/dev/null || true
fi

# Restore removed scripts
if [ -d "$BACKUP_DIR/removed" ]; then
    cp "$BACKUP_DIR/removed"/* "$SCRIPT_DIR/" 2>/dev/null || true
fi

# Make scripts executable
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true

echo "✅ Rollback completed"
echo "⚠️ You may need to manually restore some configurations"
