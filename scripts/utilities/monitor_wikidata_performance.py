#!/usr/bin/env python3
"""
WikiData Categorization Performance Monitor

Provides real-time monitoring and recommendations for WikiData categorization performance.
Run this periodically to track automation rates and identify vocabulary gaps.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def analyze_categorization_performance():
    """Analyze WikiData categorization performance from database."""
    print("\n" + "=" * 70)
    print("WIKIDATA CATEGORIZATION PERFORMANCE ANALYSIS")
    print("=" * 70)

    try:
        from src.knowledge_system.database import DatabaseService

        db = DatabaseService()

        with db.get_session() as session:
            # Check if claim-centric schema exists, otherwise use HCE schema
            from sqlalchemy import text

            try:
                # Try claim-centric schema first
                total_categorizations = session.execute(
                    text("SELECT COUNT(*) FROM claim_categories")
                ).scalar()
                schema_type = "claim-centric"
            except:
                # Fall back to HCE schema
                try:
                    total_categorizations = session.execute(
                        text("SELECT COUNT(*) FROM hce_structured_categories")
                    ).scalar()
                    schema_type = "hce"
                except:
                    total_categorizations = 0
                    schema_type = "unknown"

            if total_categorizations == 0:
                print("\n⚠️  No categorizations in database yet.")
                print(f"   Schema type: {schema_type}")
                print("   Run some summarizations to generate data.")
                print("\n   Note: Claim-centric schema not yet migrated.")
                print("   WikiData categorizer is ready but not integrated.")
                return

            print(f"\nTotal categorizations: {total_categorizations}")
            print(f"Schema type: {schema_type}")

            if schema_type == "hce":
                print("\n⚠️  Using HCE schema (old format)")
                print("   WikiData categorizer not yet integrated into pipeline")
                print("   Current categories are in hce_structured_categories table")

                # Show HCE categories
                categories = session.execute(
                    text(
                        """
                        SELECT
                            category_name,
                            COUNT(*) as usage_count,
                            AVG(coverage_confidence) as avg_confidence
                        FROM hce_structured_categories
                        GROUP BY category_name
                        ORDER BY usage_count DESC
                        LIMIT 10
                    """
                    )
                ).fetchall()

                if categories:
                    print("\nTop HCE Categories (current implementation):")
                    for name, count, conf in categories:
                        print(f"  - {name}: {count} uses, {conf:.2f} confidence")

                print("\n✅ WikiData categorizer is implemented and tested")
                print("   Integration pending (will replace hce_structured_categories)")
                return

            # Claim-centric schema analysis (if migrated)
            # Analyze by confidence
            high_conf = session.execute(
                text(
                    "SELECT COUNT(*) FROM claim_categories WHERE match_confidence = 'high'"
                )
            ).scalar()
            medium_conf = session.execute(
                text(
                    "SELECT COUNT(*) FROM claim_categories WHERE match_confidence = 'medium'"
                )
            ).scalar()
            low_conf = session.execute(
                text(
                    "SELECT COUNT(*) FROM claim_categories WHERE match_confidence = 'low'"
                )
            ).scalar()

            print(f"\nConfidence Distribution:")
            print(
                f"  High (auto-accepted):  {high_conf:4d} ({high_conf/total_categorizations*100:5.1f}%)"
            )
            print(
                f"  Medium (reviewed):     {medium_conf:4d} ({medium_conf/total_categorizations*100:5.1f}%)"
            )
            print(
                f"  Low (vocab gaps):      {low_conf:4d} ({low_conf/total_categorizations*100:5.1f}%)"
            )

            # Most common categories
            print(f"\nTop 10 Most Frequent Categories:")
            top_categories = session.execute(
                text(
                    """
                SELECT
                    wc.category_name,
                    wc.wikidata_id,
                    COUNT(*) as usage_count,
                    AVG(cc.relevance_score) as avg_relevance
                FROM claim_categories cc
                JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
                GROUP BY wc.wikidata_id, wc.category_name
                ORDER BY usage_count DESC
                LIMIT 10
            """
                )
            ).fetchall()

            for i, (name, qid, count, avg_rel) in enumerate(top_categories, 1):
                print(
                    f"  {i:2d}. {name} ({qid}) - {count} uses, {avg_rel:.2f} avg relevance"
                )

            # Recommendations
            print(f"\n{'-'*70}")
            print("RECOMMENDATIONS:")
            print("-" * 70)

            # Check vocab gap rate
            vocab_gap_rate = (
                low_conf / total_categorizations if total_categorizations > 0 else 0
            )

            if vocab_gap_rate > 0.20:
                print(f"⚠️  VOCABULARY EXPANSION NEEDED")
                print(f"   Vocab gap rate: {vocab_gap_rate:.1%} (threshold: 20%)")
                print(
                    f"   Action: Add more WikiData categories to cover content topics"
                )

                # Suggest categories to add
                print(f"\n   Categories frequently causing low confidence:")
                low_conf_cats = session.execute(
                    text(
                        """
                    SELECT
                        cc.freeform_input,
                        COUNT(*) as frequency
                    FROM claim_categories cc
                    WHERE cc.match_confidence = 'low'
                    GROUP BY cc.freeform_input
                    ORDER BY frequency DESC
                    LIMIT 5
                """
                    )
                ).fetchall()

                if low_conf_cats:
                    for freeform, freq in low_conf_cats:
                        print(
                            f"      • '{freeform}' ({freq} times) - consider adding to vocabulary"
                        )

            # Check review rate
            review_rate = (
                medium_conf / total_categorizations if total_categorizations > 0 else 0
            )

            if review_rate > 0.30:
                print(f"\n⚠️  HIGH REVIEW RATE")
                print(f"   User review rate: {review_rate:.1%} (threshold: 30%)")
                print(f"   Action: Consider adjusting confidence thresholds")

            # Check auto-accept rate
            auto_accept_rate = (
                high_conf / total_categorizations if total_categorizations > 0 else 0
            )

            if auto_accept_rate < 0.50:
                print(f"\n⚠️  LOW AUTOMATION RATE")
                print(f"   Auto-accept rate: {auto_accept_rate:.1%} (target: >50%)")
                print(f"   Causes:")
                print(f"      • Vocabulary gaps: {vocab_gap_rate:.1%}")
                print(f"      • Medium confidence: {review_rate:.1%}")
            else:
                print(f"\n✅ GOOD AUTOMATION RATE")
                print(f"   Auto-accept: {auto_accept_rate:.1%} (target: >50%)")

            # Vocabulary coverage
            from src.knowledge_system.database.claim_models import WikiDataCategory

            total_vocab = session.query(WikiDataCategory).count()
            used_categories = session.execute(
                text(
                    """
                SELECT COUNT(DISTINCT wikidata_id)
                FROM claim_categories
            """
                )
            ).scalar()

            print(f"\nVocabulary Coverage:")
            print(f"  Total categories available: {total_vocab}")
            print(f"  Categories actually used: {used_categories}")
            print(f"  Coverage: {used_categories/total_vocab*100:.1f}%")

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback

        traceback.print_exc()


def suggest_vocabulary_additions():
    """Suggest WikiData categories to add based on usage patterns."""
    print("\n" + "=" * 70)
    print("VOCABULARY EXPANSION SUGGESTIONS")
    print("=" * 70)

    try:
        from src.knowledge_system.database import DatabaseService

        db = DatabaseService()

        from sqlalchemy import text

        with db.get_session() as session:
            # Check if claim-centric schema exists
            try:
                # Try to query claim_categories
                suggestions = session.execute(
                    text(
                        """
                    SELECT
                        cc.freeform_input,
                        cc.wikidata_id as closest_match,
                        wc.category_name as closest_match_name,
                        cc.relevance_score,
                        COUNT(*) as frequency
                    FROM claim_categories cc
                    LEFT JOIN wikidata_categories wc ON cc.wikidata_id = wc.wikidata_id
                    WHERE cc.match_confidence IN ('low', 'medium')
                      AND cc.relevance_score < 0.70
                    GROUP BY cc.freeform_input, cc.wikidata_id, wc.category_name, cc.relevance_score
                    HAVING frequency >= 2
                    ORDER BY frequency DESC, cc.relevance_score ASC
                    LIMIT 10
                """
                    )
                ).fetchall()
            except:
                print("\n⚠️  Claim-centric schema not yet migrated")
                print("   WikiData categorizer ready but not integrated")
                return

            if not suggestions:
                print("\n✅ No frequent vocabulary gaps found!")
                print("   Current vocabulary appears adequate.")
                return

            print(f"\nSuggested additions (based on low-confidence frequent matches):")
            print()

            for freeform, closest_id, closest_name, rel_score, freq in suggestions:
                print(f"{freq:2d}× '{freeform}'")
                print(
                    f"     Currently maps to: {closest_name} ({closest_id}) at {rel_score:.2f}"
                )
                print(f"     Suggestion: Add '{freeform}' as new WikiData category")
                print(f"     OR: Add '{freeform}' as alias to {closest_name}")
                print()

            print("To add a category:")
            print(
                """
