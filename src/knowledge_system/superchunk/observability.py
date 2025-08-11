from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class EventLogger:
    path: Path

    def log(self, step: str, item_id: str | None = None, **kwargs: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "step": step,
            "item_id": item_id,
            **kwargs,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
