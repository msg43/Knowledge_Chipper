#!/usr/bin/env python3
"""
Validation script for HCE migration data integrity.

This script validates that the migration from legacy summarization to HCE
was successful and that data integrity is maintained.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database import DatabaseService
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class HCEMigrationValidator:
    """Validates HCE migration data integrity."""

    def __init__(self, db_path: str | None = None):
        """Initialize validator with database."""
        self.db = DatabaseService(db_path)
        self.validation_results = {
            "total_videos": 0,
            "legacy_summaries": 0,
            "hce_summaries": 0,
            "migration_issues": [],
            "data_integrity_issues": [],
            "performance_metrics": {},
        }

    def validate_migration(self) -> dict:
        """Run comprehensive migration validation.

        Returns:
            Dictionary with validation results
        """
        logger.info("Starting HCE migration validation...")

        # 1. Count and categorize summaries
        self._validate_summary_counts()

        # 2. Validate HCE data structure
        self._validate_hce_data_structure()

        # 3. Check data integrity
        self._validate_data_integrity()

        # 4. Validate database schema
        self._validate_database_schema()

        # 5. Performance validation
        self._validate_performance()

        # Generate report
        return self._generate_validation_report()

    def _validate_summary_counts(self) -> None:
        """Validate summary counts and types."""
        try:
            with self.db.get_session() as session:
                from knowledge_system.database.models import Summary, Video

                # Count total videos
                total_videos = session.query(Video).count()
                self.validation_results["total_videos"] = total_videos

                # Count summaries by type
                legacy_count = (
                    session.query(Summary)
                    .filter(Summary.processing_type == "legacy")
                    .count()
                )

                hce_count = (
                    session.query(Summary)
                    .filter(Summary.processing_type == "hce")
                    .count()
                )

                self.validation_results["legacy_summaries"] = legacy_count
                self.validation_results["hce_summaries"] = hce_count

                logger.info(
                    f"Found {total_videos} videos, {legacy_count} legacy summaries, {hce_count} HCE summaries"
                )

        except Exception as e:
            self.validation_results["migration_issues"].append(
                f"Summary count validation failed: {e}"
            )

    def _validate_hce_data_structure(self) -> None:
        """Validate HCE data JSON structure."""
        try:
            with self.db.get_session() as session:
                from knowledge_system.database.models import Summary

                hce_summaries = (
                    session.query(Summary)
                    .filter(Summary.processing_type == "hce")
                    .all()
                )

                invalid_hce_data = []

                for summary in hce_summaries:
                    if not summary.hce_data_json:
                        invalid_hce_data.append(
                            f"Summary {summary.summary_id} has no HCE data"
                        )
                        continue

                    try:
                        # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
                        hce_data = summary.hce_data_json

                        # Validate required fields
                        required_fields = [
                            "claims",
                            "people",
                            "concepts",
                            "relations",
                            "contradictions",
                        ]
                        for field in required_fields:
                            if field not in hce_data:
                                invalid_hce_data.append(
                                    f"Summary {summary.summary_id} missing field: {field}"
                                )

                        # Validate claims structure
                        claims = hce_data.get("claims", [])
                        for i, claim in enumerate(claims):
                            if not isinstance(claim, dict):
                                invalid_hce_data.append(
                                    f"Summary {summary.summary_id} claim {i} is not a dict"
                                )
                                continue

                            if "canonical" not in claim:
                                invalid_hce_data.append(
                                    f"Summary {summary.summary_id} claim {i} missing canonical text"
                                )

                            if "tier" not in claim or claim["tier"] not in [
                                "A",
                                "B",
                                "C",
                            ]:
                                invalid_hce_data.append(
                                    f"Summary {summary.summary_id} claim {i} has invalid tier"
                                )

                    except json.JSONDecodeError as e:
                        invalid_hce_data.append(
                            f"Summary {summary.summary_id} has invalid JSON: {e}"
                        )

                if invalid_hce_data:
                    self.validation_results["data_integrity_issues"].extend(
                        invalid_hce_data
                    )
                else:
                    logger.info(
                        f"All {len(hce_summaries)} HCE summaries have valid data structure"
                    )

        except Exception as e:
            self.validation_results["migration_issues"].append(
                f"HCE data structure validation failed: {e}"
            )

    def _validate_data_integrity(self) -> None:
        """Validate data integrity across tables."""
        try:
            with self.db.get_session() as session:
                from knowledge_system.database.models import Summary, Transcript, Video

                # Check for orphaned summaries
                orphaned_summaries = (
                    session.query(Summary)
                    .filter(~Summary.video_id.in_(session.query(Video.video_id)))
                    .count()
                )

                if orphaned_summaries > 0:
                    self.validation_results["data_integrity_issues"].append(
                        f"Found {orphaned_summaries} orphaned summaries"
                    )

                # Check for videos without transcripts or summaries
                videos_without_content = (
                    session.query(Video)
                    .filter(
                        ~Video.video_id.in_(session.query(Transcript.video_id)),
                        ~Video.video_id.in_(session.query(Summary.video_id)),
                    )
                    .count()
                )

                if videos_without_content > 0:
                    logger.warning(
                        f"Found {videos_without_content} videos without transcripts or summaries"
                    )

                logger.info("Data integrity validation completed")

        except Exception as e:
            self.validation_results["migration_issues"].append(
                f"Data integrity validation failed: {e}"
            )

    def _validate_database_schema(self) -> None:
        """Validate database schema for HCE compatibility."""
        try:
            with self.db.get_session() as session:
                # Check if HCE columns exist
                result = session.execute("PRAGMA table_info(summaries)")
                columns = [row[1] for row in result.fetchall()]

                required_hce_columns = ["processing_type", "hce_data_json"]
                missing_columns = [
                    col for col in required_hce_columns if col not in columns
                ]

                if missing_columns:
                    self.validation_results["migration_issues"].append(
                        f"Missing HCE columns in summaries table: {missing_columns}"
                    )
                else:
                    logger.info("Database schema validation passed")

        except Exception as e:
            self.validation_results["migration_issues"].append(
                f"Schema validation failed: {e}"
            )

    def _validate_performance(self) -> None:
        """Validate performance metrics."""
        try:
            import time

            # Test database query performance
            start_time = time.time()
            with self.db.get_session() as session:
                from knowledge_system.database.models import Summary

                # Run a complex query
                hce_summaries = (
                    session.query(Summary)
                    .filter(Summary.processing_type == "hce")
                    .limit(100)
                    .all()
                )

                query_time = time.time() - start_time

                self.validation_results["performance_metrics"][
                    "query_time"
                ] = query_time
                self.validation_results["performance_metrics"][
                    "hce_summaries_queried"
                ] = len(hce_summaries)

                if query_time > 5.0:  # Should be fast
                    self.validation_results["migration_issues"].append(
                        f"Database query performance is slow: {query_time:.2f}s"
                    )

                logger.info(
                    f"Database query performance: {query_time:.3f}s for {len(hce_summaries)} summaries"
                )

        except Exception as e:
            self.validation_results["migration_issues"].append(
                f"Performance validation failed: {e}"
            )

    def _generate_validation_report(self) -> dict:
        """Generate final validation report."""
        results = self.validation_results

        # Calculate success metrics
        total_issues = len(results["migration_issues"]) + len(
            results["data_integrity_issues"]
        )
        success_rate = max(0, 100 - (total_issues * 10))  # Rough success calculation

        results["validation_summary"] = {
            "success_rate": success_rate,
            "total_issues": total_issues,
            "migration_successful": total_issues == 0,
            "recommendations": [],
        }

        # Add recommendations based on findings
        if results["hce_summaries"] == 0 and results["total_videos"] > 0:
            results["validation_summary"]["recommendations"].append(
                "No HCE summaries found. Run HCE processing on existing content."
            )

        if results["legacy_summaries"] > results["hce_summaries"]:
            results["validation_summary"]["recommendations"].append(
                "More legacy summaries than HCE summaries. Consider migrating more content."
            )

        if total_issues > 0:
            results["validation_summary"]["recommendations"].append(
                "Address migration and data integrity issues before production deployment."
            )

        return results

    def print_report(self) -> None:
        """Print a human-readable validation report."""
        results = self.validation_results
        summary = results["validation_summary"]

        print("\n" + "=" * 60)
        print("🔍 HCE MIGRATION VALIDATION REPORT")
        print("=" * 60)

        print(f"\n📊 Summary Statistics:")
        print(f"   • Total Videos: {results['total_videos']}")
        print(f"   • Legacy Summaries: {results['legacy_summaries']}")
        print(f"   • HCE Summaries: {results['hce_summaries']}")
        print(f"   • Success Rate: {summary['success_rate']:.1f}%")

        if results["performance_metrics"]:
            print(f"\n⚡ Performance Metrics:")
            for metric, value in results["performance_metrics"].items():
                if isinstance(value, float):
                    print(f"   • {metric}: {value:.3f}")
                else:
                    print(f"   • {metric}: {value}")

        if results["migration_issues"]:
            print(f"\n❌ Migration Issues ({len(results['migration_issues'])}):")
            for issue in results["migration_issues"]:
                print(f"   • {issue}")

        if results["data_integrity_issues"]:
            print(
                f"\n⚠️ Data Integrity Issues ({len(results['data_integrity_issues'])}):"
            )
            for issue in results["data_integrity_issues"]:
                print(f"   • {issue}")

        if summary["recommendations"]:
            print(f"\n💡 Recommendations:")
            for rec in summary["recommendations"]:
                print(f"   • {rec}")

        print(
            f"\n✅ Migration Status: {'SUCCESSFUL' if summary['migration_successful'] else 'NEEDS ATTENTION'}"
        )
        print("=" * 60)


def main():
    """Run migration validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate HCE migration")
    parser.add_argument("--db", help="Database file path")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    validator = HCEMigrationValidator(args.db)
    results = validator.validate_migration()

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        validator.print_report()

    # Exit with error code if migration has issues
    if not results["validation_summary"]["migration_successful"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
