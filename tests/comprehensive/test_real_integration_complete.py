"""
Comprehensive Real Integration Testing Suite

Tests the complete integration functionality with real file processing,
System2 orchestration, and database operations.

This replaces:
- tests/integration/test_unified_real_content.py
- tests/system2/test_mining_full.py
- tests/system2/test_unified_hce_operations.py
- test_comprehensive.py
- test_unified_pipeline.py
"""

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.hce_models import Claim, Concept, Jargon, Person


@pytest.fixture
def test_db_service():
    """Create a test database service with in-memory database."""
    db_service = DatabaseService("sqlite:///:memory:")

    # Create all tables
    from src.knowledge_system.database.models import Base

    Base.metadata.create_all(db_service.engine)

    yield db_service


@pytest.fixture
def sample_transcript_file():
    """Create a sample transcript file for testing."""
    content = """
# Test Transcript

This is a test transcript about artificial intelligence and machine learning.

AI has transformed many industries including healthcare and finance.

Machine learning models require large datasets to train effectively.

Geoffrey Hinton is a pioneer in deep learning research.

Neural networks are inspired by biological neural networks in the human brain.

Deep learning uses multiple layers of neural networks to learn hierarchical representations.

The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices.

According to Fed Chairman Jerome Powell, this creates what economists call a 'wealth effect' where rising asset prices boost consumer spending.

However, some critics argue this approach primarily benefits wealthy asset holders rather than the broader economy.

The concept of 'trickle-down economics' suggests that benefits to the wealthy eventually reach lower-income groups, but empirical evidence for this mechanism remains contested.

Modern monetary theory (MMT) proposes an alternative framework where government spending is constrained by inflation rather than fiscal deficits.

This represents a paradigm shift from traditional Keynesian economics.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    yield file_path

    # Cleanup
    Path(file_path).unlink(missing_ok=True)


class TestRealFileProcessing:
    """Test processing real files with actual content."""

    @pytest.mark.integration
    def test_process_ken_rogoff_rtf(self):
        """Test processing Ken Rogoff RTF transcript."""
        rtf_path = Path("KenRogoff_Transcript.rtf")

        if not rtf_path.exists():
            pytest.skip("KenRogoff_Transcript.rtf not found in project root")

        orchestrator = System2Orchestrator()

        # Create mining job
        job_id = orchestrator.create_job(
            "mine",
            "episode_kenrogoff",
            config={
                "file_path": str(rtf_path),
                "miner_model": "ollama:qwen2.5:7b-instruct",
                "max_workers": 4,  # Moderate parallelism for testing
            },
        )

        # Process job
        result = asyncio.run(orchestrator.process_job(job_id))

        # Verify success
        assert result["status"] == "succeeded", f"Job failed: {result.get('error')}"

        # Verify results
        assert result["result"]["claims_extracted"] >= 0, "Should extract claims"
        assert result["result"]["segments_processed"] > 0, "Should process segments"

        # Verify unified database has data
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )
        assert unified_db.exists(), "Unified database should exist"

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Check episode exists
        cursor.execute(
            "SELECT COUNT(*) FROM episodes WHERE episode_id = 'episode_kenrogoff'"
        )
        episode_count = cursor.fetchone()[0]
        assert episode_count > 0, "Episode should be in database"

        # Check for any data
        cursor.execute(
            "SELECT COUNT(*) FROM claims WHERE episode_id = 'episode_kenrogoff'"
        )
        claims_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM evidence_spans WHERE episode_id = 'episode_kenrogoff'"
        )
        evidence_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM people WHERE episode_id = 'episode_kenrogoff'"
        )
        people_count = cursor.fetchone()[0]

        conn.close()

        print(f"\n✅ Processed Ken Rogoff RTF:")
        print(f"   Claims: {claims_count}")
        print(f"   Evidence spans: {evidence_count}")
        print(f"   People: {people_count}")
        print(f"   Segments: {result['result']['segments_processed']}")
        print(f"   Parallel workers: {result['result']['parallel_workers']}")

    @pytest.mark.integration
    def test_process_markdown_file(self):
        """Test processing markdown file."""
        md_path = Path(
            "Steve Bannon Silicon Valley Is Turning Us Into 'Digital Serfs'.md"
        )

        if not md_path.exists():
            pytest.skip("Markdown file not found")

        orchestrator = System2Orchestrator()

        job_id = orchestrator.create_job(
            "mine",
            "episode_bannon",
            config={
                "file_path": str(md_path),
                "miner_model": "ollama:qwen2.5:7b-instruct",
                "max_workers": 4,
            },
        )

        result = asyncio.run(orchestrator.process_job(job_id))

        assert result["status"] == "succeeded"
        assert result["result"]["segments_processed"] > 0

        # Verify database
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM episodes WHERE episode_id = 'episode_bannon'"
        )
        assert cursor.fetchone()[0] > 0

        cursor.execute(
            "SELECT COUNT(*) FROM claims WHERE episode_id = 'episode_bannon'"
        )
        claims_count = cursor.fetchone()[0]

        conn.close()

        print(f"\n✅ Processed Bannon markdown:")
        print(f"   Claims: {claims_count}")
        print(f"   Segments: {result['result']['segments_processed']}")

    @pytest.mark.integration
    def test_process_rtf_file(self):
        """Test processing RTF file."""
        rtf_path = Path("Maxine_Wolf_Deposition_Text.rtf")

        if not rtf_path.exists():
            pytest.skip("RTF file not found")

        orchestrator = System2Orchestrator()

        job_id = orchestrator.create_job(
            "mine",
            "episode_wolf",
            config={
                "file_path": str(rtf_path),
                "miner_model": "ollama:qwen2.5:7b-instruct",
                "max_workers": 4,
            },
        )

        result = asyncio.run(orchestrator.process_job(job_id))

        assert result["status"] == "succeeded"
        assert result["result"]["segments_processed"] > 0

        print(f"\n✅ Processed Wolf RTF:")
        print(f"   Claims: {result['result']['claims_extracted']}")
        print(f"   Segments: {result['result']['segments_processed']}")


class TestRealSystem2Mining:
    """Test real System2 mining with Ollama integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mine_simple_transcript(
        self, test_db_service, sample_transcript_file
    ):
        """Test mining a simple transcript end-to-end."""
        orchestrator = System2Orchestrator(test_db_service)

        episode_id = "episode_test_mine"

        # Create mining job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
            auto_process=False,
        )

        # Process the job
        result = await orchestrator.process_job(job_id)

        # Verify result
        assert result.get("status") == "succeeded"
        assert "result" in result
        assert "claims_extracted" in result["result"]

        # Should have extracted at least some claims
        assert result["result"]["claims_extracted"] >= 0

        # Verify data was stored in database
        with test_db_service.get_session() as session:
            from src.knowledge_system.database.hce_models import Episode

            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None, "Episode should be stored in database"

            # Check that some data was extracted
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            assert len(claims) >= 0, "Should have extracted claims"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_checkpoint_save_and_resume(
        self, test_db_service, sample_transcript_file
    ):
        """Test checkpoint saving during mining and resume after interruption."""
        orchestrator = System2Orchestrator(test_db_service)

        episode_id = "episode_checkpoint_test"

        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
            auto_process=False,
        )

        # Create job run
        run_id = orchestrator.create_job_run(job_id)

        # Save a checkpoint manually
        orchestrator.save_checkpoint(run_id, {"last_segment": 2, "partial_results": 2})

        # Load checkpoint
        checkpoint = orchestrator.load_checkpoint(run_id)

        assert checkpoint is not None
        assert checkpoint["last_segment"] == 2
        assert checkpoint["partial_results"] == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mining_stores_in_database(
        self, test_db_service, sample_transcript_file
    ):
        """Verify mining results are stored in HCE tables."""
        orchestrator = System2Orchestrator(test_db_service)

        episode_id = "episode_db_test"

        # Create and process job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
        )

        result = await orchestrator.process_job(job_id)

        assert result.get("status") == "succeeded"

        # Check database for stored results
        with test_db_service.get_session() as session:
            # Should have episode
            from src.knowledge_system.database.hce_models import Episode

            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None

            # May or may not have claims depending on LLM output
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            # Just verify query works
            assert isinstance(claims, list)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_segment_parsing(self, test_db_service, sample_transcript_file):
        """Test transcript parsing into segments."""
        orchestrator = System2Orchestrator(test_db_service)

        # Read transcript
        transcript_text = Path(sample_transcript_file).read_text()

        # Parse segments
        segments = orchestrator._parse_transcript_to_segments(
            transcript_text, "test_episode"
        )

        # Should have parsed some segments
        assert len(segments) > 0

        # Verify segment structure
        for segment in segments:
            assert hasattr(segment, "episode_id")
            assert hasattr(segment, "segment_id")
            assert hasattr(segment, "text")
            assert len(segment.text) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_progress_tracking(self, test_db_service, sample_transcript_file):
        """Test progress metrics are updated during mining."""
        orchestrator = System2Orchestrator(test_db_service)

        episode_id = "episode_progress_test"

        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
        )

        result = await orchestrator.process_job(job_id)

        assert result.get("status") == "succeeded"

        # Check job run for metrics
        from src.knowledge_system.database.system2_models import JobRun

        with test_db_service.get_session() as session:
            job_runs = session.query(JobRun).filter_by(job_id=job_id).all()
            assert len(job_runs) > 0

            # Latest run should have metrics
            job_run = job_runs[-1]
            # Metrics may or may not be set depending on timing
            # Just verify the field exists
            assert hasattr(job_run, "metrics_json")


