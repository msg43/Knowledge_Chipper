"""
Command Line Interface for Knowledge System.
Provides comprehensive CLI commands for all system operations.
"""

import sys
import os
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console

from .config import Settings, get_settings
from .errors import KnowledgeSystemError
from .logger import get_logger, log_system_event
from .processors.registry import list_processors, get_all_processor_stats
from .utils.file_io import get_file_info

# Import modular commands
from .commands import transcribe, summarize, moc, process

console = Console()
logger = get_logger("cli")

# Version info
__version__ = "0.1.0"


class CLIContext:
    """Context object for CLI commands."""

    def __init__(self):
        """Initialize CLI context."""
        self.settings: Optional[Settings] = None
        self.verbose: bool = False
        self.quiet: bool = False

    def get_settings(self) -> Settings:
        """Get or initialize settings."""
        if self.settings is None:
            self.settings = get_settings()
        return self.settings


pass_context = click.make_pass_decorator(CLIContext, ensure=True)


def handle_cli_error(func):
    """Decorator to handle CLI errors gracefully."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KnowledgeSystemError as e:
            console.print(f"[red]Error:[/red] {e}")
            if hasattr(e, "context") and e.context:
                console.print(f"[dim]Context: {e.context}[/dim]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            if logger:
                logger.exception("Unexpected CLI error")
            sys.exit(1)

    return wrapper


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to config file"
)
@click.pass_context
def main(
    ctx: click.Context, version: bool, verbose: bool, quiet: bool, config: Optional[str]
) -> None:
    """
    Knowledge System - Comprehensive knowledge processing and management.

    A powerful tool for processing YouTube videos, PDFs, and other content
    into structured knowledge with transcription, summarization, and MOC generation.
    """
    # Configure threading and resource management based on user settings
    
    # Ensure context object exists
    if ctx.obj is None:
        ctx.obj = CLIContext()
    
    # Get settings for thread management
    settings = ctx.obj.get_settings()
    thread_config = settings.thread_management
    
    # Set environment variables based on configuration
    os.environ["OMP_NUM_THREADS"] = str(thread_config.omp_num_threads)
    os.environ["TOKENIZERS_PARALLELISM"] = "true" if thread_config.tokenizers_parallelism else "false"
    
    # Keep MPS fallback setting
    if thread_config.pytorch_enable_mps_fallback:
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    cli_ctx: CLIContext = ctx.obj
    cli_ctx.verbose = verbose
    cli_ctx.quiet = quiet

    # Handle version flag
    if version:
        console.print(f"Knowledge System v{__version__}")
        return

    # Load custom config if provided
    if config:
        try:
            cli_ctx.settings = Settings.from_file(Path(config))
            if verbose:
                console.print(f"[dim]Loaded config from: {config}[/dim]")
        except Exception as e:
            console.print(f"[red]Error loading config:[/red] {e}")
            sys.exit(1)

    # Log CLI session start
    log_system_event(
        event="cli_session_started",
        component="cli",
        status="info",
        version=__version__,
        verbose=verbose,
        quiet=quiet,
    )

    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# Add modular commands to main CLI
main.add_command(transcribe)
main.add_command(summarize)
main.add_command(moc)
main.add_command(process)


@main.command()
@click.argument("watch_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--recursive/--no-recursive", default=True, help="Watch subdirectories recursively"
)
@click.option(
    "--patterns",
    "-p",
    multiple=True,
    default=["*.mp4", "*.mp3", "*.wav", "*.pdf"],
    help="File patterns to watch for",
)
@click.option(
    "--auto-process/--no-auto-process",
    default=True,
    help="Automatically process new files",
)
@click.option(
    "--transcribe/--no-transcribe",
    default=True,
    help="Auto-transcribe audio/video files",
)
@click.option(
    "--summarize/--no-summarize", default=True, help="Auto-summarize processed files"
)
@click.option(
    "--debounce",
    "-d",
    type=int,
    default=5,
    help="Seconds to wait before processing after file change",
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
@pass_context
def watch(
    ctx: CLIContext,
    watch_path: Path,
    recursive: bool,
    patterns: List[str],
    auto_process: bool,
    transcribe: bool,
    summarize: bool,
    debounce: int,
    dry_run: bool,
    device: str,
) -> None:
    """
    Watch directory for new files and auto-process them.

    Monitors a directory for new audio, video, or document files and
    automatically processes them through the transcription and summarization
    pipeline.

    Examples:
        knowledge-system watch ./input/
        knowledge-system watch ~/Downloads --patterns "*.mp4" "*.pdf"
        knowledge-system watch ./videos --no-summarize --debounce 10
    """
    if not ctx.quiet:
        console.print(f"[bold cyan]Watching:[/bold cyan] {watch_path}")
        console.print(
            f"[dim]Patterns: {', '.join(patterns)}, Recursive: {recursive}[/dim]"
        )
        console.print(
            f"[dim]Auto-process: {auto_process}, Debounce: {debounce}s[/dim]")

    if dry_run:
        console.print(
            "[yellow][DRY RUN] Would start file watcher with the above settings.[/yellow]"
        )
        console.print(
            f"[dim]Would watch for patterns: {', '.join(patterns)}[/dim]")
        if auto_process:
            console.print("[dim]Would auto-process new files[/dim]")
            if transcribe:
                console.print("[dim]Would transcribe audio/video files[/dim]")
            if summarize:
                console.print("[dim]Would summarize text files[/dim]")
        return

    # Log watch start
    log_system_event(
        event="watch_started",
        component="cli.watch",
        status="info",
        watch_path=str(watch_path),
        patterns=list(patterns),
        recursive=recursive,
        auto_process=auto_process,
    )

    try:
        # Define processing callback
        def process_file(file_path: Path):
            """Process a new or modified file."""
            settings = ctx.get_settings()
            if not ctx.quiet:
                console.print(f"[cyan]Processing:[/cyan] {file_path}")
            try:
                # Transcription for audio/video
                if transcribe and file_path.suffix.lower() in [
                    ".mp4",
                    ".mp3",
                    ".wav",
                    ".webm",
                ]:
                    from .processors.audio_processor import AudioProcessor
                    processor = AudioProcessor(device=device)
                    result = processor.process(file_path, device=device)
                    if result.success:
                        console.print(
                            f"[green]✓ Transcribed: {file_path}[/green]")
                    else:
                        console.print(
                            f"[red]✗ Transcription failed for {file_path}: {'; '.join(result.errors)}[/red]"
                        )
                # Summarization for markdown/text
                if summarize and file_path.suffix.lower() in [".md", ".txt"]:
                    from .processors.summarizer import SummarizerProcessor
                    # Use SummarizerProcessor
                    summarizer = SummarizerProcessor(
                        provider=settings.summarization.provider,
                        model=settings.summarization.model,
                        max_tokens=settings.summarization.max_tokens,
                    )
                    result = summarizer.process(file_path, dry_run=False)
                    if result.success:
                        console.print(
                            f"[green]✓ Summarized: {file_path}[/green]")
                    else:
                        console.print(
                            f"[red]✗ Summarization failed for {file_path}: {'; '.join(result.errors)}[/red]"
                        )
                # Log the processing
                log_system_event(
                    event="file_processed",
                    component="cli.watch",
                    status="info",
                    file_path=str(file_path),
                    auto_process=auto_process,
                )
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                if not ctx.quiet:
                    console.print(
                        f"[red]Error processing {file_path}:[/red] {e}")

        # Start the file watcher
        from .watchers import FileWatcher
        
        watcher = FileWatcher(
            directory=watch_path,
            patterns=list(patterns),
            callback=process_file if auto_process else None,
            debounce=debounce,
            recursive=recursive,
        )

        if not ctx.quiet:
            console.print(f"[green]✓ Started watching: {watch_path}[/green]")
            console.print(f"[dim]Patterns: {', '.join(patterns)}[/dim]")
            console.print(f"[dim]Auto-process: {auto_process}[/dim]")
            console.print(f"[dim]Debounce: {debounce}s[/dim]")
            console.print("[dim]Press Ctrl+C to stop watching...[/dim]")

        # Keep the watcher running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            if not ctx.quiet:
                console.print("\n[yellow]Stopping file watcher...[/yellow]")
            watcher.stop()
            if not ctx.quiet:
                console.print("[green]✓ File watcher stopped[/green]")

    except Exception as e:
        console.print(f"[red]✗ Error starting file watcher:[/red] {e}")
        if ctx.verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command()
@click.option(
    "--processors/--no-processors", default=True, help="Show processor statistics"
)
@click.option("--paths/--no-paths", default=True, help="Show configured paths")
@click.option("--settings/--no-settings",
              default=False, help="Show all settings")
@click.option("--logs/--no-logs", default=False,
              help="Show recent log entries")
@pass_context
def status(
    ctx: CLIContext, processors: bool, paths: bool, settings: bool, logs: bool
) -> None:
    """
    Show system status and statistics.

    Displays information about processor performance, configured paths,
    system settings, and recent activity.

    Examples:
        knowledge-system status
        knowledge-system status --settings
        knowledge-system status --logs --no-processors
    """
    settings_obj = ctx.get_settings()

    console.print("[bold blue]Knowledge System Status[/bold blue]\n")

    # Show processor statistics
    if processors:
        console.print("[bold]Processor Statistics:[/bold]")
        processor_stats = get_all_processor_stats()

        if processor_stats:
            from rich.table import Table
            table = Table()
            table.add_column("Processor", style="cyan")
            table.add_column("Processed", justify="right")
            table.add_column("Success Rate", justify="right")
            table.add_column("Avg Time", justify="right")

            for name, stats in processor_stats.items():
                success_rate = (
                    f"{stats['success_rate']:.1%}"
                    if stats["processed_count"] > 0
                    else "N/A"
                )
                avg_time = (
                    f"{stats['average_processing_time']:.2f}s"
                    if stats["processed_count"] > 0
                    else "N/A"
                )

                table.add_row(
                    name, str(stats["processed_count"]), success_rate, avg_time
                )

            console.print(table)
        else:
            console.print("[dim]No processor statistics available[/dim]")

        console.print()

    # Show configured paths
    if paths:
        console.print("[bold]Configured Paths:[/bold]")
        from rich.table import Table
        paths_table = Table()
        paths_table.add_column("Path Type", style="cyan")
        paths_table.add_column("Location", style="green")
        paths_table.add_column("Exists", justify="center")

        path_configs = [
            ("Input", settings_obj.paths.input),
            ("Output", settings_obj.paths.output),
            ("Transcripts", settings_obj.paths.transcripts),
            ("Summaries", settings_obj.paths.summaries),
            ("MOCs", settings_obj.paths.mocs),
            ("Cache", settings_obj.paths.cache),
            ("Logs", settings_obj.paths.logs),
        ]

        for path_type, path_str in path_configs:
            path_obj = Path(path_str)
            exists = "✓" if path_obj.exists() else "✗"
            exists_style = "green" if path_obj.exists() else "red"

            paths_table.add_row(
                path_type, str(path_obj), f"[{exists_style}]{exists}[/{exists_style}]"
            )

        console.print(paths_table)
        console.print()

    # Show all settings if requested
    if settings:
        console.print("[bold]System Settings:[/bold]")
        console.print(f"[dim]{settings_obj.model_dump_json(indent=2)}[/dim]")
        console.print()

    # Show recent logs if requested
    if logs:
        console.print("[bold]Recent Log Entries:[/bold]")
        log_file = Path(settings_obj.paths.logs) / "knowledge_system.log"

        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    recent_lines = lines[-10:] if len(lines) > 10 else lines

                for line in recent_lines:
                    console.print(f"[dim]{line.strip()}[/dim]")
            except Exception as e:
                console.print(f"[red]Error reading log file:[/red] {e}")
        else:
            console.print("[dim]No log file found[/dim]")


@main.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@pass_context
def info(ctx: CLIContext, file_path: Path) -> None:
    """
    Show detailed information about a file.

    Displays file metadata, processing history, and compatibility information.

    Examples:
        knowledge-system info video.mp4
        knowledge-system info transcript.md
    """
    if not ctx.quiet:
        console.print(
            f"[bold blue]File Information:[/bold blue] {file_path}\n")

    try:
        # Get file information
        file_info = get_file_info(file_path)

        # Display basic info
        from rich.table import Table
        info_table = Table()
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="green")

        info_table.add_row("Path", str(file_path))
        info_table.add_row("Size", file_info.get("size_human", "Unknown"))
        info_table.add_row("Modified", file_info.get("modified", "Unknown"))
        info_table.add_row("Type", file_info.get("mime_type", "Unknown"))

        if "hash_md5" in file_info:
            info_table.add_row("MD5", file_info["hash_md5"])

        console.print(info_table)

        # Check processor compatibility
        available_processors = list_processors()
        if available_processors:
            console.print("\n[bold]Processor Compatibility:[/bold]")

            # Import processors to check compatibility
            from .processors.audio_processor import AudioProcessor
            from .processors.summarizer import SummarizerProcessor
            from .processors.moc import MOCProcessor
            from .processors.pdf import PDFProcessor

            compatibility_table = Table()
            compatibility_table.add_column("Processor", style="cyan")
            compatibility_table.add_column("Compatible", justify="center")
            compatibility_table.add_column("Supported Extensions", style="dim")

            # Check each processor
            processors_to_check = [
                (
                    "AudioProcessor",
                    AudioProcessor,
                    [
                        ".mp3",
                        ".mp4",
                        ".wav",
                        ".m4a",
                        ".flac",
                        ".ogg",
                        ".webm",
                        ".avi",
                        ".mov",
                        ".mkv",
                    ],
                ),
                ("PDFProcessor", PDFProcessor, [".pdf"]),
                (
                    "SummarizerProcessor",
                    SummarizerProcessor,
                    [".txt", ".md", ".markdown"],
                ),
                ("MOCProcessor", MOCProcessor, [".md", ".txt"]),
            ]

            file_ext = file_path.suffix.lower()

            for proc_name, proc_class, supported_exts in processors_to_check:
                is_compatible = file_ext in supported_exts
                compatible_symbol = "✓" if is_compatible else "✗"
                compatible_color = "green" if is_compatible else "red"

                compatibility_table.add_row(
                    proc_name,
                    f"[{compatible_color}]{compatible_symbol}[/{compatible_color}]",
                    ", ".join(supported_exts),
                )

            console.print(compatibility_table)

    except Exception as e:
        console.print(f"[red]Error getting file info:[/red] {e}")


@main.command()
@pass_context
def gui(ctx: CLIContext) -> None:
    """Launch the graphical user interface."""
    try:
        from .gui import main as gui_main
        gui_main()
    except ImportError as e:
        console.print(f"[red]Error: GUI dependencies not available: {e}")
        console.print(
            "[yellow]Install GUI dependencies with: pip install PyQt6[/yellow]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error launching GUI: {e}")
        sys.exit(1)


@click.group()
def youtube():
    """YouTube-specific commands for troubleshooting and authentication."""
    pass


# Add youtube command group to main CLI
main.add_command(youtube)


@youtube.command()
def auth_status():
    """Check YouTube authentication status and diagnostics."""
    from .utils.youtube_utils import get_authentication_status
    
    status = get_authentication_status()
    
    click.echo("YouTube Authentication Status:")
    click.echo("=" * 40)
    
    if status["has_cached_strategy"]:
        click.echo("✓ Cached authentication strategy found")
        if status["strategy_age"]:
            age_minutes = status["strategy_age"] / 60
            click.echo(f"  Age: {age_minutes:.1f} minutes")
        if status["strategy_details"]:
            click.echo(f"  Strategy: {status['strategy_details']}")
    else:
        click.echo("✗ No cached authentication strategy")
    
    if status["has_cached_cookies"]:
        click.echo("✓ Cached cookies found")
        if status["cookie_age"]:
            age_minutes = status["cookie_age"] / 60
            click.echo(f"  Age: {age_minutes:.1f} minutes")
    else:
        click.echo("✗ No cached cookies")
    
    if status["manual_cookie_file"]:
        click.echo(f"✓ Manual cookie file found: {status['manual_cookie_file']}")
    else:
        click.echo("✗ No manual cookie file found")
    
    click.echo("\nRecommendations:")
    if not status["has_cached_strategy"] and not status["manual_cookie_file"]:
        click.echo("- Create a manual cookie file (run 'knowledge-system youtube cookie-instructions')")
        click.echo("- Visit YouTube videos in your browser first")
        click.echo("- Try a different network connection")


@youtube.command()
def clear_cache():
    """Clear YouTube authentication cache to force re-authentication."""
    from .utils.youtube_utils import clear_authentication_cache
    
    clear_authentication_cache()
    click.echo("YouTube authentication cache cleared.")
    click.echo("Next YouTube operation will attempt fresh authentication.")


@youtube.command()
def cookie_instructions():
    """Show instructions for creating a manual cookie file."""
    from .utils.youtube_utils import create_cookie_instructions
    
    instructions = create_cookie_instructions()
    click.echo(instructions)


@youtube.command()
@click.argument('url')
def test_auth(url):
    """Test YouTube authentication with a specific URL."""
    from .utils.youtube_utils import get_single_working_strategy
    
    click.echo(f"Testing authentication with: {url}")
    
    try:
        strategy = get_single_working_strategy()
        click.echo(f"Using strategy: {strategy}")
        
        # Simple authentication test - just check if strategy is available
        if strategy:
            click.echo("✓ Authentication strategy found!")
        else:
            click.echo("✗ No authentication strategy available!")
            click.echo("Consider creating a manual cookie file or visiting YouTube in your browser first.")
            
    except Exception as e:
        click.echo(f"✗ Authentication test failed with error: {e}")


if __name__ == "__main__":
    main()
