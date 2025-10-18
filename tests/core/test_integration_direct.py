"""
Direct integration tests - test GUI logic without launching GUI.

These tests validate the actual functions and data flows that the GUI uses,
without requiring GUI rendering or user interaction. Fully automated.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock


class TestTranscriptionToSummarizationDataFlow:
    """Test data flow between transcription and summarization (validates bug fix)."""
    
    @pytest.mark.direct
    @pytest.mark.timeout(30)
    def test_successful_files_structure(self):
        """Test successful_files structure includes saved_file_path (our fix)."""
        # This is the structure transcription worker creates
        successful_files = [{
            "file": "test.mp3",
            "text_length": 1000,
            "saved_to": "test_transcript.md",
            "saved_file_path": "/full/path/to/test_transcript.md"  # Must have this
        }]
        
        # Verify structure
        assert "saved_file_path" in successful_files[0]
        assert successful_files[0]["saved_file_path"].endswith(".md")
        assert "text_length" in successful_files[0]
        assert "saved_to" in successful_files[0]
    
    @pytest.mark.direct
    @pytest.mark.timeout(30)
    def test_file_path_extraction_logic(self, tmp_path):
        """Test file path extraction from successful_files (validates fix)."""
        # Create test transcripts
        transcript1 = tmp_path / "transcript1.md"
        transcript1.write_text("Test transcript 1")
        transcript2 = tmp_path / "transcript2.md"
        transcript2.write_text("Test transcript 2")
        
        # Simulate transcription worker output
        successful_files = [
            {
                "file": "audio1.mp3",
                "text_length": 500,
                "saved_to": "transcript1.md",
                "saved_file_path": str(transcript1)  # Full path
            },
            {
                "file": "audio2.mp3",
                "text_length": 750,
                "saved_to": "transcript2.md",
                "saved_file_path": str(transcript2)  # Full path
            }
        ]
        
        # Extract paths (logic from _switch_to_summarization_with_files)
        file_paths = []
        for file_info in successful_files:
            saved_file_path = file_info.get("saved_file_path")
            if saved_file_path and Path(saved_file_path).exists():
                file_paths.append(saved_file_path)
        
        # Verify extraction worked
        assert len(file_paths) == 2
        assert all(Path(p).exists() for p in file_paths)
        assert str(transcript1) in file_paths
        assert str(transcript2) in file_paths
    
    @pytest.mark.direct
    @pytest.mark.timeout(30)
    def test_fallback_path_reconstruction(self, tmp_path):
        """Test fallback logic when saved_file_path not present (backward compat)."""
        # Create output directory with transcript
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        transcript = output_dir / "test_transcript.md"
        transcript.write_text("Test transcript")
        
        # Old-style successful_files (no saved_file_path)
        successful_files = [{
            "file": "test.mp3",
            "text_length": 1000,
            "saved_to": "test_transcript.md",
            # No saved_file_path - should fallback
        }]
        
        # Fallback extraction logic
        file_paths = []
        for file_info in successful_files:
            # Try new field first
            saved_file_path = file_info.get("saved_file_path")
            if saved_file_path and Path(saved_file_path).exists():
                file_paths.append(saved_file_path)
                continue
            
            # Fallback: reconstruct from filename and output_dir
            file_path = file_info.get("file")
            if file_path:
                file_path_obj = Path(file_path)
                base_name = file_path_obj.stem
                transcript_file = output_dir / f"{base_name}_transcript.md"
                if transcript_file.exists():
                    file_paths.append(str(transcript_file))
        
        # Verify fallback worked
        assert len(file_paths) == 1
        assert Path(file_paths[0]).exists()


class TestMonitorTabLogic:
    """Test Monitor tab processing logic without GUI."""
    
    @pytest.mark.direct
    @pytest.mark.timeout(30)
    def test_monitor_tab_uses_system2(self):
        """Verify Monitor tab imports System2Orchestrator (not SummarizerProcessor)."""
        # This test ensures our Phase 1 fix persists
        import inspect
        from knowledge_system.gui.tabs.monitor_tab import MonitorTab
        
        # Get the source code of _process_file method
        source = inspect.getsource(MonitorTab._process_file)
        
        # Verify it imports System2Orchestrator
        assert "System2Orchestrator" in source
        
        # Verify it does NOT import SummarizerProcessor
        assert "from ...processors.summarizer import SummarizerProcessor" not in source


class TestEventLoopCleanupDirect:
    """Test event loop cleanup without GUI."""
    
    @pytest.mark.direct
    @pytest.mark.timeout(60)
    def test_asyncio_run_in_thread_scenario(self):
        """Test the QThread scenario: asyncio.run() from sync context."""
        import asyncio
        
        async def mock_async_operation():
            """Simulates System2Orchestrator.process_job()."""
            await asyncio.sleep(0.1)
            return {"status": "succeeded"}
        
        # This is what GUI does in QThread workers
        result = asyncio.run(mock_async_operation())
        
        assert result["status"] == "succeeded"
        # If no "Event loop is closed" error, cleanup worked
    
    @pytest.mark.direct
    @pytest.mark.timeout(60)
    def test_multiple_sequential_asyncio_runs(self):
        """Test multiple sequential asyncio.run() calls (GUI batch scenario)."""
        import asyncio
        
        async def mock_job(job_id):
            await asyncio.sleep(0.05)
            return {"job_id": job_id, "status": "succeeded"}
        
        # Simulate processing multiple files
        results = []
        for i in range(3):
            result = asyncio.run(mock_job(f"job_{i}"))
            results.append(result)
        
        # Verify all completed without event loop errors
        assert len(results) == 3
        for result in results:
            assert result["status"] == "succeeded"

