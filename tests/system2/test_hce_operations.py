"""
Unit tests for HCE operations module.

Tests database operations for storing and retrieving mining results.
"""

import pytest

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.hce_models import (
    Claim,
    Concept,
    Episode,
    Jargon,
    Person,
)
from src.knowledge_system.database.hce_operations import (
    clear_episode_data,
    get_episode_summary,
    load_mining_results,
    store_mining_results,
    store_transcript,
)
from src.knowledge_system.processors.hce.unified_miner import UnifiedMinerOutput


@pytest.fixture
def test_db_service():
    """Create a test database service with in-memory database."""
    db_service = DatabaseService("sqlite:///:memory:")

    # Create all tables from unified Base
    from src.knowledge_system.database.models import Base

    Base.metadata.create_all(db_service.engine)

    yield db_service


@pytest.fixture
def sample_miner_output():
    """Create a sample miner output for testing."""
    return UnifiedMinerOutput(
        {
            "claims": [
                {
                    "claim_id": "claim_001",
                    "claim_text": "AI will transform healthcare",
                    "claim_type": "forecast",
                    "timestamp": "00:01:30",
                    "scores": {"confidence": 0.8},
                },
                {
                    "claim_id": "claim_002",
                    "claim_text": "Machine learning requires large datasets",
                    "claim_type": "factual",
                    "timestamp": "00:02:15",
                    "scores": {"confidence": 0.9},
                },
            ],
            "jargon": [
                {
                    "term_id": "jargon_001",
                    "term": "Neural Network",
                    "definition": "A computing system inspired by biological neural networks",
                    "category": "technical",
                    "timestamp": "00:01:45",
                }
            ],
            "people": [
                {
                    "person_id": "person_001",
                    "name": "Geoffrey Hinton",
                    "description": "AI researcher and pioneer",
                    "timestamp": "00:03:00",
                }
            ],
            "mental_models": [
                {
                    "model_id": "concept_001",
                    "name": "Deep Learning",
                    "definition": "Machine learning using neural networks with multiple layers",
                    "timestamp": "00:02:30",
                }
            ],
        }
    )


class TestStoreMininingResults:
    """Test storing mining results in database."""

    def test_store_mining_results_creates_episode(
        self, test_db_service, sample_miner_output
    ):
        """Test that storing results creates episode if it doesn't exist."""
        episode_id = "episode_test_123"

        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify episode was created
        with test_db_service.get_session() as session:
            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None
            assert episode.episode_id == episode_id
            assert episode.video_id == "test_123"

    def test_store_mining_results_stores_claims(
        self, test_db_service, sample_miner_output
    ):
        """Test that claims are stored correctly."""
        episode_id = "episode_test_123"

        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify claims were stored
        with test_db_service.get_session() as session:
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            assert len(claims) == 2

            claim_texts = [c.canonical for c in claims]
            assert "AI will transform healthcare" in claim_texts
            assert "Machine learning requires large datasets" in claim_texts

            # Check claim details
            claim1 = next(c for c in claims if c.claim_id == "claim_001")
            assert claim1.claim_type == "forecast"
            assert claim1.first_mention_ts == "00:01:30"
            assert claim1.scores_json["confidence"] == 0.8

    def test_store_mining_results_stores_jargon(
        self, test_db_service, sample_miner_output
    ):
        """Test that jargon is stored correctly."""
        episode_id = "episode_test_123"

        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify jargon was stored
        with test_db_service.get_session() as session:
            jargon_list = session.query(Jargon).filter_by(episode_id=episode_id).all()
            assert len(jargon_list) == 1

            jargon = jargon_list[0]
            assert jargon.term == "Neural Network"
            assert "biological" in jargon.definition
            assert jargon.category == "technical"

    def test_store_mining_results_stores_people(
        self, test_db_service, sample_miner_output
    ):
        """Test that people are stored correctly."""
        episode_id = "episode_test_123"

        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify people were stored
        with test_db_service.get_session() as session:
            people = session.query(Person).filter_by(episode_id=episode_id).all()
            assert len(people) == 1

            person = people[0]
            assert person.name == "Geoffrey Hinton"
            assert "researcher" in person.description

    def test_store_mining_results_stores_concepts(
        self, test_db_service, sample_miner_output
    ):
        """Test that mental models/concepts are stored correctly."""
        episode_id = "episode_test_123"

        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify concepts were stored
        with test_db_service.get_session() as session:
            concepts = session.query(Concept).filter_by(episode_id=episode_id).all()
            assert len(concepts) == 1

            concept = concepts[0]
            assert concept.name == "Deep Learning"
            assert "neural networks" in concept.description

    def test_store_mining_results_multiple_outputs(self, test_db_service):
        """Test storing multiple miner outputs for same episode."""
        episode_id = "episode_test_456"

        output1 = UnifiedMinerOutput(
            {
                "claims": [
                    {"claim_id": "c1", "claim_text": "Claim 1", "claim_type": "factual"}
                ],
                "jargon": [],
                "people": [],
                "mental_models": [],
            }
        )

        output2 = UnifiedMinerOutput(
            {
                "claims": [
                    {"claim_id": "c2", "claim_text": "Claim 2", "claim_type": "causal"}
                ],
                "jargon": [],
                "people": [],
                "mental_models": [],
            }
        )

        store_mining_results(test_db_service, episode_id, [output1, output2])

        # Verify both claims were stored
        with test_db_service.get_session() as session:
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            assert len(claims) == 2

    def test_store_mining_results_handles_duplicates(
        self, test_db_service, sample_miner_output
    ):
        """Test that storing results twice doesn't create duplicates."""
        episode_id = "episode_test_789"

        # Store once
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Store again
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Should still have only one set of results
        with test_db_service.get_session() as session:
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            # Due to duplicate checking, we should have 2 claims, not 4
            assert len(claims) == 2


