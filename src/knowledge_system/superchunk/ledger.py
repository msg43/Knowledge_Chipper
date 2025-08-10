from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .validators import ClaimItem


@dataclass
class Ledger:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  started_at TEXT DEFAULT (datetime('now')),
                  config_json TEXT,
                  correlation_id TEXT
                );
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id INTEGER,
                  chunk_id TEXT,
                  text TEXT,
                  why_nonobvious TEXT,
                  rarity REAL,
                  confidence REAL,
                  quote TEXT,
                  span_start INTEGER,
                  span_end INTEGER,
                  para_idx INTEGER,
                  hedges_json TEXT,
                  novelty_score REAL,
                  included_in_final INTEGER,
                  evolution_trajectory TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_claims_para ON claims(para_idx);")
            conn.commit()

    def start_run(self, config: dict[str, Any], correlation_id: Optional[str] = None) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO runs (config_json, correlation_id) VALUES (?, ?)",
                (json.dumps(config), correlation_id),
            )
            conn.commit()
            return int(cur.lastrowid)

    def insert_claims(self, run_id: int, chunk_id: str, claims: Iterable[ClaimItem]) -> None:
        with self._connect() as conn:
            rows = [
                (
                    run_id,
                    chunk_id,
                    c.text,
                    c.why_nonobvious,
                    float(c.rarity),
                    float(c.confidence),
                    c.quote,
                    int(c.span_start),
                    int(c.span_end),
                    int(c.para_idx),
                    json.dumps(c.hedges),
                    None,
                    0,
                    None,
                )
                for c in claims
            ]
            conn.executemany(
                """
                INSERT INTO claims (
                  run_id, chunk_id, text, why_nonobvious, rarity, confidence,
                  quote, span_start, span_end, para_idx, hedges_json, novelty_score,
                  included_in_final, evolution_trajectory
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
