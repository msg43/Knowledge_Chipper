"""
Summarize command for the Knowledge System CLI
Summarize command for the Knowledge System CLI.

Handles summarization of transcripts and documents using LLM services.
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..logger import log_system_event
from ..utils.file_io import overwrite_or_insert_summary_section
from .common import CLIContext, console, logger, pass_context
from .transcribe import _generate_obsidian_link


def _extract_youtube_url_from_file(file_path: Path) -> str | None:
    """
    Extract YouTube URL from a processed file's YAML frontmatter
    Extract YouTube URL from a processed file's YAML frontmatter.

    Looks for the 'source' field in the YAML frontmatter which typically
    contains the original YouTube URL for transcript and summary files.

    Args:
        file_path: Path to the markdown file to check

    Returns:
        YouTube URL if found, None otherwise
    """
    import re

    import yaml

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Look for YAML frontmatter first
        if content.startswith("---"):
            # Find the end of YAML frontmatter
            lines = content.split("\n")
            yaml_end_idx = -1
            for i, line in enumerate(lines[1:], 1):  # Skip first "---"
                if line.strip() == "---":
                    yaml_end_idx = i
                    break

            if yaml_end_idx != -1:
                # Extract YAML content
                yaml_content = "\n".join(lines[1:yaml_end_idx])

                try:
                    metadata = yaml.safe_load(yaml_content)
                    if isinstance(metadata, dict):
                        # Check for 'source' field which contains YouTube URL
                        source = metadata.get("source", "")
                        if source and ("youtube.com" in source or "youtu.be" in source):
                            return source
                except yaml.YAMLError:
                    # If YAML parsing fails, fall back to regex search
                    pass

        # Fallback: search for YouTube URLs in the content
        youtube_patterns = [
            r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
            r"https?://(?:www\.)?youtu\.be/[\w-]+",
            r"https?://youtube\.com/watch\?v=[\w-]+",
            r"https?://youtu\.be/[\w-]+",
        ]

        for pattern in youtube_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(0)

    except Exception as e:
        logger.debug(f"Could not extract YouTube URL from {file_path}: {e}")

    return None


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: configured output path)",
)
@click.option(
    "--model",
    "-m",
    default="gpt-4o-mini-2024-07-18",
    help="LLM model to use for summarization",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local"]),
    help="LLM provider to use for summarization (overrides config setting)",
)
@click.option(
    "--max-tokens", "-t", type=int, default=1000, help="Maximum tokens in summary"
)
@click.option(
    "--template",
    type=click.Path(exists=True, path_type=Path),
    help="Custom summary template file",
)
@click.option(
    "--update-md",
    is_flag=True,
    help="Update the ## Summary section of the input .md file in-place",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.option("--progress", is_flag=True, help="Show detailed progress tracking")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Process subdirectories recursively (when input is a folder)",
)
@click.option(
    "--patterns",
    "-p",
    multiple=True,
    default=["*.pdf", "*.txt", "*.md"],
    help="File patterns to process (when input is a folder)",
)
@click.option(
    "--checkpoint",
    type=click.Path(path_type=Path),
    help="Checkpoint file for resuming operations",
)
@click.option("--resume", is_flag=True, help="Resume from checkpoint if available")
@click.option(
    "--force",
    is_flag=True,
    help="Force re-summarization of all files (ignore modification times)",
)
@click.option(
    "--min-claim-tier",
    type=click.Choice(["A", "B", "C", "all"]),
    default="all",
    help="Minimum claim tier to include in output (A=highest quality)",
)
@click.option(
    "--include-contradictions/--no-contradictions",
    default=True,
    help="Include contradiction analysis in output",
)
@click.option(
    "--include-relations/--no-relations",
    default=True,
    help="Include relationship mapping in output",
)
@click.option(
    "--max-claims",
    type=int,
    help="Maximum number of claims to extract per document",
)
@pass_context
def summarize(
    ctx: CLIContext,
    input_path: Path,
    output: Path | None,
    model: str,
    provider: str,
    max_tokens: int,
    template: Path | None,
    dry_run: bool,
    update_md: bool,
    progress: bool,
    recursive: bool,
    patterns: list[str],
    checkpoint: Path | None,
    resume: bool,
    force: bool,
    min_claim_tier: str,
    include_contradictions: bool,
    include_relations: bool,
    max_claims: int | None,
) -> None:
    """
    Summarize transcripts or documents using LLM
    Summarize transcripts or documents using LLM.

    Takes transcripts, PDFs, or markdown files and generates structured summaries
    with key points, insights, and actionable items. Supports both single files
    and batch processing of directories.

    Examples:
         knowledge-system summarize transcript.md
         knowledge-system summarize document.pdf --template custom_prompt.txt
         knowledge-system summarize ./transcripts/ --recursive --progress
         knowledge-system summarize text.txt --template custom_prompt.txt
         knowledge-system summarize file.md --update-md
         knowledge-system summarize ./docs/ --patterns "*.pdf" "*.md"
    """
    settings = ctx.get_settings()

    # Get list of files to process
    files_to_process = []

    if input_path.is_file():
        # Single file processing
        files_to_process = [input_path]
    elif input_path.is_dir():
        # Directory processing
        if recursive:
            # Recursive search
            for pattern in patterns:
                files_to_process.extend(input_path.rglob(pattern))
        else:
            # Non-recursive search
            for pattern in patterns:
                files_to_process.extend(input_path.glob(pattern))

        # Remove duplicates and sort
        files_to_process = sorted(list(set(files_to_process)))
    else:
        console.print(f"[red]✗ Path not found: {input_path}[/red]")
        sys.exit(1)

    if not files_to_process:
        if input_path.is_dir():
            console.print(
                f"[yellow]No files found matching patterns {patterns} in {input_path}[/yellow]"
            )
        else:
            console.print(f"[red]✗ File not found: {input_path}[/red]")
        return

    # Display initial information
    if not ctx.quiet:
        console.print(
            f"[bold green]{'[DRY RUN] ' if dry_run else ''}Summarizing:[/bold green] {input_path}"
        )
        if len(files_to_process) > 1:
            console.print(f"[dim]Found {len(files_to_process)} files to process[/dim]")
            if input_path.is_dir():
                console.print(
                    f"[dim]Directory processing: {'recursive' if recursive else 'non-recursive'}[/dim]"
                )
                console.print(f"[dim]Patterns: {', '.join(patterns)}[/dim]")

        console.print(f"[dim]Model: {model}, Max tokens: {max_tokens}[/dim]")
        if template:
            console.print(f"[dim]Using custom template: {template}[/dim]")
        if update_md:
            console.print(
                "[dim]Will update ## Summary section in-place for .md files[/dim]"
            )

    if dry_run:
        console.print(
            f"[yellow][DRY RUN] Would summarize {len(files_to_process)} file(s) with above options.[/yellow]"
        )
        for file_path in files_to_process[:10]:  # Show first 10 files
            console.print(f"[dim]  - {file_path.name}[/dim]")
        if len(files_to_process) > 10:
            console.print(
                f"[dim]  ... and {len(files_to_process) - 10} more files[/dim]"
            )
        return

    # Determine output path
    if output is None:
        console.print(
            "[red]✗ Error: Output directory is required. Use --output to specify where summaries should be saved.[/red]"
        )
        sys.exit(1)

    # Initialize statistics tracking
    start_time = time.time()
    session_stats = {
        "total_files": len(files_to_process),
        "processed_files": 0,
        "successful_files": 0,
        "failed_files": 0,
        "skipped_files": 0,
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_processing_time": 0.0,
        "total_input_length": 0,
        "total_summary_length": 0,
        "total_cost": 0.0,
        "successful_files_list": [],
        "failed_files_list": [],
        "skipped_files_list": [],
        "models_used": set(),
        "providers_used": set(),
        "file_details": [],
    }

    # Log summarization start
    log_system_event(
        event="batch_summarization_started",
        component="cli.summarize",
        status="info",
        input_path=str(input_path),
        output_path=str(output),
        file_count=len(files_to_process),
        model=model,
        template=str(template) if template else None,
        update_md=update_md,
    )

    # Create summarizer processor
    from ..processors.summarizer import SummarizerProcessor

    # Use provider from CLI option if provided, otherwise from settings
    effective_provider = provider if provider else settings.summarization.provider
    processor = SummarizerProcessor(
        provider=effective_provider,
        model=model,
        max_tokens=max_tokens,
        hce_options={
            "min_claim_tier": min_claim_tier,
            "include_contradictions": include_contradictions,
            "include_relations": include_relations,
            "max_claims": max_claims,
        },
    )

    # If no template provided, default to document summary template
    if not template:
        default_template_path = Path("config/prompts/document summary.txt")
        if default_template_path.exists():
            template = default_template_path
            if not ctx.quiet:
                console.print(f"[dim]Using default template: {template}[/dim]")
        else:
            if not ctx.quiet:
                console.print(
                    "[yellow]⚠️  Default template 'config/prompts/document summary.txt' not found, using generic prompt[/yellow]"
                )

    # Build summary index if not forcing re-summarization
    summary_index: dict[str, Any] = {}
    index_file: Path | None = None
    skipped_via_index: int = 0

    if not force and output is not None:
        # Create session-specific index file
        index_filename = (
            f".summary_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        index_file = output / index_filename

        # Build index from existing summaries
        if not ctx.quiet:
            console.print("[yellow]🔎 Checking for existing summaries...[/yellow]")
        summary_index = processor._build_summary_index(output)

        if summary_index:
            processor._save_index_to_file(index_file, summary_index)
            if not ctx.quiet:
                console.print(
                    f"[green]📊 Found {len(summary_index)} existing summaries[/green]"
                )

    # Track files that can be skipped
    files_to_skip: list[tuple[Path, str]] = []
    if not force:
        for file_path in files_to_process:
            needs_summary, reason = processor._check_needs_summarization(
                file_path, summary_index
            )
            if not needs_summary:
                files_to_skip.append((file_path, reason))
                skipped_via_index += 1
                session_stats["skipped_files"] += 1

    if files_to_skip and not ctx.quiet:
        console.print(
            f"\n[yellow]⏭️  Skipping {len(files_to_skip)} unchanged files:[/yellow]"
        )
        for skip_file, skip_reason in files_to_skip[:5]:  # Show first 5
            console.print(f"[dim]  - {skip_file.name}: {skip_reason}[/dim]")
        if len(files_to_skip) > 5:
            console.print(f"[dim]  ... and {len(files_to_skip) - 5} more[/dim]")

        # Update file list
        files_to_process = [
            f for f in files_to_process if f not in [skip[0] for skip in files_to_skip]
        ]

    try:
        # Process each file
        for i, file_path in enumerate(files_to_process, 1):
            file_start_time = time.time()

            # Show progress
            if progress or len(files_to_process) > 1:
                percent = (i - 1) / len(files_to_process) * 100
                if not ctx.quiet:
                    console.print(
                        f"\n[bold blue]Processing {i}/{len(files_to_process)} ({percent:.1f}%):[/bold blue] {file_path.name}"
                    )
                    if session_stats["processed_files"] > 0:
                        avg_time = (
                            session_stats["total_processing_time"]
                            / session_stats["processed_files"]
                        )
                        remaining_files = len(files_to_process) - i + 1
                        eta_seconds = avg_time * remaining_files
                        eta_min = int(eta_seconds // 60)
                        eta_sec = int(eta_seconds % 60)
                        console.print(
                            f"[dim]ETA: ~{eta_min}m {eta_sec}s | Running totals: {session_stats['total_tokens']:,} tokens, ${session_stats['total_cost']:.3f}[/dim]"
                        )

            try:
                # Handle different file types
                if file_path.suffix.lower() == ".pdf":
                    if not ctx.quiet:
                        console.print("[blue]📄 Extracting text from PDF...[/blue]")

                    from ..processors.pdf import PDFProcessor

                    pdf_processor = PDFProcessor()
                    pdf_result = pdf_processor.process(file_path)

                    if not pdf_result.success:
                        raise Exception(
                            f"PDF extraction failed: {'; '.join(pdf_result.errors)}"
                        )

                    pdf_results = pdf_result.data.get("results", [])
                    if not pdf_results:
                        raise Exception("No text extracted from PDF")

                    text_to_summarize = pdf_results[0]["text"]
                    if not text_to_summarize.strip():
                        raise Exception(
                            "PDF appears to be empty or contains no readable text"
                        )

                    if not ctx.quiet:
                        console.print(
                            f"[green]✓ Extracted {len(text_to_summarize):,} characters[/green]"
                        )

                    # Process the extracted text
                    result = processor.process(
                        text_to_summarize,
                        dry_run=False,
                        prompt_template=template,
                    )
                else:
                    # Handle text/markdown files
                    result = processor.process(
                        file_path, dry_run=False, prompt_template=template
                    )

                file_processing_time = time.time() - file_start_time

                if result.success:
                    # Update statistics
                    metadata = result.metadata or {}
                    session_stats["successful_files"] += 1
                    session_stats["successful_files_list"].append(str(file_path))
                    session_stats["total_tokens"] += metadata.get("total_tokens", 0)
                    session_stats["total_prompt_tokens"] += metadata.get(
                        "prompt_tokens", 0
                    )
                    session_stats["total_completion_tokens"] += metadata.get(
                        "completion_tokens", 0
                    )
                    session_stats["total_processing_time"] += metadata.get(
                        "processing_time", file_processing_time
                    )
                    session_stats["total_input_length"] += metadata.get(
                        "input_length", 0
                    )
                    session_stats["total_summary_length"] += metadata.get(
                        "summary_length", 0
                    )

                    # Calculate cost
                    prompt_tokens = metadata.get("prompt_tokens", 0)
                    completion_tokens = metadata.get("completion_tokens", 0)
                    if "gpt-4" in model.lower():
                        file_cost = (
                            prompt_tokens * 0.03 + completion_tokens * 0.06
                        ) / 1000
                    elif "gpt-3.5" in model.lower():
                        file_cost = (
                            prompt_tokens * 0.001 + completion_tokens * 0.002
                        ) / 1000
                    else:
                        file_cost = 0.0
                    session_stats["total_cost"] += file_cost

                    session_stats["models_used"].add(metadata.get("model", model))
                    session_stats["providers_used"].add(
                        metadata.get("provider", "unknown")
                    )

                    # Store detailed file info
                    session_stats["file_details"].append(
                        {
                            "file": str(file_path),
                            "tokens": metadata.get("total_tokens", 0),
                            "cost": file_cost,
                            "time": file_processing_time,
                            "input_length": metadata.get("input_length", 0),
                            "summary_length": metadata.get("summary_length", 0),
                            "compression": metadata.get("compression_ratio", 0),
                            "status": "success",
                        }
                    )

                    # Save summary file
                    if update_md and file_path.suffix.lower() == ".md":
                        # Generate unified YAML metadata
                        from ..utils.file_io import generate_unified_yaml_metadata

                        additional_yaml_fields = generate_unified_yaml_metadata(
                            file_path,
                            result.data,
                            model,
                            metadata.get("provider", "unknown"),
                            metadata,
                            template,
                            "document summary",
                        )

                        # Update existing .md file in-place with YAML fields
                        overwrite_or_insert_summary_section(
                            file_path, result.data, additional_yaml_fields
                        )
                        output_path = file_path
                        if not ctx.quiet:
                            console.print("[green]✓ Updated summary in-place[/green]")
                    else:
                        # Create new summary file
                        # Clean filename by removing hyphens for better readability
                        clean_filename = file_path.stem.replace("-", "_")

                        # If input file is a transcript, remove _transcript suffix for proper naming
                        if clean_filename.endswith("_transcript"):
                            clean_filename = clean_filename[
                                :-11
                            ]  # Remove "_transcript"

                        if update_md and file_path.suffix.lower() != ".md":
                            output_file = file_path.parent / f"{clean_filename}.md"
                        else:
                            output_file = output / f"{clean_filename}_summary.md"

                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_path = output_file

                        # Write summary with enhanced metadata
                        with open(output_file, "w", encoding="utf-8") as f:
                            # Basic metadata
                            f.write(f"**Source File:** {file_path.name}\n")
                            f.write(f"**Source Path:** {file_path.absolute()}\n")

                            f.write(f"**Model:** {model}\n")
                            f.write(
                                f"**Provider:** {metadata.get('provider', 'unknown')}\n"
                            )
                            if template:
                                f.write(f"**Template:** {template}\n")
                            f.write("\n")

                            # Performance stats
                            f.write("**Performance:**\n")
                            processing_time = metadata.get("processing_time", 0)
                            f.write(f"- **Processing Time:** {processing_time:.1f}s\n")

                            prompt_tokens = metadata.get("prompt_tokens", 0)
                            completion_tokens = metadata.get("completion_tokens", 0)
                            total_tokens = metadata.get("total_tokens", 0)
                            f.write(
                                f"- **Tokens Used:** {total_tokens:,} total ({prompt_tokens:,} prompt + {completion_tokens:,} completion)\n"
                            )

                            tokens_per_second = metadata.get("tokens_per_second", 0)
                            f.write(
                                f"- **Speed:** {tokens_per_second:.1f} tokens/second\n"
                            )

                            if file_cost > 0:
                                f.write(
                                    f"- **Estimated Cost:** ~${file_cost:.4f} USD\n"
                                )
                            f.write("\n")

                            # Content analysis
                            f.write("**Content Analysis:**\n")
                            input_length = metadata.get("input_length", 0)
                            summary_length = metadata.get("summary_length", 0)
                            f.write(
                                f"- **Input Length:** {input_length:,} characters\n"
                            )
                            f.write(
                                f"- **Summary Length:** {summary_length:,} characters\n"
                            )

                            compression_ratio = metadata.get("compression_ratio", 0)
                            reduction_percent = (
                                (1 - compression_ratio) * 100
                                if compression_ratio > 0
                                else 0
                            )
                            f.write(
                                f"- **Compression:** {reduction_percent:.1f}% reduction\n"
                            )
                            f.write("\n")

                            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
                            f.write("---\n\n")

                            # Add YouTube watch link if this is YouTube content
                            youtube_url = _extract_youtube_url_from_file(file_path)
                            if youtube_url:
                                f.write(f"**🎥 [Watch on YouTube]({youtube_url})**\n\n")

                            # Add link to corresponding transcript if it exists
                            base_filename = file_path.stem
                            # If filename ends with _transcript, remove it to get base name
                            if base_filename.endswith("_transcript"):
                                base_filename = base_filename[
                                    :-11
                                ]  # Remove "_transcript"
                            transcript_link = _generate_obsidian_link(
                                base_filename, "transcript", output
                            )
                            if transcript_link:
                                f.write(
                                    f"## Related Documents\n\n{transcript_link}\n\n"
                                )

                            f.write(result.data)

                        if not ctx.quiet:
                            console.print(
                                f"[green]✓ Summary saved to: {output_file.name}[/green]"
                            )

                        # Update index with new summary info
                        if not force and index_file:
                            summary_info = {
                                "summary_file": str(output_path),
                                "summary_generated": datetime.now().isoformat(),
                                "summary_size": output_path.stat().st_size,
                                "source_hash": processor._calculate_file_hash(
                                    file_path
                                ),  # Optional
                                "model": model,
                                "tokens_used": metadata.get("total_tokens", 0),
                            }
                            summary_index[str(file_path.absolute())] = summary_info
                            processor._update_index_file(
                                index_file, str(file_path.absolute()), summary_info
                            )

                    # Show file statistics
                    if progress:
                        console.print(
                            f"[dim]File stats: {metadata.get('total_tokens', 0):,} tokens, {file_processing_time:.1f}s, ${file_cost:.4f}[/dim]"
                        )

                else:
                    # Handle failure
                    session_stats["failed_files"] += 1
                    session_stats["failed_files_list"].append(
                        (str(file_path), "; ".join(result.errors))
                    )
                    session_stats["file_details"].append(
                        {
                            "file": str(file_path),
                            "status": "failed",
                            "error": "; ".join(result.errors),
                            "time": file_processing_time,
                        }
                    )
                    if not ctx.quiet:
                        console.print(
                            f"[red]✗ Failed: {'; '.join(result.errors)}[/red]"
                        )

            except Exception as e:
                # Handle exception
                file_processing_time = time.time() - file_start_time
                session_stats["failed_files"] += 1
                session_stats["failed_files_list"].append((str(file_path), str(e)))
                session_stats["file_details"].append(
                    {
                        "file": str(file_path),
                        "status": "failed",
                        "error": str(e),
                        "time": file_processing_time,
                    }
                )
                if not ctx.quiet:
                    console.print(f"[red]✗ Error: {str(e)}[/red]")

            session_stats["processed_files"] += 1

        # Calculate final statistics
        total_session_time = time.time() - start_time

        # Calculate averages
        avg_compression = 0
        if session_stats["total_input_length"] > 0:
            avg_compression = (
                session_stats["total_summary_length"]
                / session_stats["total_input_length"]
            )

        avg_tokens_per_second = 0
        if session_stats["total_processing_time"] > 0:
            avg_tokens_per_second = (
                session_stats["total_tokens"] / session_stats["total_processing_time"]
            )

        # Display comprehensive session statistics
        if not ctx.quiet:
            console.print("\n" + "=" * 80)
            console.print("[bold green]📊 SUMMARIZATION SESSION COMPLETE[/bold green]")
            console.print("=" * 80)

            # Summary overview
            console.print("[bold]Session Summary:[/bold]")
            console.print(
                f"✅ Successful: [green]{session_stats['successful_files']}[/green]"
            )
            console.print(f"❌ Failed: [red]{session_stats['failed_files']}[/red]")
            console.print(f"📁 Total files: {session_stats['total_files']}")
            console.print(f"⏱️  Total time: {total_session_time:.1f}s")

            # Token and cost statistics
            console.print("\n[bold]Resource Usage:[/bold]")
            console.print(
                f"🎯 Total tokens: [blue]{session_stats['total_tokens']:,}[/blue] ({session_stats['total_prompt_tokens']:,} prompt + {session_stats['total_completion_tokens']:,} completion)"
            )
            console.print(
                f"💰 Total cost: [yellow]${session_stats['total_cost']:.4f} USD[/yellow]"
            )
            console.print(
                f"⚡ Average speed: {avg_tokens_per_second:.1f} tokens/second"
            )

            # Content statistics
            console.print("\n[bold]Content Analysis:[/bold]")
            console.print(
                f"📝 Total input: {session_stats['total_input_length']:,} characters"
            )
            console.print(
                f"📄 Total output: {session_stats['total_summary_length']:,} characters"
            )
            console.print(
                f"🗜️  Average compression: {(1-avg_compression)*100:.1f}% reduction"
            )

            # Models and providers
            if session_stats["models_used"]:
                console.print(
                    f"\n[bold]Models used:[/bold] {', '.join(session_stats['models_used'])}"
                )
            if session_stats["providers_used"]:
                console.print(
                    f"[bold]Providers used:[/bold] {', '.join(session_stats['providers_used'])}"
                )

            # Failed files details
            if session_stats["failed_files_list"]:
                console.print("\n[bold red]Failed Files:[/bold red]")
                for file_path, error in session_stats["failed_files_list"]:
                    console.print(f"❌ {Path(file_path).name}: {error}")

        # Generate detailed processing report
        report_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output / f"summarization_report_{report_timestamp}.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)

        with open(report_file, "w", encoding="utf-8") as f:
            f.write("# Summarization Session Report\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n")
            f.write(f"**Session Duration:** {total_session_time:.1f} seconds\n")
            f.write(f"**Input Path:** {input_path}\n")
            f.write(f"**Output Path:** {output}\n")
            f.write(f"**Model:** {model}\n")

            if template:
                f.write(f"**Template:** {template}\n")
            f.write("\n")

            # Session overview
            f.write("## Session Overview\n\n")
            f.write(f"- **Total Files:** {session_stats['total_files']}\n")
            f.write(f"- **Successful:** {session_stats['successful_files']}\n")
            f.write(f"- **Failed:** {session_stats['failed_files']}\n")
            f.write(
                f"- **Success Rate:** {(session_stats['successful_files']/session_stats['total_files']*100):.1f}%\n\n"
            )

            # Resource usage
            f.write("## Resource Usage\n\n")
            f.write(f"- **Total Tokens:** {session_stats['total_tokens']:,}\n")
            f.write(f"- **Prompt Tokens:** {session_stats['total_prompt_tokens']:,}\n")
            f.write(
                f"- **Completion Tokens:** {session_stats['total_completion_tokens']:,}\n"
            )
            f.write(f"- **Total Cost:** ${session_stats['total_cost']:.4f} USD\n")
            f.write(f"- **Average Speed:** {avg_tokens_per_second:.1f} tokens/second\n")
            f.write(
                f"- **Processing Time:** {session_stats['total_processing_time']:.1f}s\n\n"
            )

            # Content analysis
            f.write("## Content Analysis\n\n")
            f.write(
                f"- **Total Input:** {session_stats['total_input_length']:,} characters\n"
            )
            f.write(
                f"- **Total Output:** {session_stats['total_summary_length']:,} characters\n"
            )
            f.write(
                f"- **Average Compression:** {(1-avg_compression)*100:.1f}% reduction\n\n"
            )

            # Per-file details
            f.write("## Per-File Details\n\n")
            f.write("| File | Status | Tokens | Cost | Time | Compression |\n")
            f.write("|------|--------|--------|------|------|-------------|\n")

            for detail in session_stats["file_details"]:
                file_name = Path(detail["file"]).name
                if detail["status"] == "success":
                    compression_pct = (1 - detail.get("compression", 0)) * 100
                    f.write(
                        f"| {file_name} | ✅ Success | {detail['tokens']:,} | ${detail['cost']:.4f} | {detail['time']:.1f}s | {compression_pct:.1f}% |\n"
                    )
                else:
                    f.write(
                        f"| {file_name} | ❌ Failed | - | - | {detail['time']:.1f}s | {detail.get('error', 'Unknown error')} |\n"
                    )

            f.write("\n")

            # Failed files section
            if session_stats["failed_files_list"]:
                f.write("## Failed Files\n\n")
                for file_path, error in session_stats["failed_files_list"]:
                    f.write(f"- **{Path(file_path).name}:** {error}\n")
                f.write("\n")

            # Models and providers
            f.write("## Configuration\n\n")
            f.write(
                f"- **Models Used:** {', '.join(session_stats['models_used']) if session_stats['models_used'] else 'None'}\n"
            )
            f.write(
                f"- **Providers Used:** {', '.join(session_stats['providers_used']) if session_stats['providers_used'] else 'None'}\n"
            )
            f.write(f"- **Update MD:** {'Yes' if update_md else 'No'}\n")
            f.write(f"- **Progress Tracking:** {'Yes' if progress else 'No'}\n")

        if not ctx.quiet:
            console.print(
                f"\n[green]📋 Detailed report saved to: {report_file.name}[/green]"
            )

            # Report index optimization statistics
            if not force and skipped_via_index > 0:
                console.print("\n[green]🚀 Performance optimization:[/green]")
                console.print(
                    f"  - Skipped {skipped_via_index} unchanged files via index"
                )

                # Estimate savings
                avg_tokens = session_stats["total_tokens"] / max(
                    session_stats["successful_files"], 1
                )
                saved_tokens = skipped_via_index * avg_tokens
                saved_cost = saved_tokens * 0.002 / 1000  # Rough estimate
                saved_time = skipped_via_index * 5  # Estimate 5 seconds per summary

                console.print(f"  - Estimated tokens saved: ~{int(saved_tokens):,}")
                console.print(f"  - Estimated cost saved: ~${saved_cost:.2f}")
                console.print(
                    f"  - Estimated time saved: ~{saved_time}s ({saved_time/60:.1f}m)"
                )

            console.print("=" * 80)

        # Clean up session index file
        if index_file and index_file.exists():
            try:
                index_file.unlink()
                logger.debug(f"Cleaned up session index file: {index_file.name}")
            except (OSError, PermissionError):
                pass  # Ignore cleanup failures

    except Exception as e:
        console.print(f"[red]✗ Unexpected error during summarization:[/red] {e}")
        if ctx.verbose:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
