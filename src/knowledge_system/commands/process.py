"""
Process command for the Knowledge System CLI
Process command for the Knowledge System CLI.

Handles comprehensive file processing with transcription, summarization, and MOC generation.
"""

import sys
from pathlib import Path
from typing import Any

import click

from ..logger import log_system_event
from ..superchunk.config import SuperChunkConfig
from ..superchunk.runner import Runner
from .common import CLIContext, console, pass_context
from .transcribe import _generate_obsidian_link, format_transcript_content


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: configured output path)",
)
@click.option(
    "--transcribe/--no-transcribe", default=True, help="Transcribe audio/video files"
)
@click.option(
    "--summarize/--no-summarize",
    default=True,
    help="Summarize transcripts and documents",
)
@click.option("--moc/--no-moc", default=True, help="Generate Maps of Content")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Process subdirectories recursively (when input is a folder)",
)
@click.option(
    "--patterns",
    "-p",
    multiple=True,
    default=[
        "*.mp4",
        "*.mp3",
        "*.wav",
        "*.m4a",
        "*.avi",
        "*.mov",
        "*.mkv",
        "*.pdf",
        "*.txt",
        "*.md",
    ],
    help="File patterns to process (when input is a folder)",
)
@click.option(
    "--transcription-model",
    default="base",
    help="Whisper model to use for transcription",
)
@click.option(
    "--summarization-model",
    default="gpt-4o-mini-2024-07-18",
    help="LLM model to use for summarization",
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "cuda", "mps"]),
    default="auto",
    help="Device to use for processing",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.option("--progress", is_flag=True, help="Show progress tracking")
