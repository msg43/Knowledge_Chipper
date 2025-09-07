#!/usr/bin/env python3
"""
Heuristic EXPLAIN(JSON) to index DDL suggester.

Reads a Postgres EXPLAIN (FORMAT JSON) file and emits best-guess CREATE INDEX
statements for:
- Seq Scan with Filter on columns (including expressions on jsonb ->> keys)
- Hash/Loop Join on join keys
- Sort nodes with large rows/temporary disk usage (suggest ORDER BY index)

This is intentionally simple and conservative; you should review/adjust before applying.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, List, Optional

JSON_FILTER_KEY_PATTERN = re.compile(r"\(([^)]+)\)")
JSON_ARROW_EXTRACT = re.compile(r"\(([^)]+)->>'([A-Za-z0-9_]+)'\)")


@dataclass
class Suggestion:
    ddl: str
    reason: str


def load_plan(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
        if not text:
            raise SystemExit("Empty plan JSON")
        data = json.loads(text)
        # EXPLAIN (FORMAT JSON) usually returns a list with one element
        if isinstance(data, list) and data:
            return data[0]
        return data


def traverse(node: dict, visit: callable[[dict], None]) -> None:
    visit(node)
    for key in ("Plans", "Inner Unique"):  # standard child container
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    traverse(child, visit)


def parse_relation(node: dict) -> str | None:
    rel = node.get("Relation Name")
    schema = node.get("Schema")
    if rel and schema:
        return f"{schema}.{rel}"
    return None


def extract_columns_from_filter(filter_text: str) -> list[str]:
    cols: list[str] = []
    # Capture expressions like ((table.column) = $X) or ((table.column) >= ...)
    for match in JSON_FILTER_KEY_PATTERN.finditer(filter_text):
        expr = match.group(1)
        # Keep jsonb ->> key expressions as-is to recommend expression indexes
        cols.append(expr)
    return cols


def normalize_identifier(identifier: str) -> str:
    ident = identifier.strip()
    # Remove wrapping quotes if any
    if ident.startswith('"') and ident.endswith('"'):
        ident = ident[1:-1]
    return ident


def suggest_index_for_expression(table: str, expr: str) -> str:
    # Handle jsonb ->> key expression specifically
    m = JSON_ARROW_EXTRACT.match(expr)
    if m:
        lhs, key = m.groups()
        lhs = lhs.strip()
        key = normalize_identifier(key)
        # Index on ((lhs->>'key')) expression
        return (
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{table.replace('.', '_')}_json_{key} "
            f"ON {table} ((({lhs}->>'{key}')));"
        )

    # Fallback: plain column like table.col or alias.col
    col = expr.split(".")[-1]
    col = normalize_identifier(col)
    return (
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{table.replace('.', '_')}_{col} "
        f"ON {table} ({col});"
    )


def collect_suggestions(plan_root: dict) -> list[Suggestion]:
    suggestions: list[Suggestion] = []

    def visit(node: dict) -> None:
        node_type = node.get("Node Type", "")
        relation = parse_relation(node)
        # Seq Scan with Filter
        if node_type == "Seq Scan" and relation and node.get("Filter"):
            filt = node["Filter"]
            cols = extract_columns_from_filter(filt)
            for expr in cols:
                ddl = suggest_index_for_expression(relation, expr)
                suggestions.append(
                    Suggestion(ddl=ddl, reason=f"Seq Scan filter: {filt}")
                )

        # Nested Loop/Hash Join - suggest indexes on join conditions
        if node_type in ("Nested Loop", "Hash Join", "Merge Join"):
            cond = (
                node.get("Hash Cond")
                or node.get("Merge Cond")
                or node.get("Join Filter")
            )
            if cond:
                cols = extract_columns_from_filter(cond)
                for expr in cols:
                    # Heuristic: if looks like (schema.table.col = schema.table.col)
                    if "=" in cond and "." in expr:
                        parts = expr.split(".")
                        if len(parts) >= 2:
                            # Suggest on the rightmost relation we saw prior in the plan is hard.
                            # Default to the right-hand side column as separate suggestion.
                            col = parts[-1]
                            # If we can infer a relation from parent scans, skip for now.
                            if relation:
                                ddl = suggest_index_for_expression(relation, expr)
                                suggestions.append(
                                    Suggestion(
                                        ddl=ddl, reason=f"Join condition: {cond}"
                                    )
                                )

        # Sort with many rows spilled to disk
        if node_type == "Sort" and node.get("Sort Key"):
            rows = node.get("Plan Rows", 0)
            sort_keys: list[str] = node["Sort Key"]
            if relation and rows and rows > 10000:
                # Recommend multi-column index on sort keys
                keys_sql = ", ".join(k for k in sort_keys)
                ddl = (
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_{relation.replace('.', '_')}_order_"
                    f"ON {relation} ({keys_sql});"
                )
                suggestions.append(
                    Suggestion(ddl=ddl, reason=f"Sort on {sort_keys} over {rows} rows")
                )

    plan = plan_root.get("Plan") or plan_root
    traverse(plan, visit)
    return suggestions


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: plan_to_indexes.py <plan.json>", file=sys.stderr)
        raise SystemExit(2)
    plan_path = sys.argv[1]
    root = load_plan(plan_path)
    suggestions = collect_suggestions(root)
    if not suggestions:
        print("-- No heuristic index suggestions found. Review plan.json manually.")
        return

    print("-- Heuristic index suggestions generated from EXPLAIN (FORMAT JSON)")
    print("-- Review carefully before applying in production.")
    for s in suggestions:
        print()
        print(f"-- Reason: {s.reason}")
        print(s.ddl + ";")


if __name__ == "__main__":
    main()
