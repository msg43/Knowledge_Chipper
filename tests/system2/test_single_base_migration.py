"""
Comprehensive tests for single base migration.

Tests that all models are accessible from unified Base and that
foreign keys resolve correctly after migration.
"""

import pytest

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.models import Base


def test_all_models_accessible_from_unified_base():
    """Verify all models are accessible from the unified Base."""
    tables = Base.metadata.tables.keys()

    # Core models (MainBase)
    assert "media_sources" in tables
    assert "transcripts" in tables
    assert "summaries" in tables
    assert "moc_extractions" in tables
    assert "generated_files" in tables
    assert "processing_jobs" in tables
    assert "bright_data_sessions" in tables
    assert "claim_tier_validations" in tables
    assert "quality_ratings" in tables
    assert "quality_metrics" in tables

    # HCE models
    assert "episodes" in tables
    assert "claims" in tables
    assert "people" in tables
    assert "concepts" in tables
    assert "jargon" in tables

    # System2 models
    assert "job" in tables
    assert "job_run" in tables
    assert "llm_request" in tables
    assert "llm_response" in tables

    # Speaker models
    assert "speaker_voices" in tables
    assert "speaker_assignments" in tables
    assert "speaker_learning_history" in tables
    assert "speaker_sessions" in tables
    assert "channel_host_mappings" in tables
    assert "speaker_processing_sessions" in tables


def test_in_memory_database_creation():
    """Test that in-memory database can be created with all tables."""
    db_service = DatabaseService("sqlite:///:memory:")

    # Verify database was created
    assert db_service.engine is not None
    assert db_service.Session is not None

    # Verify we can get a session
    with db_service.get_session() as session:
        assert session is not None


def test_cross_base_foreign_key_resolution():
    """Test that Episode.video_id → MediaSource.media_id FK resolves correctly."""
    from src.knowledge_system.database.models import Episode, MediaSource

    # Check that Episode has the foreign key
    episode_table = Base.metadata.tables["episodes"]
    assert "video_id" in episode_table.columns

    # Check that the FK references media_sources
    fk = list(episode_table.foreign_keys)[0]
    assert fk.column.table.name == "media_sources"
    assert fk.column.name == "media_id"


def test_hce_models_in_unified_base():
    """Test that all HCE models are in the unified Base."""
    from src.knowledge_system.database.models import (
        Claim,
        Concept,
        Episode,
        Jargon,
        Person,
    )

    # Verify all models use the same Base
    assert Episode.__table__.metadata is Base.metadata
    assert Claim.__table__.metadata is Base.metadata
    assert Person.__table__.metadata is Base.metadata
    assert Concept.__table__.metadata is Base.metadata
    assert Jargon.__table__.metadata is Base.metadata


def test_speaker_models_in_unified_base():
    """Test that all Speaker models are in the unified Base."""
    from src.knowledge_system.database.models import (
        ChannelHostMapping,
        SpeakerAssignment,
        SpeakerLearningHistory,
        SpeakerProcessingSession,
        SpeakerSession,
        SpeakerVoice,
    )

    # Verify all models use the same Base
    assert SpeakerVoice.__table__.metadata is Base.metadata
    assert SpeakerAssignment.__table__.metadata is Base.metadata
    assert SpeakerLearningHistory.__table__.metadata is Base.metadata
    assert SpeakerSession.__table__.metadata is Base.metadata
    assert ChannelHostMapping.__table__.metadata is Base.metadata
    assert SpeakerProcessingSession.__table__.metadata is Base.metadata


def test_system2_models_in_unified_base():
    """Test that all System2 models are in the unified Base."""
    # System2 models are imported through system2_models.py
    from src.knowledge_system.database.system2_models import (
        Job,
        JobRun,
        LLMRequest,
        LLMResponse,
    )

    # Verify all models use the same Base
    assert Job.__table__.metadata is Base.metadata
    assert JobRun.__table__.metadata is Base.metadata
    assert LLMRequest.__table__.metadata is Base.metadata
    assert LLMResponse.__table__.metadata is Base.metadata


def test_backward_compatibility_hce_imports():
    """Test that old imports from hce_models still work."""
    from src.knowledge_system.database.hce_models import Base as HCEBase
    from src.knowledge_system.database.hce_models import (
        Claim,
        Concept,
        Episode,
        Jargon,
        Person,
    )

    # Verify they're the same Base
    assert HCEBase is Base

    # Verify models are accessible
    assert Episode is not None
    assert Claim is not None
    assert Person is not None
    assert Concept is not None
    assert Jargon is not None


def test_backward_compatibility_speaker_imports():
    """Test that old imports from speaker_models still work."""
    from src.knowledge_system.database.speaker_models import Base as SpeakerBase
    from src.knowledge_system.database.speaker_models import (
        ChannelHostMapping,
        SpeakerAssignment,
        SpeakerLearningHistory,
        SpeakerProcessingSession,
        SpeakerSession,
        SpeakerVoice,
    )

    # Verify they're the same Base
    assert SpeakerBase is Base

    # Verify models are accessible
    assert SpeakerVoice is not None
    assert SpeakerAssignment is not None
    assert SpeakerLearningHistory is not None
    assert SpeakerSession is not None
    assert ChannelHostMapping is not None
    assert SpeakerProcessingSession is not None


def test_backward_compatibility_system2_imports():
    """Test that old imports from system2_models still work."""
    from src.knowledge_system.database.system2_models import Base as System2Base
    from src.knowledge_system.database.system2_models import (
        Job,
        JobRun,
        LLMRequest,
        LLMResponse,
    )

    # Verify they're the same Base
    assert System2Base is Base

    # Verify models are accessible
    assert Job is not None
    assert JobRun is not None
    assert LLMRequest is not None
    assert LLMResponse is not None


def test_bidirectional_relationships():
    """Test that bidirectional relationships work."""
    from src.knowledge_system.database.models import Episode, MediaSource

    # Check MediaSource has episodes relationship
    assert hasattr(MediaSource, "episodes")

    # Check Episode has media_source relationship
    assert hasattr(Episode, "media_source")


def test_create_episode_with_media_source():
    """Test creating an Episode that references a MediaSource."""
    db_service = DatabaseService("sqlite:///:memory:")

    from src.knowledge_system.database.models import Episode, MediaSource

    with db_service.get_session() as session:
        # Create a media source
        media_source = MediaSource(
            media_id="test_video_123",
            source_type="youtube",
            title="Test Video",
            url="https://youtube.com/watch?v=test_video_123",
        )
        session.add(media_source)
        session.flush()

        # Create an episode that references it
        episode = Episode(
            episode_id="episode_test_123",
            video_id="test_video_123",
            title="Test Episode",
        )
        session.add(episode)
        session.commit()

        # Verify the episode was created
        retrieved_episode = (
            session.query(Episode).filter_by(episode_id="episode_test_123").first()
        )
        assert retrieved_episode is not None
        assert retrieved_episode.video_id == "test_video_123"

        # Verify the relationship works
        assert retrieved_episode.media_source is not None
        assert retrieved_episode.media_source.media_id == "test_video_123"


def test_all_foreign_keys_resolve():
    """Test that all foreign keys can resolve their target tables."""
    for table_name, table in Base.metadata.tables.items():
        for fk in table.foreign_keys:
            # Verify the target table exists in the same metadata
            target_table_name = fk.column.table.name
            assert (
                target_table_name in Base.metadata.tables
            ), f"FK in {table_name} references {target_table_name} which is not in Base.metadata"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
