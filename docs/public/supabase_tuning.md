## Supabase/Postgres query tuning

Use the helper to capture EXPLAIN plans and generate heuristic index suggestions for `public.get_subgraph(filters jsonb)` (or any similar RPC).

1) Set your database URL via env or flag:

```bash
export DATABASE_URL="postgres://user:pass@host:6543/dbname"
```

2) Prepare a `filters.json` payload (see `scripts/example_filters.json`).

3) Run the tuner:

```bash
scripts/supabase_tune.sh \
  --schema public \
  --function get_subgraph \
  --filters scripts/example_filters.json \
  --limit 100 \
  --signature "public.get_subgraph(jsonb)"
```

Outputs are written under `output/supabase_tuning/<timestamp>/`:

- plan.text: EXPLAIN ANALYZE text
- plan.json: EXPLAIN ANALYZE (FORMAT JSON)
- index_suggestions.sql: heuristic CREATE INDEX statements to review
- function_ddl.sql: function definition (if `--signature` provided)

Apply relevant indexes carefully in production, prefer `CONCURRENTLY`, and consider switching to keyset pagination instead of large OFFSETs.