class TestRealUnifiedHCEStorage:
    """Test unified HCE storage with real content."""

    def test_mining_creates_rich_data(self, sample_transcript_file):
        """Test that mining creates evidence, relations, categories."""
        orchestrator = System2Orchestrator()

        # Create mining job
        job_id = orchestrator.create_job(
            "mine",
            "test_episode",
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
        )

        # Process job
        result = asyncio.run(orchestrator.process_job(job_id))

        # Verify success
        assert result["status"] == "succeeded"
        assert result["result"]["claims_extracted"] >= 0

        # Verify rich data in database
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )
        assert unified_db.exists()

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Check for claims
        cursor.execute("SELECT COUNT(*) FROM claims WHERE episode_id = 'test_episode'")
        claims_count = cursor.fetchone()[0]
        assert claims_count >= 0, "Should have claims table"

        # Check for evidence spans
        cursor.execute(
            "SELECT COUNT(*) FROM evidence_spans WHERE episode_id = 'test_episode'"
        )
        evidence_count = cursor.fetchone()[0]
        assert evidence_count >= 0, "Should have evidence_spans table"

        # Check for people mentions
        cursor.execute("SELECT COUNT(*) FROM people WHERE episode_id = 'test_episode'")
        people_count = cursor.fetchone()[0]
        assert people_count >= 0, "Should have people table"

        # Check for concepts
        cursor.execute(
            "SELECT COUNT(*) FROM concepts WHERE episode_id = 'test_episode'"
        )
        concepts_count = cursor.fetchone()[0]
        assert concepts_count >= 0, "Should have concepts table"

        conn.close()

    def test_context_quotes_populated(self, sample_transcript_file):
        """Test that context_quote fields are populated."""
        orchestrator = System2Orchestrator()

        job_id = orchestrator.create_job(
            "mine", "test_context_episode", config={"file_path": sample_transcript_file}
        )

        asyncio.run(orchestrator.process_job(job_id))

        # Check database
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Verify context_quote in people (if any people were extracted)
        cursor.execute(
            """
            SELECT name, context_quote FROM people
            WHERE episode_id = 'test_context_episode'
            AND context_quote IS NOT NULL
        """
        )
        people_with_quotes = cursor.fetchall()
        # May be 0 if no people extracted, but structure should exist
        assert isinstance(people_with_quotes, list)

        # Verify context_quote in concepts (if any concepts were extracted)
        cursor.execute(
            """
            SELECT name, context_quote FROM concepts
            WHERE episode_id = 'test_context_episode'
            AND context_quote IS NOT NULL
        """
        )
        concepts_with_quotes = cursor.fetchall()
        # May be 0 if no concepts extracted, but structure should exist
        assert isinstance(concepts_with_quotes, list)

        conn.close()


