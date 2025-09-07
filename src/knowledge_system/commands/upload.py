"""
Upload command for Knowledge_Chipper CLI

Provides OAuth-based uploading of claims data to GetReceipts.org
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ..logger import get_logger
from ..services.claims_upload_service import ClaimsUploadService
from .common import CLIContext, pass_context

console = Console()
logger = get_logger(__name__)


@click.command()
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True, path_type=Path),
    help="Path to SQLite database (default: knowledge_system.db in current directory)",
)
@click.option(
    "--production",
    is_flag=True,
    help="Upload to production GetReceipts.org (default: development)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be uploaded without actually uploading",
)
@click.option(
    "--filter-tier",
    type=click.Choice(["A", "B", "C"], case_sensitive=False),
    multiple=True,
    help="Only upload claims of specified tiers (can be used multiple times)",
)
@pass_context
def upload(
    ctx: CLIContext,
    database: Path | None,
    production: bool,
    dry_run: bool,
    filter_tier: tuple[str, ...],
) -> None:
    """
    Upload claims data to GetReceipts.org via OAuth authentication.

    This command reads claims from your local SQLite database and uploads them
    to GetReceipts.org with complete user attribution via OAuth.

    Examples:
        knowledge-system upload
        knowledge-system upload --database /path/to/my.db --production
        knowledge-system upload --filter-tier A B --dry-run
    """
    if not ctx.quiet:
        console.print("[bold blue]📤 GetReceipts.org Upload[/bold blue]\n")

    try:
        # Initialize upload service
        upload_service = ClaimsUploadService(database)

        # Validate database
        is_valid, message = upload_service.is_database_valid()
        if not is_valid:
            console.print(f"[red]❌ Database error: {message}[/red]")
            sys.exit(1)

        # Get upload statistics
        stats = upload_service.get_database_stats()
        if not ctx.quiet:
            console.print(f"📊 Database Statistics:")
            console.print(f"   Total claims: {stats.get('total_claims', 0)}")
            console.print(f"   Unuploaded: {stats.get('unuploaded_claims', 0)}")
            console.print(f"   Previously uploaded: {stats.get('uploaded_claims', 0)}")
            console.print()

        # Get claims to upload
        claims_to_upload = upload_service.get_unuploaded_claims()

        if not claims_to_upload:
            console.print("[yellow]ℹ️ No unuploaded claims found.[/yellow]")
            return

        # Apply tier filter if specified
        if filter_tier:
            allowed_tiers = [tier.upper() for tier in filter_tier]
            claims_to_upload = [
                claim
                for claim in claims_to_upload
                if claim.tier and claim.tier.upper() in allowed_tiers
            ]

            if not ctx.quiet:
                console.print(
                    f"🔍 Filtered to tiers {', '.join(allowed_tiers)}: {len(claims_to_upload)} claims"
                )

        if not claims_to_upload:
            console.print("[yellow]ℹ️ No claims match the specified filters.[/yellow]")
            return

        if dry_run:
            console.print(
                f"[yellow]🔍 DRY RUN: Would upload {len(claims_to_upload)} claims:[/yellow]"
            )
            for claim in claims_to_upload[:10]:  # Show first 10
                console.print(f"   - [{claim.tier}] {claim.canonical[:60]}...")
            if len(claims_to_upload) > 10:
                console.print(f"   ... and {len(claims_to_upload) - 10} more")
            return

        # Configure for production if requested
        if production:
            from ..cloud.oauth import set_production

            set_production()
            console.print("[blue]🌐 Using production GetReceipts.org[/blue]")

        # Start OAuth authentication and upload
        console.print(f"[blue]🔐 Starting OAuth authentication...[/blue]")

        from ..cloud.oauth import upload_to_getreceipts

        # Convert claims to session data format
        session_data = _convert_claims_to_session_data(claims_to_upload)

        # Upload via OAuth
        console.print(
            f"[blue]📤 Uploading {len(claims_to_upload)} claims to GetReceipts.org...[/blue]"
        )
        upload_results = upload_to_getreceipts(session_data, use_production=production)

        # Report results
        total_uploaded = sum(
            len(data) if data else 0 for data in upload_results.values()
        )
        console.print(
            f"[green]✅ Successfully uploaded {total_uploaded} records![/green]"
        )

        if not ctx.quiet:
            console.print("\n📊 Upload Summary:")
            for table, data in upload_results.items():
                count = len(data) if data else 0
                console.print(f"   {table}: {count} records")

        # Mark claims as uploaded in local database
        claim_ids = [(claim.episode_id, claim.claim_id) for claim in claims_to_upload]
        upload_service.mark_claims_uploaded(claim_ids)

        console.print(f"\n[green]🎉 Upload completed successfully![/green]")

    except KeyboardInterrupt:
        console.print(f"\n[yellow]⚠️ Upload cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        console.print(f"[red]❌ Upload failed: {str(e)}[/red]")
        sys.exit(1)


def _convert_claims_to_session_data(claims_data) -> dict:
    """Convert ClaimUploadData list to session data format."""
    session_data = {
        "episodes": [],
        "claims": [],
        "evidence_spans": [],
        "people": [],
        "jargon": [],
        "concepts": [],
        "relations": [],
    }

    # Track unique episodes
    seen_episodes = set()

    for claim in claims_data:
        # Add episode data (if not already added)
        if claim.episode_data and claim.episode_id not in seen_episodes:
            session_data["episodes"].append(claim.episode_data)
            seen_episodes.add(claim.episode_id)

        # Add claim data
        claim_dict = {
            "claim_id": claim.claim_id,
            "canonical": claim.canonical,
            "episode_id": claim.episode_id,
            "claim_type": claim.claim_type,
            "tier": claim.tier,
            "scores_json": claim.scores_json,
            "first_mention_ts": claim.first_mention_ts,
            "inserted_at": claim.inserted_at,
        }
        session_data["claims"].append(claim_dict)

        # Add associated data
        session_data["evidence_spans"].extend(claim.evidence_spans)
        session_data["people"].extend(claim.people)
        session_data["jargon"].extend(claim.jargon)
        session_data["concepts"].extend(claim.concepts)
        session_data["relations"].extend(claim.relations)

    return session_data
