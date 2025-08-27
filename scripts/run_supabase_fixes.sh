#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SQL_FILE="$SCRIPT_DIR/supabase_fix_warnings.sql"

usage() {
  echo "Usage: $0 [-u DATABASE_URL] [-f SQL_FILE]" 1>&2
  echo "  -u DATABASE_URL : Postgres connection string (or set SUPABASE_DB_URL/DATABASE_URL env var)" 1>&2
  echo "  -f SQL_FILE     : Path to SQL file (default: $DEFAULT_SQL_FILE)" 1>&2
}

DB_URL="${SUPABASE_DB_URL:-${DATABASE_URL:-}}"
SQL_FILE="$DEFAULT_SQL_FILE"

while getopts ":u:f:h" opt; do
  case $opt in
    u) DB_URL="$OPTARG" ;;
    f) SQL_FILE="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Option -$OPTARG requires an argument" 1>&2; usage; exit 2 ;;
    \?) echo "Invalid option: -$OPTARG" 1>&2; usage; exit 2 ;;
  esac
done

if [[ -z "${DB_URL}" ]]; then
  echo "Error: DATABASE_URL not provided. Use -u or set SUPABASE_DB_URL/DATABASE_URL env var." 1>&2
  usage
  exit 2
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "Error: SQL file not found: $SQL_FILE" 1>&2
  exit 2
fi

echo "Applying Supabase fixes using: $SQL_FILE"
echo "Target database: ${DB_URL%%\?*} (parameters hidden)"

if command -v supabase >/dev/null 2>&1; then
  echo "Detected Supabase CLI. Executing via supabase db execute..."
  supabase db execute --db-url "$DB_URL" -f "$SQL_FILE" | cat
  echo "Done."
  exit 0
fi

if command -v psql >/dev/null 2>&1; then
  echo "Supabase CLI not found. Falling back to psql..."
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$SQL_FILE" | cat
  echo "Done."
  exit 0
fi

echo "Error: Neither 'supabase' CLI nor 'psql' found in PATH. Install one to proceed." 1>&2
exit 127


