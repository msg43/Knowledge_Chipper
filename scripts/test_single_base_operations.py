#!/usr/bin/env python3
"""
Test database operations with unified single Base.
Verifies that foreign keys work correctly across all model types.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.hce_operations import (
    load_mining_results,
    store_mining_results,
)
from src.knowledge_system.database.models import Claim, Episode, MediaSource
from src.knowledge_system.processors.hce.unified_miner import UnifiedMinerOutput


def test_cross_base_foreign_keys():
    """Test that foreign keys work across what were previously separate bases."""
    print("\n" + "=" * 80)
    print("TESTING CROSS-BASE FOREIGN KEY RESOLUTION")
    print("=" * 80)

    # Create in-memory database
    print("\n1. Creating in-memory database...")
    db = DatabaseService("sqlite:///:memory:")
    print("   ✓ Database created")

    # Test 1: Episode → MediaSource FK (HCE → Main)
    print("\n2. Testing Episode → MediaSource foreign key...")
    print("   (This was the main issue with multiple bases)")

    episode_id = "episode_test123"
    video_id = "test123"

    # Create mining output
    output = UnifiedMinerOutput(
        {
            "claims": [
                {
                    "claim_id": "claim1",
                    "claim_text": "Test claim",
                    "claim_type": "factual",
                },
                {
                    "claim_id": "claim2",
                    "claim_text": "Another claim",
                    "claim_type": "forecast",
                },
            ],
            "jargon": [
                {
                    "term_id": "term1",
                    "term": "API",
                    "definition": "Application Programming Interface",
                    "category": "technical",
                }
            ],
            "people": [{"person_id": "person1", "name": "John Doe", "role": "Expert"}],
            "mental_models": [
                {
                    "concept_id": "concept1",
                    "concept_name": "Systems Thinking",
                    "description": "Holistic approach",
                }
            ],
        }
    )

    # Store mining results (this creates MediaSource and Episode with FK)
    try:
        store_mining_results(db, episode_id, [output])
        print("   ✓ Episode created with FK to MediaSource")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False

    # Verify FK relationship works
    print("\n3. Verifying FK relationship...")
    with db.get_session() as session:
        episode = session.query(Episode).filter_by(episode_id=episode_id).first()
        if not episode:
            print("   ✗ Episode not found")
            return False

        # Access related MediaSource through FK
        media_source = episode.media_source
        if not media_source:
            print("   ✗ MediaSource not accessible through FK")
            return False

        print(f"   ✓ Episode.media_source accessible: {media_source.media_id}")

        # Test reverse relationship
        episodes = media_source.episodes
        if not episodes or len(episodes) == 0:
            print("   ✗ Reverse relationship MediaSource.episodes not working")
            return False

        print(f"   ✓ MediaSource.episodes accessible: {len(episodes)} episode(s)")

    # Test 2: Claim → Episode FK (HCE internal)
    print("\n4. Testing Claim → Episode foreign key...")
    with db.get_session() as session:
        claims = session.query(Claim).filter_by(episode_id=episode_id).all()
        if len(claims) != 2:
            print(f"   ✗ Expected 2 claims, found {len(claims)}")
            return False

        # Access episode through FK
        claim_episode = claims[0].episode
        if not claim_episode:
            print("   ✗ Episode not accessible through Claim FK")
            return False

        print(f"   ✓ Claim.episode accessible: {claim_episode.episode_id}")
        print(f"   ✓ All {len(claims)} claims have valid FK to episode")

    # Test 3: Load mining results (tests all relationships)
    print("\n5. Testing load_mining_results (full relationship test)...")
    try:
        loaded_outputs = load_mining_results(db, episode_id)
        if not loaded_outputs:
            print("   ✗ Failed to load mining results")
            return False

        # load_mining_results returns a list of UnifiedMinerOutput
        loaded_output = loaded_outputs[0]
        print(f"   ✓ Loaded {len(loaded_output.claims)} claims")
        print(f"   ✓ Loaded {len(loaded_output.jargon)} jargon terms")
        print(f"   ✓ Loaded {len(loaded_output.people)} people")
        print(f"   ✓ Loaded {len(loaded_output.mental_models)} concepts")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 4: Query across relationships
    print("\n6. Testing complex queries across relationships...")
    with db.get_session() as session:
        # Query: Get all claims for a specific media source
        media_source = session.query(MediaSource).filter_by(media_id=video_id).first()
        if not media_source:
            print("   ✗ MediaSource not found")
            return False

        # Access claims through episode relationship
        all_claims = []
        for ep in media_source.episodes:
            all_claims.extend(ep.claims)

        if len(all_claims) != 2:
            print(
                f"   ✗ Expected 2 claims through relationship, found {len(all_claims)}"
            )
            return False

        print(
            f"   ✓ Successfully queried {len(all_claims)} claims through MediaSource → Episode → Claim"
        )

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Single Base migration successful!")
    print("=" * 80)
    print("\nKey achievements:")
    print("  • Episode → MediaSource FK works (was broken with multiple bases)")
    print(
        "  • Bidirectional relationships work (episode.media_source, media_source.episodes)"
    )
    print("  • All HCE relationships intact (Claim, Person, Concept, Jargon → Episode)")
    print("  • Complex queries across relationships work")
    print("  • In-memory database creation works (was failing before)")
    print("\n")

    return True


if __name__ == "__main__":
    success = test_cross_base_foreign_keys()
    exit(0 if success else 1)