@click.option(
    "--superchunk-artifacts",
    type=click.Path(path_type=Path),
    required=False,
    help="If set, run SuperChunk summarizer on the input text/markdown and write artifacts here",
)
@click.option(
    "--sc-preset",
    type=click.Choice(["precision", "balanced", "narrative"]),
    required=False,
    help="SuperChunk window preset override",
)
@click.option(
    "--sc-verify-top",
    type=float,
    required=False,
    help="SuperChunk verification top percent (0..1)",
)
@click.option(
    "--sc-quote-cap", type=int, required=False, help="SuperChunk max quote words"
)
@click.option(
    "--sc-max-concurrent",
    type=int,
    required=False,
    help="SuperChunk max concurrent calls",
)
@click.option(
    "--export-getreceipts",
    is_flag=True,
    help="Export extracted claims to GetReceipts platform",
)
@pass_context
def process(
    ctx: CLIContext,
    input_path: Path,
    output: Path | None,
    transcribe: bool,
    summarize: bool,
    moc: bool,
    recursive: bool,
    patterns: list[str],
    transcription_model: str,
    summarization_model: str,
    device: str,
    dry_run: bool,
    progress: bool,
    superchunk_artifacts: Path | None,
    sc_preset: str | None,
    sc_verify_top: float | None,
    sc_quote_cap: int | None,
    sc_max_concurrent: int | None,
    export_getreceipts: bool,
) -> None:
    """
    Process files or folders with transcription, summarization, and MOC generation
    Process files or folders with transcription, summarization, and MOC generation.

    Can process a single file or recursively process all files in a folder
    that match the specified patterns.

     Examples:
         knowledge-system process video.mp4
         knowledge-system process ./videos/ --recursive
         knowledge-system process ./content/ --no-transcribe --patterns "*.pdf" "*.txt"
         knowledge-system process audio.wav --output ./results --dry-run
    """
    settings = ctx.get_settings()

    if not ctx.quiet:
        console.print(
            f"[bold green]{'[DRY RUN] ' if dry_run else ''}Processing:[/bold green] {input_path}"
        )
        if input_path.is_dir():
            console.print(
                f"[dim]Directory processing: {'recursive' if recursive else 'non-recursive'}, Patterns: {', '.join(patterns)}[/dim]"
            )
        console.print(
            f"[dim]Operations: Transcribe={transcribe}, Summarize={summarize}, MOC={moc}, GetReceipts={export_getreceipts}[/dim]"
        )
        console.print(
            f"[dim]Models: Transcription={transcription_model}, Summarization={summarization_model}[/dim]"
        )

    if dry_run:
        console.print(
            "[yellow][DRY RUN] Would process file(s) with the above settings.[/yellow]"
        )
        return

    # Determine output path
    if output is None:
        console.print(
            "[red]✗ Error: Output directory is required. Use --output to specify where processed files should be saved.[/red]"
        )
        sys.exit(1)

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

    if not files_to_process:
        console.print(
            "[yellow]No files found matching the specified patterns.[/yellow]"
        )
        return

    if not ctx.quiet:
        console.print(f"[dim]Found {len(files_to_process)} files to process[/dim]")

    # Log processing start
    log_system_event(
        event="processing_started",
        component="cli.process",
        status="info",
        input_path=str(input_path),
        output_path=str(output),
        file_count=len(files_to_process),
        transcribe=transcribe,
        summarize=summarize,
        moc=moc,
        recursive=recursive,
    )

    # Track processing results
    results: dict[str, list[Any]] = {
        "transcribed": [],
        "summarized": [],
        "moc_generated": [],
        "errors": [],
    }

    # Track files for MOC generation
    moc_input_files: list[Path] = []

    try:
        # Import processors
        from ..processors.audio_processor import AudioProcessor
        from ..processors.moc import MOCProcessor
        from ..processors.summarizer import SummarizerProcessor

        # Create processors
        audio_processor = AudioProcessor(device=device)
        summarizer_processor = SummarizerProcessor(
            provider=settings.summarization.provider,
            model=summarization_model,
            max_tokens=settings.summarization.max_tokens,
        )
        moc_processor = MOCProcessor()

        # Process each file
        for i, file_path in enumerate(files_to_process, 1):
            if progress and not ctx.quiet:
                console.print(
                    f"[dim]Processing {i}/{len(files_to_process)}: {file_path.name}[/dim]"
                )

            try:
                # Step 1: Transcription (if enabled and file is audio/video)
                transcript_path = None
                if transcribe and file_path.suffix.lower() in [
                    ".mp4",
                    ".mp3",
                    ".wav",
                    ".m4a",
                    ".avi",
                    ".mov",
                    ".mkv",
                ]:
                    if not ctx.quiet:
                        console.print(f"[blue]Transcribing: {file_path.name}[/blue]")

                    result = audio_processor.process(file_path, device=device)
                    if result.success:
                        # Save transcript
                        transcript_file = output / f"{file_path.stem}_transcript.md"
                        transcript_file.parent.mkdir(parents=True, exist_ok=True)

                        # Format transcript content
                        content = format_transcript_content(
                            result.data,
                            file_path.name,
                            transcription_model,
                            device,
                            "md",
                            file_path,
                            timestamps=True,
                            output_dir=output,
                        )

                        with open(transcript_file, "w", encoding="utf-8") as f:
                            f.write(content)

                        transcript_path = transcript_file
                        results["transcribed"].append(str(file_path))

                        if not ctx.quiet:
                            console.print(
                                f"[green]✓ Transcribed: {file_path.name}[/green]"
                            )
                    else:
                        results["errors"].append(
                            f"Transcription failed for {file_path.name}: {result.errors}"
                        )
                        if not ctx.quiet:
                            console.print(
                                f"[red]✗ Transcription failed: {file_path.name}[/red]"
                            )

                # Step 2: Summarization (if enabled)
                summary_path = None
                if summarize:
                    # Determine what to summarize
                    input_for_summary = (
                        transcript_path if transcript_path else file_path
                    )

                    if not ctx.quiet:
                        console.print(
                            f"[blue]Summarizing: {input_for_summary.name}[/blue]"
                        )

                    result = summarizer_processor.process(input_for_summary)
                    if result.success:
                        # Save summary
                        # Clean filename by removing hyphens for better readability
                        clean_filename_for_file = input_for_summary.stem.replace(
                            "-", "_"
                        )

                        # If input file is a transcript, remove _transcript suffix for proper naming
                        if clean_filename_for_file.endswith("_transcript"):
                            clean_filename_for_file = clean_filename_for_file[
                                :-11
                            ]  # Remove "_transcript"

                        summary_file = output / f"{clean_filename_for_file}_summary.md"
                        summary_file.parent.mkdir(parents=True, exist_ok=True)

                        # Clean filename for title by removing hyphens and file extension
                        clean_filename = input_for_summary.stem.replace("-", " ")
                        content = f"# Summary of {clean_filename}\n\n"
                        content += "**Processing:** HCE Claim Extraction\n"
                        content += f"**Model:** {summarization_model}\n"
                        content += f"**Provider:** {result.metadata.get('provider', 'unknown')}\n"
                        content += f"**Generated:** {result.metadata.get('timestamp', 'unknown')}\n"
                        if result.metadata.get("claims_extracted"):
                            content += f"**Claims Extracted:** {result.metadata['claims_extracted']}\n"
                        if result.metadata.get("tier1_claims"):
                            content += f"**High-Quality Claims:** {result.metadata['tier1_claims']}\n"
                        content += "\n---\n\n"

                        # Add link to corresponding transcript
                        base_filename = input_for_summary.stem
                        # If filename ends with _transcript, remove it to get base name
                        if base_filename.endswith("_transcript"):
                            base_filename = base_filename[:-11]  # Remove "_transcript"
                        transcript_link = _generate_obsidian_link(
                            base_filename, "transcript", output
                        )
                        if transcript_link:
                            content += f"## Related Documents\n\n{transcript_link}\n\n"

                        content += result.data

                        with open(summary_file, "w", encoding="utf-8") as f:
                            f.write(content)

                        summary_path = summary_file
                        results["summarized"].append(str(input_for_summary))

                        if not ctx.quiet:
                            console.print(
                                f"[green]✓ Summarized: {input_for_summary.name}[/green]"
                            )

                        # Export to GetReceipts if enabled and summarization succeeded
                        if export_getreceipts and result.success and result.metadata.get("hce_data"):
                            if not ctx.quiet:
                                console.print(
                                    f"[blue]Exporting to GetReceipts: {input_for_summary.name}[/blue]"
                                )
                            
                            try:
                                # Import our knowledge_chipper_integration function
                                import sys
                                from pathlib import Path
                                
                                # Add the project root to Python path to import our integration
                                project_root = Path(__file__).parent.parent.parent.parent
                                if str(project_root) not in sys.path:
                                    sys.path.insert(0, str(project_root))
                                
                                from knowledge_chipper_integration import publish_to_getreceipts
                                
                                # Get HCE pipeline outputs from result metadata
                                hce_data = result.metadata["hce_data"]
                                
                                # Read transcript content for GetReceipts
                                transcript_text = ""
                                if transcript_path and transcript_path.exists():
                                    transcript_text = transcript_path.read_text(encoding="utf-8")
                                elif input_for_summary.suffix.lower() in [".md", ".txt"]:
                                    transcript_text = input_for_summary.read_text(encoding="utf-8")
                                
                                # Convert HCE data to GetReceipts format
                                claims = []
                                people = []
                                jargon = []
                                mental_models = []
                                
                                # Extract claims (only high-quality ones)
                                for claim in hce_data.get("claims", []):
                                    if claim.get("tier") in ["A", "B"]:  # Only high-quality claims
                                        claims.append(claim.get("canonical", ""))
                                
                                # Extract people 
                                for person in hce_data.get("people", []):
                                    people.append({
                                        "name": person.get("normalized", person.get("surface", "")),
                                        "bio": None,  # HCE doesn't provide bio
                                        "expertise": None,  # HCE doesn't provide expertise
                                        "credibility_score": person.get("confidence", 0.5),
                                        "sources": []  # HCE doesn't provide sources
                                    })
                                
                                # Extract jargon terms
                                for term in hce_data.get("jargon", []):
                                    jargon.append({
                                        "term": term.get("term", ""),
                                        "definition": term.get("definition", ""),
                                        "domain": term.get("category"),
                                        "related_terms": [],
                                        "examples": []
                                    })
                                
                                # Extract mental models (concepts)
                                for concept in hce_data.get("concepts", []):
                                    # Convert HCE relations to GetReceipts format
                                    concept_relations = []
                                    for relation in hce_data.get("relations", []):
                                        if relation.get("source_claim_id") == concept.get("model_id"):
                                            rel_type = relation.get("type", "")
                                            # Map HCE relation types to GetReceipts types
                                            if rel_type == "supports":
                                                gr_type = "enables"
                                            elif rel_type == "depends_on":
                                                gr_type = "requires"
                                            elif rel_type == "contradicts":
                                                gr_type = "conflicts_with"
                                            else:
                                                gr_type = "causes"
                                            
                                            concept_relations.append({
                                                "from": concept.get("name", ""),
                                                "to": relation.get("target_claim_id", ""),
                                                "type": gr_type
                                            })
                                    
                                    mental_models.append({
                                        "name": concept.get("name", ""),
                                        "description": concept.get("definition", ""),
                                        "domain": None,  # HCE doesn't provide domain
                                        "key_concepts": concept.get("aliases", []),
                                        "relationships": concept_relations
                                    })
                                
                                # Determine video URL if available
                                video_url = "unknown"
                                if hasattr(input_for_summary, 'url'):
                                    video_url = input_for_summary.url
                                elif transcript_path:
                                    # Try to extract URL from transcript metadata
                                    video_url = f"file://{str(input_for_summary)}"
                                
                                # Call our GetReceipts integration function
                                getreceipts_result = publish_to_getreceipts(
                                    transcript=transcript_text[:5000],  # Limit to first 5000 chars
                                    video_url=video_url,
                                    claims=claims,
                                    people=people,
                                    jargon=jargon,
                                    mental_models=mental_models,
                                    topics=[input_for_summary.stem, "knowledge_chipper", "video_content"]
                                )
                                
                                if getreceipts_result["success"]:
                                    claims_exported = getreceipts_result["published_claims"]
                                    if not ctx.quiet:
                                        console.print(
                                            f"[green]✓ Published {claims_exported} claims to GetReceipts[/green]"
                                        )
                                        
                                        # Show claim URLs
                                        for url in getreceipts_result.get("claim_urls", []):
                                            console.print(f"[dim]📄 View claim: {url}[/dim]")
                                else:
                                    errors = getreceipts_result.get("errors", ["Unknown error"])
                                    if not ctx.quiet:
                                        console.print(
                                            f"[yellow]⚠ GetReceipts export failed: {'; '.join(errors)}[/yellow]"
                                        )
                                    
                            except Exception as e:
                                error_msg = f"GetReceipts export error: {str(e)}"
                                if not ctx.quiet:
                                    console.print(f"[yellow]⚠ {error_msg}[/yellow]")
                                    
                    else:
                        results["errors"].append(
                            f"Summarization failed for {input_for_summary.name}: {result.errors}"
                        )
                        if not ctx.quiet:
                            console.print(
                                f"[red]✗ Summarization failed: {input_for_summary.name}[/red]"
                            )

                # Optionally, run SuperChunk on text/markdown inputs
                if superchunk_artifacts and file_path.suffix.lower() in [".md", ".txt"]:
                    text = Path(file_path).read_text(encoding="utf-8")
                    paragraphs = [p for p in text.split("\n\n") if p.strip()]
                    cfg = SuperChunkConfig.from_global_settings().with_overrides(
                        preset=sc_preset,
                        verify_top_percent=sc_verify_top,
                        max_quote_words=sc_quote_cap,
                        max_concurrent_calls=sc_max_concurrent,
                    )
                    runner = Runner(config=cfg, artifacts_dir=superchunk_artifacts)
                    runner.run(paragraphs)
                    if not ctx.quiet:
                        console.print(
                            f"[green]✓ SuperChunk artifacts written to: {superchunk_artifacts}[/green]"
                        )

                # Collect files for MOC generation (but don't generate yet)
                if moc:
                    # Determine what to use for MOC
                    input_for_moc = (
                        summary_path
                        if summary_path
                        else (transcript_path if transcript_path else file_path)
                    )
                    moc_input_files.append(str(input_for_moc))

            except Exception as e:
                error_msg = f"Processing failed for {file_path.name}: {str(e)}"
                results["errors"].append(error_msg)
                if not ctx.quiet:
                    console.print(f"[red]✗ {error_msg}[/red]")

        # Step 3: MOC Generation (after all files are processed)
        if moc and moc_input_files:
            if not ctx.quiet:
                console.print(
                    f"\n[blue]Generating Map of Content from {len(moc_input_files)} files...[/blue]"
                )

            try:
                result = moc_processor.process(
                    moc_input_files, theme="topical", depth=3, include_beliefs=True
                )
                if result.success:
                    # Save MOC files
                    moc_dir = output / "moc"
                    moc_dir.mkdir(parents=True, exist_ok=True)

                    for filename, content in result.data.items():
                        file_path = moc_dir / filename
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)

                    results["moc_generated"] = moc_input_files

                    if not ctx.quiet:
                        console.print(
                            f"[green]✓ Map of Content generated from {len(moc_input_files)} files[/green]"
                        )
                else:
                    results["errors"].append(f"MOC generation failed: {result.errors}")
                    if not ctx.quiet:
                        console.print(
                            f"[red]✗ MOC generation failed: {result.errors}[/red]"
                        )
            except Exception as e:
                error_msg = f"MOC generation failed: {str(e)}"
                results["errors"].append(error_msg)
                if not ctx.quiet:
                    console.print(f"[red]✗ {error_msg}[/red]")

        # Print summary
        if not ctx.quiet:
            console.print("\n[bold green]Processing completed![/bold green]")
            console.print(
                f"[dim]Files transcribed: {len(results['transcribed'])}[/dim]"
            )
            console.print(f"[dim]Files summarized: {len(results['summarized'])}[/dim]")
            if results["moc_generated"]:
                console.print(
                    f"[dim]MOC generated from: {len(results['moc_generated'])} files[/dim]"
                )
            if results["errors"]:
                console.print(f"[dim]Errors: {len(results['errors'])}[/dim]")
                for error in results["errors"]:
                    console.print(f"[red]  - {error}[/red]")

        # Log processing completion
        log_system_event(
            event="processing_completed",
            component="cli.process",
            status="info",
            input_path=str(input_path),
            output_path=str(output),
            files_processed=len(files_to_process),
            transcribed_count=len(results["transcribed"]),
            summarized_count=len(results["summarized"]),
            moc_generated=bool(results["moc_generated"]),
            moc_input_count=len(results["moc_generated"]),
            error_count=len(results["errors"]),
        )

    except Exception as e:
        console.print(f"[red]✗ Unexpected error during processing:[/red] {e}")
        if ctx.verbose:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