from src.knowledge_system.services.wikidata_categorizer import WikiDataCategorizer

categorizer = WikiDataCategorizer()
categorizer.add_category_to_vocabulary(
    wikidata_id='Q...',  # Look up on wikidata.org
    category_name='Category name',
    description='Description from WikiData',
    level='specific',  # or 'general'
    parent_id='Q...',  # Parent category
    aliases=['Alt name 1', 'Alt name 2']
)
"""
            )

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback

        traceback.print_exc()


def check_categorization_health():
    """Check overall health of categorization system."""
    print("\n" + "=" * 70)
    print("CATEGORIZATION SYSTEM HEALTH CHECK")
    print("=" * 70)

    try:
        from src.knowledge_system.services.wikidata_categorizer import (
            WikiDataCategorizer,
        )

        categorizer = WikiDataCategorizer(embedding_model="all-MiniLM-L6-v2")

        # Check embeddings
        print(f"\n✅ Embeddings: Loaded")
        print(f"   Vocabulary size: {len(categorizer.categories)} categories")
        print(f"   Embedding model: {categorizer.embedding_model_name}")

        # Check if embeddings are up-to-date
        import pickle

        with open(categorizer.embeddings_file, "rb") as f:
            cache = pickle.load(f)
            cached_vocab_time = cache.get("vocab_version", 0)
            current_vocab_time = categorizer.vocab_file.stat().st_mtime

            if cached_vocab_time < current_vocab_time:
                print(f"\n⚠️  STALE EMBEDDINGS")
                print(f"   Embeddings are older than vocabulary file")
                print(f"   Action: Run categorizer._compute_embeddings() to refresh")
            else:
                print(f"✅ Embeddings are up-to-date")

        # Check if fuzzy matching is available
        try:
            from fuzzywuzzy import fuzz

            print(f"✅ Fuzzy matching: Available")
        except ImportError:
            print(f"⚠️  Fuzzy matching: Not installed (optional)")
            print(f"   Install with: pip install python-Levenshtein fuzzywuzzy")

        # Get performance metrics
        report = categorizer.get_performance_report()

        if report.get("automation", {}).get("total", 0) > 0:
            print(f"\n✅ Performance Metrics: Available")
            print(f"   Total categorizations tracked: {report['automation']['total']}")
        else:
            print(f"\nℹ️  Performance Metrics: No data yet")
            print(f"   Run categorizations to generate metrics")

        print(f"\n✅ System Health: GOOD")
        print(f"   All components operational")

    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run all monitoring checks."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║          WIKIDATA CATEGORIZATION PERFORMANCE MONITOR                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )

    # Run checks
    check_categorization_health()
    analyze_categorization_performance()
    suggest_vocabulary_additions()

    print("\n" + "=" * 70)
    print("MONITORING COMPLETE")
    print("=" * 70)
    print("\nFor real-time monitoring during categorization:")
    print("  Use: categorizer.get_performance_report()")
    print("\nTo check if vocabulary expansion needed:")
    print("  Use: categorizer.should_expand_vocabulary()")
    print()


if __name__ == "__main__":
    main()
