"""
File Watcher
File Watcher

Monitors directories for new/changed files using watchdog.
Supports multiple patterns, user callback, and robust error handling.
"""

import fnmatch
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import List, Optional, Union

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class FileWatcher:
    """ Watches a directory for new/changed files and triggers a callback."""

    def __init__(
        self,
        directory: str | Path,
        patterns: list[str] | None = None,
        callback: Callable[[Path], None] | None = None,
        debounce: float = 2.0,
        recursive: bool = False,
    ) -> None:
        self.directory = Path(directory)
        self.patterns = patterns or ["*"]
        self.callback = callback
        self.debounce = debounce
        self.recursive = recursive
        self._observer = None
        self._thread = None
        self._stop_event = threading.Event()

    def _matches_patterns(self, file_path: Path) -> bool:
        return any(fnmatch.fnmatch(str(file_path.name), pat) for pat in self.patterns)

    def _on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        file_path = Path(str(event.src_path))
        logger.info(f"File created: {file_path}")
        if self.callback and self._matches_patterns(file_path):
            time.sleep(self.debounce)  # Debounce to avoid partial writes
            try:
                self.callback(file_path)
            except Exception as e:
                logger.error(f"Callback error for {file_path}: {e}")

    def _on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        file_path = Path(str(event.src_path))
        logger.info(f"File modified: {file_path}")
        if self.callback and self._matches_patterns(file_path):
            time.sleep(self.debounce)
            try:
                self.callback(file_path)
            except Exception as e:
                logger.error(f"Callback error for {file_path}: {e}")

    def start(self):

        """ Start."""
        if not self.directory.exists() or not self.directory.is_dir():
            raise ValueError(f"Directory does not exist: {self.directory}")
        event_handler = PatternMatchingEventHandler(
            patterns=self.patterns, ignore_directories=True, case_sensitive=False
        )
        event_handler.on_created = self._on_created
        event_handler.on_modified = self._on_modified
        self._observer = Observer()
        self._observer.schedule(
            event_handler, str(self.directory), recursive=self.recursive
        )
        self._observer.start()
        logger.info(
            f"Started watching: {self.directory} (patterns: {self.patterns}, recursive: {self.recursive})"
        )
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            while not self._stop_event.is_set():
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"FileWatcher run error: {e}")

    def stop(self):

        """ Stop."""
        self._stop_event.set()
        if self._observer:
            self._observer.stop()
            self._observer.join()
        logger.info(f"Stopped watching: {self.directory}")


def watch_directory(
    directory: str | Path,
    patterns: list[str] | None = None,
    callback: Callable[[Path], None] | None = None,
    debounce: float = 2.0,
    recursive: bool = False,
) -> FileWatcher:
    """ Convenience function to start a file watcher."""
    watcher = FileWatcher(
        directory,
        patterns=patterns,
        callback=callback,
        debounce=debounce,
        recursive=recursive,
    )
    watcher.start()
    return watcher
