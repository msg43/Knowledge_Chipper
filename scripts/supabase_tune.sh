#!/bin/bash

set -euo pipefail

# Supabase/Postgres RPC profiler for slow functions like public.get_subgraph
# - Runs EXPLAIN ANALYZE (TEXT and JSON)
# - Saves plans and function DDL (optional)
# - Generates heuristic index suggestions from the JSON plan via plan_to_indexes.py
#
# Requirements:
# - psql (PostgreSQL client)
# - python3
#
# Usage examples:
#   scripts/supabase_tune.sh \
#     --db-url "$DATABASE_URL" \
#     --schema public \
#     --function get_subgraph \
#     --filters scripts/example_filters.json \
#     --limit 100
#
# Notes:
# - You can also set DB URL via env: DATABASE_URL or SUPABASE_DB_URL
# - Filters file contents are passed as a single JSONB parameter to the RPC

print_usage() {
  cat <<'USAGE'
Usage: supabase_tune.sh --db-url <postgres-url> --schema <schema> --function <function> --filters <json-file> [--limit N] [--offset N] [--signature <schema.func(args)>]

Required:
  --db-url        Postgres connection URL (or set env DATABASE_URL / SUPABASE_DB_URL)
  --schema        Schema name (e.g., public)
  --function      Function name (e.g., get_subgraph)
  --filters       Path to JSON file passed as filters jsonb arg

Optional:
  --limit         LIMIT for the RPC result (default: 50)
  --offset        OFFSET for the RPC result (default: 0)
  --signature     Regprocedure signature for pg_get_functiondef (e.g., "public.get_subgraph(jsonb)")
  --outdir        Output directory (default: output/supabase_tuning/<timestamp>)

Outputs in outdir:
  plan.text            EXPLAIN ANALYZE (TEXT)
  plan.json            EXPLAIN ANALYZE (FORMAT JSON)
  index_suggestions.sql  Heuristic index DDL suggestions
  function_ddl.sql     Function definition if --signature provided
USAGE
}

timestamp() { date +"%Y%m%d_%H%M%S"; }

# --- Parse args ---
DB_URL="${DATABASE_URL:-${SUPABASE_DB_URL:-}}"
SCHEMA=""
FUNCTION=""
FILTERS_FILE=""
LIMIT_VAL=50
OFFSET_VAL=0
SIGNATURE=""
OUTDIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-url)
      DB_URL="$2"; shift 2;;
    --schema)
      SCHEMA="$2"; shift 2;;
    --function)
      FUNCTION="$2"; shift 2;;
    --filters)
      FILTERS_FILE="$2"; shift 2;;
    --limit)
      LIMIT_VAL="$2"; shift 2;;
    --offset)
      OFFSET_VAL="$2"; shift 2;;
    --signature)
      SIGNATURE="$2"; shift 2;;
    --outdir)
      OUTDIR="$2"; shift 2;;
    -h|--help)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; print_usage; exit 1;;
  esac
done

# --- Validate ---
if [[ -z "$DB_URL" || -z "$SCHEMA" || -z "$FUNCTION" || -z "$FILTERS_FILE" ]]; then
  echo "Missing required args." >&2
  print_usage
  exit 1
fi
if [[ ! -f "$FILTERS_FILE" ]]; then
  echo "Filters file not found: $FILTERS_FILE" >&2
  exit 1
fi
if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Please install PostgreSQL client tools." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3." >&2
  exit 1
fi

# --- Prepare output dir ---
if [[ -z "$OUTDIR" ]]; then
  OUTDIR="output/supabase_tuning/$(timestamp)"
fi
mkdir -p "$OUTDIR"

PLAN_TEXT="$OUTDIR/plan.text"
PLAN_JSON="$OUTDIR/plan.json"
FUNC_DDL="$OUTDIR/function_ddl.sql"
INDEX_SQL="$OUTDIR/index_suggestions.sql"
FILTERS_COPY="$OUTDIR/filters.json"

cp "$FILTERS_FILE" "$FILTERS_COPY"

echo "Outdir: $OUTDIR"
echo "Collecting EXPLAIN ANALYZE for ${SCHEMA}.${FUNCTION}() ..."

# Prepare SQL snippets
SQL_SELECT="SELECT * FROM ${SCHEMA}.${FUNCTION}(filters := :'filters'::jsonb) LIMIT :limit OFFSET :offset;"

# EXPLAIN (TEXT)
PSQL_FLAGS=(
  -v ON_ERROR_STOP=1
  -X
  --set=filters="$(cat "$FILTERS_FILE")"
  --set=limit="$LIMIT_VAL"
  --set=offset="$OFFSET_VAL"
)

# Generate plan.text
psql "${DB_URL}" "${PSQL_FLAGS[@]}" \
  -c "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, WAL, SETTINGS) ${SQL_SELECT}" \
  | cat > "$PLAN_TEXT"

# Generate plan.json
psql "${DB_URL}" "${PSQL_FLAGS[@]}" \
  -c "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, WAL, SETTINGS, FORMAT JSON) ${SQL_SELECT}" \
  | sed '1,/\[/d' | sed '$d' | sed 's/;$//' > "$PLAN_JSON"

# Optionally dump function DDL
if [[ -n "$SIGNATURE" ]]; then
  echo "Dumping function DDL for $SIGNATURE ..."
  psql "${DB_URL}" -X -v ON_ERROR_STOP=1 -c \
    "SELECT pg_get_functiondef('${SIGNATURE}'::regprocedure);" \
    | cat > "$FUNC_DDL" || true
fi

# Generate heuristic index suggestions
echo "Generating index suggestions ..."
python3 "$(dirname "$0")/plan_to_indexes.py" "$PLAN_JSON" > "$INDEX_SQL" || {
  echo "Failed to generate index suggestions; see plan.json for manual review." >&2
}

cat <<EOF

Done.
- EXPLAIN text:   $PLAN_TEXT
- EXPLAIN (JSON): $PLAN_JSON
- Index suggestions: $INDEX_SQL
$( [[ -n "$SIGNATURE" ]] && echo "- Function DDL:     $FUNC_DDL" )

Next steps:
- Review $INDEX_SQL and apply relevant indexes on hot paths.
- Prefer keyset pagination on ordered keys (avoid large OFFSETs).
EOF
