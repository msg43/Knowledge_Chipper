"""
Database management CLI commands for Knowledge System.

Provides commands for managing the SQLite database, regenerating files,
viewing statistics, and performing maintenance operations.
"""

from pathlib import Path

import click

from ..database import DatabaseService
from ..database.alembic_migrations import (
    DatabaseMigrationManager,
    check_schema_compatibility,
)
from ..logger import get_logger
from ..services.file_generation import FileGenerationService
from ..utils.cost_tracking import CostTracker
from ..utils.progress_tracker import ProgressTracker
from .common import CLIContext, pass_context

logger = get_logger(__name__)


@click.group()
@pass_context
def database(ctx: CLIContext):
    """Database management and file regeneration commands."""


@database.command()
@click.argument("video_id")
@click.option(
    "--output-dir", "-o", type=click.Path(), help="Output directory for generated files"
)
@click.option(
    "--formats",
    "-f",
    multiple=True,
    default=["md", "srt", "txt"],
    help="File formats to generate (md, srt, vtt, txt, json)",
)
@click.option(
    "--include-timestamps/--no-timestamps",
    default=True,
    help="Include timestamps in transcript",
)
@click.option(
    "--include-speakers/--no-speakers",
    default=True,
    help="Include speaker labels if available",
)
@pass_context
def regenerate(
    ctx: CLIContext,
    video_id: str,
    output_dir: str | None,
    formats: tuple,
    include_timestamps: bool,
    include_speakers: bool,
):
    """Regenerate all files for a specific video from database."""
    try:
        click.echo(f"🔄 Regenerating files for video: {video_id}")

        # Initialize services
        db = DatabaseService()
        file_service = FileGenerationService(
            database_service=db, output_dir=Path(output_dir) if output_dir else None
        )

        # Check if video exists
        video = db.get_video(video_id)
        if not video:
            click.echo(f"❌ Video {video_id} not found in database", err=True)
            ctx.exit(1)

        click.echo(f"📹 Video: {video.title}")

        generated_files = []

        # Generate transcript markdown
        if "md" in formats:
            click.echo("📝 Generating transcript markdown...")
            transcript_path = file_service.generate_transcript_markdown(
                video_id=video_id,
                include_timestamps=include_timestamps,
                include_speakers=include_speakers,
            )
            if transcript_path:
                generated_files.append(f"Transcript: {transcript_path}")
                click.echo(f"   ✅ {transcript_path}")
            else:
                click.echo("   ❌ Failed to generate transcript markdown")

        # Generate summary markdown
        if "md" in formats:
            click.echo("📊 Generating summary markdown...")
            summary_path = file_service.generate_summary_markdown(video_id=video_id)
            if summary_path:
                generated_files.append(f"Summary: {summary_path}")
                click.echo(f"   ✅ {summary_path}")
            else:
                click.echo("   ⚠️  No summary found or failed to generate")

        # Generate export files
        export_formats = [f for f in formats if f in ["srt", "vtt", "txt", "json"]]
        if export_formats:
            click.echo(f"📤 Generating export files: {', '.join(export_formats)}")
            export_files = file_service.generate_export_files(video_id, export_formats)

            for fmt, path in export_files.items():
                generated_files.append(f"{fmt.upper()}: {path}")
                click.echo(f"   ✅ {path}")

        # Summary
        click.echo(f"\n✅ Generated {len(generated_files)} files:")
        for file_info in generated_files:
            click.echo(f"   • {file_info}")

    except Exception as e:
        click.echo(f"❌ Failed to regenerate files: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option(
    "--output-dir", "-o", type=click.Path(), help="Output directory for MOC files"
)
@pass_context
def regenerate_moc(ctx: CLIContext, output_dir: str | None):
    """Regenerate MOC (Maps of Content) files from all processed videos."""
    try:
        click.echo("🗺️  Regenerating MOC files from database...")

        # Initialize services
        db = DatabaseService()
        file_service = FileGenerationService(
            database_service=db, output_dir=Path(output_dir) if output_dir else None
        )

        # Generate MOC files
        moc_files = file_service.generate_moc_files()

        if moc_files:
            click.echo(f"✅ Generated {len(moc_files)} MOC files:")
            for moc_type, path in moc_files.items():
                click.echo(f"   • {moc_type.title()}: {path}")
        else:
            click.echo("⚠️  No MOC data found or failed to generate files")

    except Exception as e:
        click.echo(f"❌ Failed to regenerate MOC files: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option(
    "--days", "-d", default=30, help="Number of days to include in statistics"
)
@pass_context
def stats(ctx: CLIContext, days: int):
    """Show database statistics and usage analytics."""
    try:
        click.echo(f"📊 Database Statistics (Last {days} days)")
        click.echo("=" * 50)

        # Initialize services
        db = DatabaseService()
        cost_tracker = CostTracker(db)

        # Get basic statistics
        stats = db.get_processing_stats()
        usage_summary = cost_tracker.get_usage_summary(days)

        # Display video statistics
        click.echo(f"📹 Videos:")
        click.echo(f"   • Total Processed: {stats.get('total_videos', 0):,}")
        click.echo(f"   • Completed: {stats.get('completed_videos', 0):,}")
        click.echo(f"   • Completion Rate: {stats.get('completion_rate', 0):.1%}")

        # Display cost statistics
        click.echo(f"\n💰 Costs:")
        click.echo(
            f"   • Total Bright Data Cost: ${stats.get('total_bright_data_cost', 0):.4f}"
        )
        click.echo(
            f"   • Average per Video: ${stats.get('average_cost_per_video', 0):.4f}"
        )
        click.echo(
            f"   • Daily Average: ${usage_summary['summary']['daily_average_cost']:.4f}"
        )
        click.echo(
            f"   • Monthly Estimate: ${usage_summary['summary']['monthly_estimated_cost']:.2f}"
        )

        # Display processing statistics
        click.echo(f"\n⚡ Processing:")
        click.echo(f"   • Total Tokens: {stats.get('total_tokens_consumed', 0):,}")
        click.echo(
            f"   • Processing Time: {stats.get('total_processing_time_hours', 0):.1f} hours"
        )

        # Display optimization suggestions
        suggestions = usage_summary.get("optimization_suggestions", [])
        if suggestions:
            click.echo(f"\n💡 Optimization Suggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                click.echo(f"   {i}. {suggestion}")

    except Exception as e:
        click.echo(f"❌ Failed to get statistics: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option("--budget", "-b", type=float, help="Monthly budget in USD")
@pass_context
def budget(ctx: CLIContext, budget: float | None):
    """Check budget status and cost alerts."""
    try:
        if not budget:
            click.echo("❌ Please specify a monthly budget with --budget", err=True)
            ctx.exit(1)

        click.echo(f"💰 Budget Status (${budget:.2f}/month)")
        click.echo("=" * 40)

        # Initialize cost tracker
        cost_tracker = CostTracker()

        # Check budget alerts
        budget_status = cost_tracker.check_budget_alerts(budget)

        # Display alert level with colors
        alert_level = budget_status["alert_level"]
        alert_message = budget_status["alert_message"]

        if alert_level == "red":
            click.echo(click.style(f"🚨 {alert_message}", fg="red", bold=True))
        elif alert_level == "yellow":
            click.echo(click.style(f"⚠️  {alert_message}", fg="yellow", bold=True))
        else:
            click.echo(click.style(f"✅ {alert_message}", fg="green"))

        # Display budget breakdown
        click.echo(f"\n📊 Budget Breakdown:")
        click.echo(f"   • Current Spend: ${budget_status['current_spend']:.4f}")
        click.echo(f"   • Budget Used: {budget_status['budget_percentage_used']:.1f}%")
        click.echo(
            f"   • Projected Monthly: ${budget_status['projected_monthly_cost']:.2f}"
        )
        click.echo(
            f"   • Projected Usage: {budget_status['projected_percentage']:.1f}%"
        )

        # Display recommendations
        recommendations = budget_status.get("recommendations", [])
        if recommendations:
            click.echo(f"\n💡 Recommendations:")
            for i, recommendation in enumerate(recommendations, 1):
                click.echo(f"   {i}. {recommendation}")

    except Exception as e:
        click.echo(f"❌ Failed to check budget: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option("--limit", "-l", default=10, help="Number of jobs to show")
@pass_context
def jobs(ctx: CLIContext, limit: int):
    """Show recent processing jobs and their status."""
    try:
        click.echo(f"📋 Recent Processing Jobs (Last {limit})")
        click.echo("=" * 60)

        # Initialize progress tracker
        tracker = ProgressTracker()

        # Get recent jobs
        recent_jobs = tracker.get_recent_jobs(limit)

        if not recent_jobs:
            click.echo("No jobs found in database")
            return

        for job in recent_jobs:
            # Format status with colors
            status = job["status"]
            if status == "completed":
                status_display = click.style(status, fg="green")
            elif status == "failed":
                status_display = click.style(status, fg="red")
            elif status == "running":
                status_display = click.style(status, fg="yellow")
            else:
                status_display = status

            click.echo(f"🆔 {job['job_id'][:8]}... ({job['job_type']})")
            click.echo(f"   Status: {status_display}")
            progress_text = (
                f"   Progress: {job['completed_items']}/{job['total_items']} "
                f"({job['progress_percentage']:.1f}%)"
            )
            click.echo(progress_text)
            click.echo(
                f"   Created: {job['created_at'][:19] if job['created_at'] else 'Unknown'}"
            )
            if job["total_cost"] > 0:
                click.echo(f"   Cost: ${job['total_cost']:.4f}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Failed to get jobs: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option("--days", "-d", default=30, help="Remove jobs older than this many days")
@click.confirmation_option(prompt="Are you sure you want to clean up old jobs?")
@pass_context
def cleanup(ctx: CLIContext, days: int):
    """Clean up old completed jobs from database."""
    try:
        click.echo(f"🧹 Cleaning up jobs older than {days} days...")

        # Initialize progress tracker
        tracker = ProgressTracker()

        # Cleanup old jobs
        cleaned_count = tracker.cleanup_old_jobs(days)

        if cleaned_count > 0:
            click.echo(f"✅ Cleaned up {cleaned_count} old jobs")
        else:
            click.echo("No old jobs found to clean up")

        # Also vacuum database to reclaim space
        click.echo("💾 Vacuuming database...")
        db = DatabaseService()
        if db.vacuum_database():
            click.echo("✅ Database vacuumed successfully")
        else:
            click.echo("⚠️  Database vacuum failed")

    except Exception as e:
        click.echo(f"❌ Failed to cleanup database: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.argument("video_id")
@pass_context
def info(ctx: CLIContext, video_id: str):
    """Show detailed information about a specific video in the database."""
    try:
        click.echo(f"📹 Video Information: {video_id}")
        click.echo("=" * 50)

        # Initialize database service
        db = DatabaseService()

        # Get video information
        video = db.get_video(video_id)
        if not video:
            click.echo(f"❌ Video {video_id} not found in database", err=True)
            ctx.exit(1)

        # Display video details
        click.echo(f"Title: {video.title}")
        click.echo(f"URL: {video.url}")
        click.echo(f"Uploader: {video.uploader or 'Unknown'}")
        click.echo(
            f"Duration: {video.duration_seconds}s"
            if video.duration_seconds
            else "Duration: Unknown"
        )
        click.echo(f"Upload Date: {video.upload_date or 'Unknown'}")
        click.echo(f"Status: {video.status}")
        click.echo(f"Processed: {video.processed_at}")
        click.echo(f"Extraction Method: {video.extraction_method or 'Unknown'}")

        # Get transcripts
        transcripts = db.get_transcripts_for_video(video_id)
        click.echo(f"\n📝 Transcripts: {len(transcripts)}")
        for transcript in transcripts:
            click.echo(
                f"   • {transcript.transcript_id} ({transcript.language}, {transcript.transcript_type})"
            )

        # Get summaries
        summaries = db.get_summaries_for_video(video_id)
        click.echo(f"\n📊 Summaries: {len(summaries)}")
        for summary in summaries:
            click.echo(
                f"   • {summary.summary_id} ({summary.llm_model}, ${summary.processing_cost:.4f})"
            )

    except Exception as e:
        click.echo(f"❌ Failed to get video info: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option(
    "--state-dir",
    "-d",
    type=click.Path(exists=True),
    help="Directory containing legacy state files",
)
@click.option(
    "--backup/--no-backup",
    default=True,
    help="Create backup of legacy files before migration",
)
@click.option(
    "--cleanup", is_flag=True, help="Remove legacy files after successful migration"
)
@click.confirmation_option(
    prompt="Are you sure you want to migrate legacy state files to SQLite?"
)
@pass_context
def migrate_state(ctx: CLIContext, state_dir: str | None, backup: bool, cleanup: bool):
    """Migrate legacy JSON state files to SQLite database."""
    try:
        click.echo("🔄 Starting legacy state migration to SQLite...")
        click.echo("=" * 50)

        from pathlib import Path

        from ..utils.state_migration import StateMigrator

        # Initialize migrator
        legacy_dir = Path(state_dir) if state_dir else None
        migrator = StateMigrator(legacy_state_dir=legacy_dir)

        # Show files that will be migrated
        found_files = []
        for file_type, file_path in migrator.legacy_files.items():
            if file_path.exists():
                found_files.append(f"   • {file_type}: {file_path}")

        if found_files:
            click.echo("📂 Found legacy state files:")
            for file_info in found_files:
                click.echo(file_info)
        else:
            click.echo("ℹ️  No legacy state files found - nothing to migrate")
            return

        click.echo(f"\n🔧 Migration options:")
        click.echo(f"   • Backup files: {'Yes' if backup else 'No'}")
        click.echo(f"   • Cleanup after: {'Yes' if cleanup else 'No'}")
        click.echo()

        # Perform migration
        results = migrator.migrate_all_state(backup_legacy=backup)

        # Display results
        if results["success"]:
            click.echo(f"✅ Migration completed successfully!")
            click.echo(f"   Records migrated: {results['total_records_migrated']}")
            click.echo(f"   Files processed: {len(results['files_processed'])}")

            # Show details for each file type
            for file_type, file_result in results["files_processed"].items():
                if file_result.get("success"):
                    migrated = file_result.get("records_migrated", 0)
                    if migrated > 0:
                        click.echo(f"   • {file_type}: {migrated} records")
                    else:
                        click.echo(f"   • {file_type}: no data found")
                else:
                    click.echo(
                        f"   • {file_type}: ❌ {file_result.get('error', 'unknown error')}"
                    )

            # Handle warnings
            if results.get("warnings"):
                click.echo(f"\n⚠️  Warnings ({len(results['warnings'])}):")
                for warning in results["warnings"][:5]:  # Show first 5 warnings
                    click.echo(f"   • {warning}")
                if len(results["warnings"]) > 5:
                    click.echo(
                        f"   ... and {len(results['warnings']) - 5} more warnings"
                    )

            # Cleanup if requested
            if cleanup:
                click.echo(f"\n🧹 Cleaning up legacy files...")
                cleanup_results = migrator.cleanup_legacy_files(confirm=True)

                if cleanup_results["success"]:
                    removed_count = len(cleanup_results["files_removed"])
                    click.echo(f"✅ Removed {removed_count} legacy files")
                else:
                    click.echo(f"⚠️  Cleanup completed with errors:")
                    for error in cleanup_results["errors"]:
                        click.echo(f"   • {error}")

        else:
            click.echo(f"❌ Migration failed with errors:")
            for error in results["errors"]:
                click.echo(f"   • {error}")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Migration failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@pass_context
def init_migrations(ctx: CLIContext) -> None:
    """Initialize Alembic database migrations."""
    try:
        db_service = DatabaseService()
        migration_manager = DatabaseMigrationManager(db_service)

        if not migration_manager.is_alembic_available():
            click.echo("⚠️ Alembic not available. Install with: pip install alembic")
            click.echo(
                "Database will work without migrations, but schema versioning will be disabled."
            )
            return

        if migration_manager.initialize_migrations():
            click.echo("✅ Successfully initialized Alembic migrations")
            click.echo(f"📁 Migrations directory: {migration_manager.migrations_dir}")
        else:
            click.echo("❌ Failed to initialize migrations")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Migration initialization failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.argument("message")
@pass_context
def create_migration(ctx: CLIContext, message: str) -> None:
    """Create a new database migration."""
    try:
        db_service = DatabaseService()
        migration_manager = DatabaseMigrationManager(db_service)

        if not migration_manager.is_alembic_available():
            click.echo("❌ Alembic not available. Install with: pip install alembic")
            ctx.exit(1)

        revision = migration_manager.create_migration(message)
        if revision:
            click.echo(f"✅ Created migration: {revision}")
            click.echo(f"📝 Message: {message}")
        else:
            click.echo("❌ Failed to create migration")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Migration creation failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.option(
    "--revision", "-r", default="head", help="Target revision (default: head)"
)
@pass_context
def upgrade(ctx: CLIContext, revision: str) -> None:
    """Upgrade database schema to latest or specified revision."""
    try:
        db_service = DatabaseService()
        migration_manager = DatabaseMigrationManager(db_service)

        if not migration_manager.is_alembic_available():
            click.echo("⚠️ Alembic not available. Using basic database initialization.")
            # Fallback to basic table creation
            db_service.create_tables()
            click.echo("✅ Database tables created/updated")
            return

        if migration_manager.upgrade_database(revision):
            click.echo(f"✅ Successfully upgraded database to revision: {revision}")
        else:
            click.echo("❌ Failed to upgrade database")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Database upgrade failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@click.argument("revision")
@pass_context
def downgrade(ctx: CLIContext, revision: str) -> None:
    """Downgrade database schema to specified revision."""
    try:
        db_service = DatabaseService()
        migration_manager = DatabaseMigrationManager(db_service)

        if not migration_manager.is_alembic_available():
            click.echo(
                "❌ Alembic not available. Cannot downgrade without migration system."
            )
            ctx.exit(1)

        click.echo(
            f"⚠️ Warning: This will downgrade your database to revision {revision}"
        )
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Cancelled.")
            return

        if migration_manager.downgrade_database(revision):
            click.echo(f"✅ Successfully downgraded database to revision: {revision}")
        else:
            click.echo("❌ Failed to downgrade database")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Database downgrade failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@pass_context
def schema_check(ctx: CLIContext) -> None:
    """Check database schema compatibility."""
    try:
        compatibility = check_schema_compatibility()

        click.echo("🔍 Database Schema Compatibility Check")
        click.echo("=" * 50)

        if compatibility["compatible"]:
            click.echo("✅ Database schema is compatible")
        else:
            click.echo("⚠️ Database schema compatibility issues found")

        click.echo(
            f"📊 Current revision: {compatibility['current_revision'] or 'Unknown'}"
        )
        click.echo(f"🎯 Expected revision: {compatibility['expected_revision']}")
        click.echo(
            f"🔧 Alembic available: {'Yes' if compatibility['alembic_available'] else 'No'}"
        )

        if compatibility["issues"]:
            click.echo("\n❌ Issues:")
            for issue in compatibility["issues"]:
                click.echo(f"   • {issue}")

        if compatibility["recommendations"]:
            click.echo("\n💡 Recommendations:")
            for rec in compatibility["recommendations"]:
                click.echo(f"   • {rec}")

        if not compatibility["compatible"]:
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ Schema check failed: {e}", err=True)
        ctx.exit(1)


@database.command()
@pass_context
def migration_history(ctx: CLIContext) -> None:
    """Show database migration history."""
    try:
        db_service = DatabaseService()
        migration_manager = DatabaseMigrationManager(db_service)

        if not migration_manager.is_alembic_available():
            click.echo("⚠️ Alembic not available. No migration history available.")
            return

        current_revision = migration_manager.get_current_revision()
        history = migration_manager.get_migration_history()

        click.echo("📜 Database Migration History")
        click.echo("=" * 50)
        click.echo(f"Current revision: {current_revision or 'None'}")
        click.echo()

        if not history:
            click.echo("No migrations found.")
            return

        for revision in history:
            status = "🔸" if revision["revision"] == current_revision else "  "
            click.echo(
                f"{status} {revision['revision'][:8]} - {revision['doc'] or 'No description'}"
            )
            if revision["down_revision"]:
                click.echo(f"   ↳ From: {revision['down_revision'][:8]}")
            if revision["is_head"]:
                click.echo("   👆 HEAD")

    except Exception as e:
        click.echo(f"❌ Failed to get migration history: {e}", err=True)
        ctx.exit(1)
