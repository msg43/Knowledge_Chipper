"""
MOC (Maps of Content) command for the Knowledge System CLI.

Handles generation of Maps of Content from processed documents.
"""

import sys
from pathlib import Path
from typing import List, Optional

import click

from ..logger import log_system_event
from ..processors.moc import MOCProcessor
from .common import CLIContext, pass_context, console, logger


@click.command()
@click.argument("input_paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for MOC (default: configured MOC path)",
)
@click.option("--title", "-t", help="Title for the MOC")
@click.option(
    "--theme",
    type=click.Choice(["chronological", "topical", "hierarchical"]),
    default="topical",
    help="MOC organization theme",
)
@click.option(
    "--depth",
    "-d",
    type=int,
    default=3,
    help="Maximum depth for hierarchical organization",
)
@click.option(
    "--include-beliefs/--no-include-beliefs",
    default=True,
    help="Include belief graph generation",
)
@click.option(
    "--template",
    type=click.Path(exists=True, path_type=Path),
    help="Custom MOC template file",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@pass_context
def moc(
    ctx: CLIContext,
    input_paths: List[Path],
    output: Optional[Path],
    title: Optional[str],
    theme: str,
    depth: int,
    include_beliefs: bool,
    template: Optional[Path],
    dry_run: bool,
) -> None:
    """
    Generate Maps of Content (MOC) from processed documents.

    Creates structured MOCs that organize and link related content,
    with optional belief graph integration for knowledge relationships.

    Examples:
        knowledge-system moc summary1.md summary2.md
        knowledge-system moc ./summaries/ --theme hierarchical
        knowledge-system moc *.md --title "Project Knowledge" --depth 2
    """
    settings = ctx.get_settings()

    if not input_paths:
        console.print("[red]Error:[/red] No input paths provided")
        sys.exit(1)

    if not ctx.quiet:
        console.print(
            f"[bold magenta]{'[DRY RUN] ' if dry_run else ''}Generating MOC:[/bold magenta] {len(input_paths)} sources"
        )
        console.print(
            f"[dim]Theme: {theme}, Depth: {depth}, Include beliefs: {include_beliefs}[/dim]"
        )
        if template:
            console.print(f"[dim]Using custom template: {template}[/dim]")

    if dry_run:
        console.print(
            "[yellow][DRY RUN] Would generate MOC with the above settings.[/yellow]"
        )
        return

    # Determine output path
    if output is None:
        output = Path(settings.paths.mocs) / "generated_moc.md"

    # Log MOC generation start
    log_system_event(
        event="moc_generation_started",
        component="cli.moc",
        status="info",
        input_count=len(input_paths),
        output_path=str(output),
        theme=theme,
        depth=depth,
        template=str(template) if template else None,
    )

    try:
        # Create MOC processor
        processor = MOCProcessor()

        # Process the input files
        result = processor.process(
            [str(path) for path in input_paths],
            theme=theme,
            depth=depth,
            include_beliefs=include_beliefs,
            dry_run=dry_run,
            template=template,
        )

        if result.success:
            if not ctx.quiet:
                console.print("[green]✓ MOC generated successfully[/green]")
                if not dry_run:
                    console.print(
                        f"[dim]People found: {result.metadata.get('people_found', 0)}[/dim]"
                    )
                    console.print(
                        f"[dim]Tags found: {result.metadata.get('tags_found', 0)}[/dim]"
                    )
                    console.print(
                        f"[dim]Mental models found: {result.metadata.get('mental_models_found', 0)}[/dim]"
                    )
                    console.print(
                        f"[dim]Jargon terms found: {result.metadata.get('jargon_found', 0)}[/dim]"
                    )
                    if include_beliefs:
                        console.print(
                            f"[dim]Beliefs found: {result.metadata.get('beliefs_found', 0)}[/dim]"
                        )

            # Save MOC files to output directory
            if not dry_run:
                output.parent.mkdir(parents=True, exist_ok=True)

                # Save each generated file
                for filename, content in result.data.items():
                    file_path = output.parent / filename
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    if not ctx.quiet:
                        console.print(f"[green]✓ Saved {filename} to {file_path}[/green]")
        else:
            console.print(
                f"[red]✗ MOC generation failed:[/red] {'; '.join(result.errors)}"
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Unexpected error during MOC generation:[/red] {e}")
        if ctx.verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1) 