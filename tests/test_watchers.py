"""
Tests for FileWatcher.

Covers detection of new/modified files, pattern filtering, callback invocation, and error handling.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from knowledge_system.watchers import FileWatcher, watch_directory


class TestFileWatcher:
    def test_start_stop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = FileWatcher(tmpdir)
            watcher.start()
            assert watcher._observer.is_alive()
            watcher.stop()
            assert not watcher._observer.is_alive()

    def test_invalid_directory(self):
        with pytest.raises(ValueError):
            watcher = FileWatcher("/nonexistent/dir")
            watcher.start()

    @patch("knowledge_system.watchers.PatternMatchingEventHandler")
    @patch("knowledge_system.watchers.Observer")
    def test_event_handler_created(self, mock_observer, mock_handler):
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = FileWatcher(
                tmpdir, patterns=["*.txt"], callback=callback, debounce=0
            )
            watcher.start()
            # Simulate file created event
            event = Mock()
            event.is_directory = False
            event.src_path = str(Path(tmpdir) / "file.txt")
            watcher._on_created(event)
            callback.assert_called_once()
            watcher.stop()

    @patch("knowledge_system.watchers.PatternMatchingEventHandler")
    @patch("knowledge_system.watchers.Observer")
    def test_event_handler_modified(self, mock_observer, mock_handler):
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = FileWatcher(
                tmpdir, patterns=["*.md"], callback=callback, debounce=0
            )
            watcher.start()
            # Simulate file modified event
            event = Mock()
            event.is_directory = False
            event.src_path = str(Path(tmpdir) / "file.md")
            watcher._on_modified(event)
            callback.assert_called_once()
            watcher.stop()

    def test_pattern_filtering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            called = []

            def cb(path):
                called.append(str(path))

            watcher = FileWatcher(
    tmpdir,
    patterns=["*.pdf"],
    callback=cb,
     debounce=0)
            watcher.start()
            # Create a matching file
            file1 = Path(tmpdir) / "a.pdf"
            file1.touch()
            watcher._on_created(Mock(is_directory=False, src_path=str(file1)))
            # Create a non-matching file
            file2 = Path(tmpdir) / "b.txt"
            file2.touch()
            watcher._on_created(Mock(is_directory=False, src_path=str(file2)))
            watcher.stop()
            assert any("a.pdf" in c for c in called)
            assert not any("b.txt" in c for c in called)

    def test_callback_error_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:

            def bad_cb(path):
                raise RuntimeError("fail!")

            watcher = FileWatcher(tmpdir, callback=bad_cb, debounce=0)
            watcher.start()
            event = Mock()
            event.is_directory = False
            event.src_path = str(Path(tmpdir) / "fail.txt")
            # Should not raise
            watcher._on_created(event)
            watcher.stop()


class TestWatchDirectory:
    @patch("knowledge_system.watchers.FileWatcher")
    def test_watch_directory_convenience(self, mock_fw):
        watcher = Mock()
        mock_fw.return_value = watcher
        out = watch_directory(
    "/tmp",
    patterns=["*.md"],
    callback=None,
     debounce=1.0)
        mock_fw.assert_called_once_with(
            "/tmp", patterns=["*.md"], callback=None, debounce=1.0
        )
        watcher.start.assert_called_once()
        assert out is watcher
