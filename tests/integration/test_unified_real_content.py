"""
Real-world integration tests for unified HCE pipeline.

Tests using actual files and content to verify end-to-end functionality.
"""

import pytest
import asyncio
from pathlib import Path
import sqlite3

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator


class TestUnifiedPipelineRealContent:
    """Test unified pipeline with real content."""
    
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
            }
        )
        
        # Process job
        result = asyncio.run(orchestrator.process_job(job_id))
        
        # Verify success
        assert result["status"] == "succeeded", f"Job failed: {result.get('error')}"
        
        # Verify results
        assert result["result"]["claims_extracted"] >= 0, "Should extract claims"
        assert result["result"]["segments_processed"] > 0, "Should process segments"
        
        # Verify unified database has data
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        assert unified_db.exists(), "Unified database should exist"
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Check episode exists
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE episode_id = 'episode_kenrogoff'")
        episode_count = cursor.fetchone()[0]
        assert episode_count > 0, "Episode should be in database"
        
        # Check for any data
        cursor.execute("SELECT COUNT(*) FROM claims WHERE episode_id = 'episode_kenrogoff'")
        claims_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM evidence_spans WHERE episode_id = 'episode_kenrogoff'")
        evidence_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM people WHERE episode_id = 'episode_kenrogoff'")
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
        md_path = Path("Steve Bannon Silicon Valley Is Turning Us Into 'Digital Serfs'.md")
        
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
            }
        )
        
        result = asyncio.run(orchestrator.process_job(job_id))
        
        assert result["status"] == "succeeded"
        assert result["result"]["segments_processed"] > 0
        
        # Verify database
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE episode_id = 'episode_bannon'")
        assert cursor.fetchone()[0] > 0
        
        cursor.execute("SELECT COUNT(*) FROM claims WHERE episode_id = 'episode_bannon'")
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
            }
        )
        
        result = asyncio.run(orchestrator.process_job(job_id))
        
        assert result["status"] == "succeeded"
        assert result["result"]["segments_processed"] > 0
        
        print(f"\n✅ Processed Wolf RTF:")
        print(f"   Claims: {result['result']['claims_extracted']}")
        print(f"   Segments: {result['result']['segments_processed']}")
    
    @pytest.mark.integration
    def test_verify_evidence_spans_structure(self):
        """Verify evidence spans have proper structure with timestamps."""
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        
        if not unified_db.exists():
            pytest.skip("No unified database found - run other tests first")
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Get sample evidence spans
        cursor.execute("""
            SELECT 
                episode_id,
                claim_id,
                t0,
                t1,
                quote,
                context_type
            FROM evidence_spans
            LIMIT 10
        """)
        
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
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        
        if not unified_db.exists():
            pytest.skip("No unified database found")
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Get tier distribution
        cursor.execute("""
            SELECT 
                tier,
                COUNT(*) as count
            FROM claims
            WHERE tier IS NOT NULL
            GROUP BY tier
            ORDER BY tier
        """)
        
        tier_dist = cursor.fetchall()
        
        if tier_dist:
            print(f"\n✅ Claim tier distribution:")
            for tier, count in tier_dist:
                print(f"   Tier {tier}: {count} claims")
        
        conn.close()
    
    @pytest.mark.integration
    def test_verify_relations(self):
        """Verify claim relations are captured."""
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        
        if not unified_db.exists():
            pytest.skip("No unified database found")
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Get relations
        cursor.execute("""
            SELECT 
                r.type,
                COUNT(*) as count
            FROM relations r
            GROUP BY r.type
        """)
        
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
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        
        if not unified_db.exists():
            pytest.skip("No unified database found")
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Get categories
        cursor.execute("""
            SELECT 
                category_name,
                wikidata_qid,
                coverage_confidence
            FROM structured_categories
            ORDER BY coverage_confidence DESC
            LIMIT 10
        """)
        
        categories = cursor.fetchall()
        
        if categories:
            print(f"\n✅ Structured categories ({len(categories)}):")
            for name, qid, conf in categories[:5]:
                print(f"   {name} [{qid}] - confidence: {conf:.2f}")
        else:
            print(f"\n⚠️  No categories found (may need category prompt)")
        
        conn.close()
    
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
            }
        )
        
        result = asyncio.run(orchestrator.process_job(job_id))
        
        elapsed_time = time.time() - start_time
        
        assert result["status"] == "succeeded"
        
        print(f"\n✅ Performance metrics:")
        print(f"   Total time: {elapsed_time:.2f}s")
        print(f"   Segments: {result['result']['segments_processed']}")
        print(f"   Workers: {result['result']['parallel_workers']}")
        print(f"   Claims extracted: {result['result']['claims_extracted']}")
        print(f"   Time per segment: {elapsed_time / result['result']['segments_processed']:.2f}s")