class TestLoadMiningResults:
    """Test loading mining results from database."""

    def test_load_mining_results_returns_correct_structure(
        self, test_db_service, sample_miner_output
    ):
        """Test that loaded results have correct structure."""
        episode_id = "episode_test_load"

        # Store first
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Load back
        outputs = load_mining_results(test_db_service, episode_id)

        assert len(outputs) == 1
        output = outputs[0]

        assert len(output.claims) == 2
        assert len(output.jargon) == 1
        assert len(output.people) == 1
        assert len(output.mental_models) == 1

    def test_load_mining_results_preserves_data(
        self, test_db_service, sample_miner_output
    ):
        """Test that loaded results preserve original data."""
        episode_id = "episode_test_preserve"

        # Store
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Load
        outputs = load_mining_results(test_db_service, episode_id)
        output = outputs[0]

        # Check claims
        claim = next(c for c in output.claims if c.get("claim_id") == "claim_001")
        assert claim["claim_text"] == "AI will transform healthcare"
        assert claim["claim_type"] == "forecast"
        assert claim["scores"]["confidence"] == 0.8

        # Check jargon
        jargon = output.jargon[0]
        assert jargon["term"] == "Neural Network"

        # Check people
        person = output.people[0]
        assert person["name"] == "Geoffrey Hinton"

        # Check concepts
        concept = output.mental_models[0]
        assert concept["name"] == "Deep Learning"

    def test_load_mining_results_empty_episode(self, test_db_service):
        """Test loading results for episode with no data."""
        episode_id = "episode_empty"

        outputs = load_mining_results(test_db_service, episode_id)

        assert len(outputs) == 1
        output = outputs[0]

        assert len(output.claims) == 0
        assert len(output.jargon) == 0
        assert len(output.people) == 0
        assert len(output.mental_models) == 0


class TestStoreTranscript:
    """Test storing transcript references."""

    def test_store_transcript_creates_episode(self, test_db_service):
        """Test that storing transcript creates episode if needed."""
        episode_id = "episode_transcript_test"
        transcript_path = "/path/to/transcript.md"

        store_transcript(test_db_service, episode_id, transcript_path)

        # Verify episode exists
        with test_db_service.get_session() as session:
            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None
            assert transcript_path in episode.description

    def test_store_transcript_updates_existing_episode(self, test_db_service):
        """Test that storing transcript updates existing episode."""
        episode_id = "episode_existing"

        # Create media source and episode first
        from src.knowledge_system.database.models import MediaSource

        with test_db_service.get_session() as session:
            # Create media source
            media_source = MediaSource(
                media_id="existing",
                source_type="youtube",
                title="Existing Media",
                url="https://youtube.com/watch?v=existing",
            )
            session.add(media_source)
            session.flush()

            # Create episode
            episode = Episode(
                episode_id=episode_id,
                video_id="existing",
                title="Existing Episode",
                description="Original description",
            )
            session.add(episode)
            session.commit()

        # Store transcript
        transcript_path = "/path/to/transcript.md"
        store_transcript(test_db_service, episode_id, transcript_path)

        # Verify description was updated
        with test_db_service.get_session() as session:
            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert "Original description" in episode.description
            assert transcript_path in episode.description


class TestGetEpisodeSummary:
    """Test episode summary statistics."""

    def test_get_episode_summary(self, test_db_service, sample_miner_output):
        """Test getting summary statistics for an episode."""
        episode_id = "episode_summary_test"

        # Store data
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Get summary
        summary = get_episode_summary(test_db_service, episode_id)

        assert summary["episode_id"] == episode_id
        assert summary["claims_count"] == 2
        assert summary["jargon_count"] == 1
        assert summary["people_count"] == 1
        assert summary["concepts_count"] == 1
        assert summary["total_extractions"] == 5

    def test_get_episode_summary_empty(self, test_db_service):
        """Test summary for episode with no data."""
        episode_id = "episode_empty_summary"

        summary = get_episode_summary(test_db_service, episode_id)

        assert summary["claims_count"] == 0
        assert summary["total_extractions"] == 0


class TestClearEpisodeData:
    """Test clearing episode data."""

    def test_clear_episode_data(self, test_db_service, sample_miner_output):
        """Test clearing all data for an episode."""
        episode_id = "episode_clear_test"

        # Store data
        store_mining_results(test_db_service, episode_id, [sample_miner_output])

        # Verify data exists
        summary_before = get_episode_summary(test_db_service, episode_id)
        assert summary_before["total_extractions"] > 0

        # Clear data
        clear_episode_data(test_db_service, episode_id)

        # Verify data is gone
        summary_after = get_episode_summary(test_db_service, episode_id)
        assert summary_after["total_extractions"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
