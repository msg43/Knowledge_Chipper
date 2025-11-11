"""
Simple import validation tests to catch database import errors early.

This test ensures that all database models are properly exported and can be imported
without errors. It should run quickly and catch configuration issues before integration tests.
"""

import pytest


def test_database_service_imports():
    """Test that DatabaseService can be imported without errors."""
    from knowledge_system.database import DatabaseService

    assert DatabaseService is not None


def test_all_database_models_importable():
    """Test that all major database models can be imported from the database module."""
    from knowledge_system.database import (
        Base,
        BrightDataSession,
        Claim,
        ClaimRelation,
        Concept,
        DatabaseService,
        EvidenceSpan,
        GeneratedFile,
        JargonTerm,
        MediaSource,
        MOCExtraction,
        Person,
        ProcessingJob,
        Summary,
        Transcript,
    )

    # Verify all imports succeeded
    assert MediaSource is not None
    assert Transcript is not None
    assert Summary is not None
    assert Claim is not None
    assert DatabaseService is not None


def test_download_cleanup_imports():
    """Test that DownloadCleanupService can be imported without errors."""
    from knowledge_system.utils.download_cleanup import DownloadCleanupService

    assert DownloadCleanupService is not None


def test_download_cleanup_can_use_database_models():
    """Test that DownloadCleanupService can instantiate with DatabaseService."""
    import tempfile
    from pathlib import Path

    from knowledge_system.database import DatabaseService, MediaSource
    from knowledge_system.utils.download_cleanup import DownloadCleanupService

    # Create test database in memory
    db_service = DatabaseService("sqlite:///:memory:")

    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        cleanup_service = DownloadCleanupService(db_service, Path(tmpdir))
        assert cleanup_service is not None
        assert cleanup_service.db_service is db_service


def test_no_video_model_exported():
    """Test that 'Video' is NOT exported from database module (should use MediaSource instead)."""
    import knowledge_system.database as db_module

    # Video should NOT be in __all__
    assert "Video" not in db_module.__all__
    assert not hasattr(db_module, "Video")


def test_claim_search_tab_imports():
    """Test that claim_search_tab can import MediaSource without errors."""
    # This test verifies that claim_search_tab.py doesn't try to import Video
    from knowledge_system.gui.tabs.claim_search_tab import ClaimSearchTab

    assert ClaimSearchTab is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
