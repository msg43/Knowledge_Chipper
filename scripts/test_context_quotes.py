#!/usr/bin/env python3
"""
Test script to verify context_quote fields are populated in the database during mining.

This script creates a test episode with mock mining data and verifies that
the context_quote fields are correctly stored in the database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database.service import DatabaseService
from knowledge_system.database.hce_operations import store_mining_results
from knowledge_system.processors.hce.unified_miner import UnifiedMinerOutput


def create_test_mining_output():
    """Create a test mining output with context quotes."""
    test_data = {
        "claims": [
            {
                "claim_text": "Test claim about technology",
                "claim_type": "factual",
                "stance": "asserts",
                "timestamp": "00:00",
            }
        ],
        "jargon": [
            {
                "term": "API",
                "definition": "Application Programming Interface",
                "context_quote": "The API allows developers to integrate our service easily",
                "timestamp": "01:30",
            },
            {
                "term": "Machine Learning",
                "definition": "A type of artificial intelligence",
                "context_quote": "We use machine learning to analyze patterns in the data",
                "timestamp": "02:45",
            },
        ],
        "people": [
            {
                "name": "Elon Musk",
                "role_or_description": "CEO of Tesla and SpaceX",
                "context_quote": "Elon Musk recently announced plans for the new Tesla model",
                "timestamp": "03:15",
            },
            {
                "name": "Marie Curie",
                "role_or_description": "Nobel Prize winning physicist",
                "context_quote": "Marie Curie was the first woman to win a Nobel Prize",
                "timestamp": "04:00",
            },
        ],
        "mental_models": [
            {
                "name": "First Principles Thinking",
                "description": "Breaking down problems to their fundamental truths",
                "context_quote": "Using first principles thinking, we can question every assumption",
                "timestamp": "05:30",
            },
            {
                "name": "Compounding Effect",
                "description": "Small improvements accumulate over time",
                "context_quote": "The compounding effect shows that 1% improvement daily leads to 37x improvement yearly",
                "timestamp": "06:45",
            },
        ],
    }
    
    return UnifiedMinerOutput(test_data)


def test_context_quotes():
    """Test that context_quote fields are properly stored in the database."""
    print("=" * 80)
    print("Testing Context Quote Storage")
    print("=" * 80)
    
    # Initialize database service
    db_path = Path(__file__).parent.parent / "knowledge_system.db"
    db_url = f"sqlite:///{db_path}"
    db_service = DatabaseService(db_url)
    
    # Create test episode ID
    test_episode_id = "test_context_quotes_episode"
    test_video_id = "test_video_123"
    
    print(f"\n✓ Database initialized: {db_path}")
    print(f"✓ Test episode ID: {test_episode_id}")
    
    # Manually create media source and episode to avoid FK issues
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clean up any existing test data first
    cursor.execute("DELETE FROM episodes WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM media_sources WHERE media_id = ?", (test_video_id,))
    
    # Create media source
    cursor.execute("""
        INSERT INTO media_sources (media_id, source_type, title, url)
        VALUES (?, ?, ?, ?)
    """, (test_video_id, "youtube", "Test Video", "https://youtube.com/watch?v=test"))
    
    # Create episode
    cursor.execute("""
        INSERT INTO episodes (episode_id, video_id, title, recorded_at)
        VALUES (?, ?, ?, ?)
    """, (test_episode_id, test_video_id, "Test Episode", "2025-01-01T00:00:00"))
    
    conn.commit()
    conn.close()
    
    print("✓ Created test media source and episode")
    
    # Create test mining output
    miner_output = create_test_mining_output()
    print(f"\n✓ Created test mining output:")
    print(f"  - {len(miner_output.jargon)} jargon terms")
    print(f"  - {len(miner_output.people)} people")
    print(f"  - {len(miner_output.mental_models)} mental models")
    
    # Store mining results
    print(f"\n⏳ Storing mining results...")
    store_mining_results(db_service, test_episode_id, [miner_output])
    print("✓ Mining results stored")
    
    # Verify jargon context_quotes
    print("\n" + "=" * 80)
    print("Verifying Jargon Context Quotes")
    print("=" * 80)
    
    with db_service.get_session() as session:
        from knowledge_system.database.hce_models import Jargon
        
        jargon_items = session.query(Jargon).filter_by(episode_id=test_episode_id).all()
        
        if not jargon_items:
            print("❌ No jargon items found in database")
            return False
        
        all_passed = True
        for jargon in jargon_items:
            if jargon.context_quote:
                print(f"✓ {jargon.term}")
                print(f"  Definition: {jargon.definition}")
                print(f"  Context Quote: {jargon.context_quote[:80]}...")
            else:
                print(f"❌ {jargon.term} - Missing context_quote")
                all_passed = False
    
    # Verify people context_quotes
    print("\n" + "=" * 80)
    print("Verifying People Context Quotes")
    print("=" * 80)
    
    with db_service.get_session() as session:
        from knowledge_system.database.hce_models import Person
        
        people = session.query(Person).filter_by(episode_id=test_episode_id).all()
        
        if not people:
            print("❌ No people found in database")
            return False
        
        for person in people:
            if person.context_quote:
                print(f"✓ {person.name}")
                print(f"  Description: {person.description}")
                print(f"  Context Quote: {person.context_quote[:80]}...")
            else:
                print(f"❌ {person.name} - Missing context_quote")
                all_passed = False
    
    # Verify concepts (mental models) context_quotes
    print("\n" + "=" * 80)
    print("Verifying Mental Models Context Quotes")
    print("=" * 80)
    
    with db_service.get_session() as session:
        from knowledge_system.database.hce_models import Concept
        
        concepts = session.query(Concept).filter_by(episode_id=test_episode_id).all()
        
        if not concepts:
            print("❌ No concepts found in database")
            return False
        
        for concept in concepts:
            if concept.context_quote:
                print(f"✓ {concept.name}")
                print(f"  Description: {concept.description}")
                print(f"  Context Quote: {concept.context_quote[:80]}...")
            else:
                print(f"❌ {concept.name} - Missing context_quote")
                all_passed = False
    
    # Clean up test data
    print("\n" + "=" * 80)
    print("Cleaning Up Test Data")
    print("=" * 80)
    
    # Use SQL to clean up
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jargon WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM people WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM concepts WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM claims WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM episodes WHERE episode_id = ?", (test_episode_id,))
    cursor.execute("DELETE FROM media_sources WHERE media_id = ?", (test_video_id,))
    conn.commit()
    conn.close()
    print("✓ Test data cleaned up")
    
    # Final result
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Context quotes are being stored correctly!")
    else:
        print("❌ SOME TESTS FAILED - Context quotes are not being stored correctly")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = test_context_quotes()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