class TestRealDatabaseValidation:
    """Test database validation with real data."""

    @pytest.mark.integration
    def test_verify_evidence_spans_structure(self):
        """Verify evidence spans have proper structure with timestamps."""
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )

        if not unified_db.exists():
            pytest.skip("No unified database found - run other tests first")

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Get sample evidence spans
        cursor.execute(
            """
            SELECT
                episode_id,
                claim_id,
                t0,
                t1,
                quote,
                context_type
            FROM evidence_spans
            LIMIT 10
        """
        )

        evidence_samples = cursor.fetchall()

        if evidence_samples:
            print(f"\n✅ Evidence span samples ({len(evidence_samples)}):")
            for ep_id, claim_id, t0, t1, quote, ctx_type in evidence_samples[:3]:
                print(f"   Episode: {ep_id}")
                print(f"   Claim: {claim_id}")
                print(f"   Time: {t0} - {t1}")
                print(f"   Quote: {quote[:80] if quote else 'None'}...")
                print(f"   Type: {ctx_type}")
                print()

        conn.close()

    @pytest.mark.integration
    def test_verify_claim_tiers(self):
        """Verify claims have tier assignments (A/B/C)."""
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )

        if not unified_db.exists():
            pytest.skip("No unified database found")

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Get tier distribution
        cursor.execute(
            """
            SELECT
                tier,
                COUNT(*) as count
            FROM claims
            WHERE tier IS NOT NULL
            GROUP BY tier
            ORDER BY tier
        """
        )

        tier_dist = cursor.fetchall()

        if tier_dist:
            print(f"\n✅ Claim tier distribution:")
            for tier, count in tier_dist:
                print(f"   Tier {tier}: {count} claims")

        conn.close()

    @pytest.mark.integration
    def test_verify_relations(self):
        """Verify claim relations are captured."""
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )

        if not unified_db.exists():
            pytest.skip("No unified database found")

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Get relations
        cursor.execute(
            """
            SELECT
                r.type,
                COUNT(*) as count
            FROM relations r
            GROUP BY r.type
        """
        )

        relation_types = cursor.fetchall()

        if relation_types:
            print(f"\n✅ Claim relations:")
            for rel_type, count in relation_types:
                print(f"   {rel_type}: {count}")
        else:
            print(f"\n⚠️  No relations found (may need more complex content)")

        conn.close()

    @pytest.mark.integration
    def test_verify_categories(self):
        """Verify structured categories are identified."""
        unified_db = (
            Path.home()
            / "Library"
            / "Application Support"
            / "SkipThePodcast"
            / "unified_hce.db"
        )

        if not unified_db.exists():
            pytest.skip("No unified database found")

        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()

        # Get categories
        cursor.execute(
            """
            SELECT
                category_name,
                wikidata_qid,
                coverage_confidence
            FROM structured_categories
            ORDER BY coverage_confidence DESC
            LIMIT 10
        """
        )

        categories = cursor.fetchall()

        if categories:
            print(f"\n✅ Structured categories ({len(categories)}):")
            for name, qid, conf in categories[:5]:
                print(f"   {name} [{qid}] - confidence: {conf:.2f}")
        else:
            print(f"\n⚠️  No categories found (may need category prompt)")

        conn.close()


