"""
Test utilities for GUI automation and deterministic sandboxing.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton

DEFAULT_WAIT_MS = 50
DEFAULT_TRIES = 60  # 3 seconds at 50ms


def process_events_for(ms: int) -> None:
    app = QApplication.instance()
    if not app:
        return
    end = time.time() + (ms / 1000.0)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_until(predicate: Callable[[], bool], timeout_ms: int = 3000) -> bool:
    app = QApplication.instance()
    if not app:
        return predicate()
    end = time.time() + (timeout_ms / 1000.0)
    while time.time() < end:
        if predicate():
            return True
        app.processEvents()
        time.sleep(0.02)
    return predicate()


def switch_to_tab(main_window: QObject, tab_name: str) -> bool:
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return False
    for i in range(tabs.count()):
        if tabs.tabText(i).lower() == tab_name.lower():
            tabs.setCurrentIndex(i)
            process_events_for(200)
            return True
    return False


def find_button_by_text(
    main_window: QObject, text_substring: str
) -> QPushButton | None:
    for btn in main_window.findChildren(QPushButton):
        if text_substring.lower() in btn.text().lower():
            return btn
    return None


def find_first_combo(main_window: QObject) -> QComboBox | None:
    combos = main_window.findChildren(QComboBox)
    return combos[0] if combos else None


def set_env_sandboxes(db_path: Path, output_dir: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["KNOWLEDGE_CHIPPER_TEST_DB"] = str(db_path)
    os.environ["KNOWLEDGE_CHIPPER_TEST_OUTPUT_DIR"] = str(output_dir)


@dataclass
class Sandbox:
    db_path: Path
    output_dir: Path


def create_sandbox(base_dir: Path) -> Sandbox:
    base_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(int(time.time()))
    db_path = base_dir / "db" / f"ks_test_{run_id}.sqlite"
    output_dir = base_dir / "output" / run_id
    set_env_sandboxes(db_path, output_dir)
    return Sandbox(db_path=db_path, output_dir=output_dir)