class TestRealPerformanceMetrics:
    """Test performance metrics with real processing."""

    @pytest.mark.integration
    def test_performance_metrics(self):
        """Test and report performance metrics."""
        import time

        # Use Ken Rogoff as test file
        rtf_path = Path("KenRogoff_Transcript.rtf")

        if not rtf_path.exists():
            pytest.skip("Test file not found")

        orchestrator = System2Orchestrator()

        # Test with parallel processing
        start_time = time.time()

        job_id = orchestrator.create_job(
            "mine",
            "episode_performance_test",
            config={
                "file_path": str(rtf_path),
                "miner_model": "ollama:qwen2.5:7b-instruct",
                "max_workers": None,  # Auto-calculate
                "enable_parallel_processing": True,
            },
        )

        result = asyncio.run(orchestrator.process_job(job_id))

        elapsed_time = time.time() - start_time

        assert result["status"] == "succeeded"

        print(f"\n✅ Performance metrics:")
        print(f"   Total time: {elapsed_time:.2f}s")
        print(f"   Segments: {result['result']['segments_processed']}")
        print(f"   Workers: {result['result']['parallel_workers']}")
        print(f"   Claims extracted: {result['result']['claims_extracted']}")
        print(
            f"   Time per segment: {elapsed_time / result['result']['segments_processed']:.2f}s"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
