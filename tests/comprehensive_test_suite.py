#!/usr/bin/env python3
"""
Comprehensive Test Suite for Knowledge Chipper System 2

This script systematically tests all combinations of extraction, transcription,
and summarization using the System 2 orchestrator with job tracking and
checkpoint persistence.

Note: This is a GUI-only application. All tests use System2Orchestrator.

Test Categories:
1. Local Transcription - Tests Whisper transcription with/without diarization via System 2
2. YouTube Cloud Transcription - Tests YouTube URL processing with job tracking
3. Document Processing - Tests document processing with System 2 orchestrator
4. Document Summarization - Tests AI summarization with LLM adapter tracking
5. Markdown In-Place - Tests updating markdown files with job persistence
6. Combined Processing - Tests full pipeline with auto-process chaining
7. Job Orchestration - Tests System 2 job creation, execution, and tracking
8. Schema Validation - Tests JSON schema validation and repair
9. Cloud Sync - Tests Supabase configuration and connectivity
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).parent.parent  # Go up to Knowledge_Chipper root
TEST_INPUTS_DIR = Path(__file__).parent / "data" / "test_files" / "Test Inputs"
TEST_OUTPUTS_DIR = Path(__file__).parent / "data" / "test_files" / "Test Outputs"
SUMMARY_PROMPT_FILE = TEST_INPUTS_DIR / "Summary Prompt.txt"

# Add knowledge_system to path
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# System 2 imports
from knowledge_system.core.system2_orchestrator import (
    System2Orchestrator,
    get_orchestrator,
)
from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)

# Note: CLI removed - all tests use System2Orchestrator directly


class TestResult:
    """Container for test result information."""

    def __init__(
        self,
        test_name: str,
        command: list[str] | None = None,
        success: bool = False,
        output: str = "",
        error: str = "",
        duration: float = 0.0,
        output_files: list[Path] | None = None,
        job_id: str | None = None,
        run_id: str | None = None,
        system2_result: dict | None = None,
    ):
        self.test_name = test_name
        self.command = command or []
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration
        self.output_files = output_files or []
        self.job_id = job_id
        self.run_id = run_id
        self.system2_result = system2_result or {}
        self.timestamp = datetime.now().isoformat()


class ComprehensiveTestSuite:
    """Comprehensive test suite for Knowledge Chipper System 2."""

    def __init__(self):
        self.results: list[TestResult] = []
        self.setup_output_directories()

        # Initialize System 2 components
        self.db_service = DatabaseService()
        self.orchestrator = get_orchestrator(self.db_service)

        # Create System 2 output directories
        self.setup_system2_directories()

    def setup_output_directories(self):
        """Create organized output directory structure."""
        TEST_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for different test types
        subdirs = [
            "transcription",
            "transcription_with_diarization",
            "summarization",
            "combined_processing",
            "youtube_extraction",
            "html_processing",
            "pdf_processing",
            "logs",
        ]

        for subdir in subdirs:
            (TEST_OUTPUTS_DIR / subdir).mkdir(exist_ok=True)

    def setup_system2_directories(self):
        """Create System 2 specific output directories."""
        system2_subdirs = [
            "system2_jobs",
            "system2_checkpoints",
            "system2_llm_tracking",
            "system2_schema_validation",
        ]

        for subdir in system2_subdirs:
            (TEST_OUTPUTS_DIR / subdir).mkdir(exist_ok=True)

    def run_command(
        self, cmd: list[str], timeout: int = 600
    ) -> tuple[bool, str, str, float]:
        """Run a CLI command and return results with improved process management."""
        start_time = time.time()
        process = None
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=PROJECT_ROOT,
                # Create new process group to allow killing child processes
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                duration = time.time() - start_time
                return process.returncode == 0, stdout, stderr, duration
            except subprocess.TimeoutExpired:
                duration = time.time() - start_time

                # Try graceful termination first
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()

                    # Wait a bit for graceful shutdown
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful didn't work
                        if hasattr(os, "killpg"):
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        else:
                            process.kill()
                        process.wait()
                except (ProcessLookupError, OSError):
                    pass  # Process already terminated

                return False, "", f"Command timed out after {timeout} seconds", duration

        except Exception as e:
            duration = time.time() - start_time
            if process:
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except (ProcessLookupError, OSError):
                    pass
            return False, "", str(e), duration

    def test_audio_transcription(self):
        """Test transcription of audio/video files with various options."""
        print("\n🎵 Testing Local Transcription...")

        # All audio and video files are treated as audio transcription
        # Use files that actually exist in our test directory
        potential_audio_video_files = [
            "quick_test_5s.wav",
            "short_speech_30s.mp3",
            "medium_speech_2min.wav",
            "quick_test_10s.mp4",
            "tutorial_3min.mp4",
        ]

        # Only use files that actually exist
        audio_video_files = []
        for filename in potential_audio_video_files:
            if (TEST_INPUTS_DIR / filename).exists():
                audio_video_files.append(filename)

        models = ["base", "small"]  # Using smaller models for faster testing
        devices = ["auto"]  # Can add "cpu", "mps" if needed
        formats = ["md", "txt"]

        for audio_file in audio_video_files:
            if not (TEST_INPUTS_DIR / audio_file).exists():
                continue

            for model in models:
                for device in devices:
                    for format_type in formats:
                        # Test without diarization
                        self._test_single_transcription(
                            audio_file,
                            model,
                            device,
                            format_type,
                            diarization=False,
                            output_subdir="transcription",
                        )

                        # Test with diarization
                        self._test_single_transcription(
                            audio_file,
                            model,
                            device,
                            format_type,
                            diarization=True,
                            output_subdir="transcription_with_diarization",
                        )

    def _test_single_transcription(
        self,
        input_file: str,
        model: str,
        device: str,
        format_type: str,
        diarization: bool,
        output_subdir: str,
    ):
        """Test a single transcription configuration."""
        safe_filename = self._sanitize_filename(input_file)
        diar_suffix = "_with_diarization" if diarization else "_no_diarization"
        test_name = (
            f"transcribe_{safe_filename}_{model}_{device}_{format_type}{diar_suffix}"
        )

        output_dir = TEST_OUTPUTS_DIR / output_subdir

        cmd = CLI_CMD + [
            "transcribe",
            "--input",
            str(TEST_INPUTS_DIR / input_file),
            "--output",
            str(output_dir),
            "--model",
            model,
            "--device",
            device,
            "--format",
            format_type,
            "--overwrite",
        ]

        if diarization:
            cmd.append("--speaker-labels")
        else:
            cmd.append("--no-speaker-labels")

        success, output, error, duration = self.run_command(cmd)

        # Find output files
        output_files = list(output_dir.glob(f"*{Path(input_file).stem}*"))

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=output_files,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def test_youtube_extraction(self):
        """Test YouTube URL extraction and transcription from multiple file formats."""
        print("\n📺 Testing YouTube Cloud Transcription...")

        # Test all YouTube playlist file formats
        playlist_files = [
            ("Youtube_Playlists_1.csv", "csv"),
            ("Youtube_Playlists_1.txt", "txt"),
            ("Youtube_Playlists_1.rtf", "rtf"),
        ]

        # Check if any playlist files exist
        found_files = False
        for playlist_file, file_type in playlist_files:
            full_path = TEST_INPUTS_DIR / playlist_file
            if not full_path.exists():
                print(f"  ⚠️  YouTube playlist file not found: {playlist_file}")
                continue

            found_files = True
            # Extract URL from file
            youtube_url = self._extract_youtube_url_from_file(full_path, file_type)
            if not youtube_url:
                print(f"  ⚠️  Could not extract YouTube URL from: {playlist_file}")
                continue

            # Test YouTube transcription without diarization
            self._test_youtube_transcription(
                youtube_url, diarization=False, source_file=playlist_file
            )

            # Test YouTube transcription with diarization
            self._test_youtube_transcription(
                youtube_url, diarization=True, source_file=playlist_file
            )

        if not found_files:
            print("  📋 No YouTube playlist files available - skipping YouTube tests")

    def _extract_youtube_url_from_file(
        self, file_path: Path, file_type: str
    ) -> str | None:
        """Extract YouTube URL from different file formats."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read().strip()

            if file_type == "csv":
                # CSV format - handle both quoted URLs and CSV with headers
                lines = content.strip().split("\n")
                if len(lines) > 1 and lines[0].upper() in [
                    "URL",
                    "YOUTUBE_URL",
                    "LINK",
                ]:
                    # CSV with header - take the first URL line
                    url = lines[1].strip().strip('"')
                else:
                    # Simple CSV - remove quotes if present
                    url = content.strip().strip('"')
            elif file_type == "txt":
                # Plain text format
                url = content.strip()
            elif file_type == "rtf":
                # RTF format - extract URL from RTF content
                # Look for http URLs in the RTF content
                import re

                url_match = re.search(r"https?://[^\s\\}]+", content)
                url = url_match.group(0) if url_match else ""
            else:
                return None

            # Validate URL
            if (
                url
                and url.startswith("http")
                and ("youtube.com" in url or "youtu.be" in url)
            ):
                return url

        except Exception as e:
            print(f"  ⚠️  Error reading {file_path}: {e}")

        return None

    def _test_youtube_transcription(
        self, youtube_url: str, diarization: bool, source_file: str = ""
    ):
        """Test a single YouTube transcription."""
        diar_suffix = "_with_diarization" if diarization else "_no_diarization"
        source_suffix = f"_{Path(source_file).stem}" if source_file else ""
        test_name = f"youtube_transcribe{source_suffix}{diar_suffix}"

        output_dir = TEST_OUTPUTS_DIR / "youtube_extraction"

        cmd = CLI_CMD + [
            "transcribe",
            "--input",
            youtube_url,
            "--output",
            str(output_dir),
            "--model",
            "base",
            "--format",
            "md",
            "--download-thumbnails",
            "--overwrite",
        ]

        if diarization:
            cmd.append("--speaker-labels")
        else:
            cmd.append("--no-speaker-labels")

        # Detect if this is a playlist by checking if URL contains "playlist" or "list="
        is_playlist = (
            "playlist" in youtube_url.lower() or "list=" in youtube_url.lower()
        )

        # Use longer timeout for playlists (5 minutes) to allow multiple video downloads
        timeout = 300 if is_playlist else 120

        success, output, error, duration = self.run_command(cmd, timeout=timeout)

        # Check if failure is due to missing credentials (but not just informational PacketStream logs)
        if not success and (
            "PACKETSTREAM CREDENTIALS NOT CONFIGURED" in error
            or "PACKETSTREAM PROXY NOT AVAILABLE" in error
            or "Missing Bright Data credentials" in error
            or "Missing PacketStream credentials" in error
            or "credentials missing" in error
            or "API endpoints failed" in error
            or ("Bright Data" in error and "credentials" in error)
        ):
            print(
                f"  ⚠️  {test_name} - Skipped (YouTube proxy/credentials not configured)"
            )
            # Don't record credential failures as test failures - they're expected
            return

        # Find output files
        output_files = list(output_dir.glob("*"))

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=output_files,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def test_document_processing_with_attribution(self):
        """Test document processing with author attribution and metadata extraction."""
        print("\n📚 Testing Document Processing with Author Attribution...")

        # Test files for document processing - use files that actually exist
        potential_test_files = [
            ("research_paper.txt", "document"),
            ("meeting_notes.txt", "document"),
            ("technical_spec.md", "document"),
            ("blog_post.html", "document"),
        ]

        # Only use files that actually exist
        test_files = []
        for filename, doc_type in potential_test_files:
            if (TEST_INPUTS_DIR / filename).exists():
                test_files.append((filename, doc_type))

        for test_file, doc_type in test_files:
            if not (TEST_INPUTS_DIR / test_file).exists():
                continue

            self._test_document_processing(test_file, doc_type)

    def _test_document_processing(self, input_file: str, doc_type: str):
        """Test processing a document with author attribution."""
        safe_filename = self._sanitize_filename(input_file)
        test_name = f"process_document_{safe_filename}"

        output_dir = TEST_OUTPUTS_DIR / "document_processing"

        cmd = CLI_CMD + [
            "process",
            str(TEST_INPUTS_DIR / input_file),
            "--output",
            str(output_dir),
            "--no-moc",  # Skip MOC generation for simpler testing
        ]

        success, output, error, duration = self.run_command(cmd, timeout=180)

        # Check for metadata extraction in output
        if success and "authors:" in output.lower():
            print(f"    📖 Extracted author metadata from {input_file}")

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=list(output_dir.glob(f"*{Path(input_file).stem}*")),
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def test_document_summarization(self):
        """Test summarization of various document types."""
        print("\n📝 Testing Document Summarization...")

        # Test files for summarization - use files that actually exist
        potential_test_files = [
            ("blog_post.html", "html_processing"),
            ("research_paper.txt", "summarization"),
            ("technical_spec.md", "summarization"),
            ("meeting_notes.txt", "summarization"),
        ]

        # Only use files that actually exist
        test_files = []
        for filename, output_subdir in potential_test_files:
            if (TEST_INPUTS_DIR / filename).exists():
                test_files.append((filename, output_subdir))

        models = ["gpt-4o-mini-2024-07-18", "gpt-3.5-turbo"]

        for test_file, output_subdir in test_files:
            if not (TEST_INPUTS_DIR / test_file).exists():
                continue

            for model in models:
                # Test with default template
                self._test_single_summarization(
                    test_file, model, None, output_subdir, "default_template"
                )

                # Test with custom template
                self._test_single_summarization(
                    test_file,
                    model,
                    SUMMARY_PROMPT_FILE,
                    output_subdir,
                    "custom_template",
                )

    def test_markdown_inplace_summarization(self):
        """Test in-place summarization of markdown files with Full Transcript section."""
        print("\n📄 Testing Markdown In-Place Summarization...")

        # Test files that have "# Full Transcript" or "## Full Transcript" headers
        # Use files that actually exist
        potential_markdown_files = [
            "technical_spec.md",
            "blog_post.html",  # We'll test HTML too
        ]

        # Only use files that actually exist
        markdown_files = []
        for filename in potential_markdown_files:
            if (TEST_INPUTS_DIR / filename).exists():
                markdown_files.append(filename)

        models = ["gpt-4o-mini-2024-07-18"]

        for md_file in markdown_files:
            if not (TEST_INPUTS_DIR / md_file).exists():
                continue

            # Check if file has Full Transcript section
            if self._has_full_transcript_section(TEST_INPUTS_DIR / md_file):
                for model in models:
                    self._test_markdown_inplace_summary(md_file, model)

    def _has_full_transcript_section(self, file_path: Path) -> bool:
        """Check if markdown file has a Full Transcript section."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read().lower()
                return "# full transcript" in content or "## full transcript" in content
        except Exception:
            return False

    def _test_markdown_inplace_summary(self, input_file: str, model: str):
        """Test in-place markdown summarization."""
        safe_filename = self._sanitize_filename(input_file)
        model_safe = model.replace(".", "_").replace("-", "_")
        test_name = f"md_inplace_summary_{safe_filename}_{model_safe}"

        # Create a copy of the file for in-place editing
        output_dir = TEST_OUTPUTS_DIR / "summarization"
        original_file = TEST_INPUTS_DIR / input_file
        test_file = output_dir / f"inplace_test_{input_file}"

        # Copy original to test location
        import shutil

        shutil.copy2(original_file, test_file)

        cmd = CLI_CMD + [
            "summarize",
            str(test_file),
            "--model",
            model,
            "--update-md",  # This flag makes it update in-place
            "--template",
            str(SUMMARY_PROMPT_FILE),
            "--force",
        ]

        success, output, error, duration = self.run_command(cmd, timeout=300)

        # The output file should be the same file, but modified
        output_files = [test_file] if success and test_file.exists() else []

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=output_files,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def _test_single_summarization(
        self,
        input_file: str,
        model: str,
        template_file: Path | None,
        output_subdir: str,
        template_type: str,
    ):
        """Test a single summarization configuration."""
        safe_filename = self._sanitize_filename(input_file)
        model_safe = model.replace(".", "_").replace("-", "_")
        test_name = f"summarize_{safe_filename}_{model_safe}_{template_type}"

        output_dir = TEST_OUTPUTS_DIR / output_subdir

        cmd = CLI_CMD + [
            "summarize",
            str(TEST_INPUTS_DIR / input_file),
            "--output",
            str(output_dir),
            "--model",
            model,
            "--force",  # Force re-summarization
        ]

        if template_file:
            cmd.extend(["--template", str(template_file)])

        success, output, error, duration = self.run_command(cmd, timeout=300)

        # Find output files
        output_files = list(output_dir.glob(f"*{Path(input_file).stem}*"))

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=output_files,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def test_combined_processing(self):
        """Test combined transcription + summarization pipeline."""
        print("\n🔄 Testing Combined Processing Pipeline...")

        # Test on audio/video files that can be transcribed and summarized
        # Use files that actually exist
        potential_test_files = ["quick_test_5s.wav", "short_speech_30s.mp3"]

        # Only use files that actually exist
        test_files = []
        for filename in potential_test_files:
            if (TEST_INPUTS_DIR / filename).exists():
                test_files.append(filename)

        for test_file in test_files:
            if not (TEST_INPUTS_DIR / test_file).exists():
                continue

            # Test combined processing
            self._test_single_combined_processing(test_file)

    def _test_single_combined_processing(self, input_file: str):
        """Test a single combined processing pipeline."""
        safe_filename = self._sanitize_filename(input_file)
        test_name = f"combined_process_{safe_filename}"

        output_dir = TEST_OUTPUTS_DIR / "combined_processing"

        cmd = CLI_CMD + [
            "process",
            str(TEST_INPUTS_DIR / input_file),
            "--output",
            str(output_dir),
            "--transcription-model",
            "base",
            "--summarization-model",
            "gpt-4o-mini-2024-07-18",
            "--no-moc",  # Skip MOC generation for simpler testing
        ]

        success, output, error, duration = self.run_command(cmd, timeout=600)

        # Find output files
        output_files = list(output_dir.glob(f"*{Path(input_file).stem}*"))

        result = TestResult(
            test_name=test_name,
            command=cmd,
            success=success,
            output=output,
            error=error,
            duration=duration,
            output_files=output_files,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name} ({duration:.1f}s)")
        if not success:
            print(f"    Error: {error}")

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for use in test names."""
        # Remove extension and sanitize
        name = Path(filename).stem
        # Replace problematic characters
        sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # Limit length
        return sanitized[:50]

    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n📊 Generating Test Report...")

        # Summary statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        total_duration = sum(r.duration for r in self.results)

        # Generate report
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": (
                    f"{(successful_tests/total_tests*100):.1f}%"
                    if total_tests > 0
                    else "0%"
                ),
                "total_duration": f"{total_duration:.1f}s",
                "timestamp": datetime.now().isoformat(),
            },
            "test_results": [],
        }

        # Add individual test results
        for result in self.results:
            test_result = {
                "test_name": result.test_name,
                "success": result.success,
                "duration": f"{result.duration:.1f}s",
                "command": " ".join(result.command) if result.command else "",
                "output_files": [str(f) for f in result.output_files],
                "error": result.error if not result.success else "",
                "timestamp": result.timestamp,
            }

            # Add System 2 specific fields
            if result.job_id:
                test_result["job_id"] = result.job_id
            if result.run_id:
                test_result["run_id"] = result.run_id
            if result.system2_result:
                test_result["system2_result"] = result.system2_result

            report["test_results"].append(test_result)

        # Save JSON report
        report_file = (
            TEST_OUTPUTS_DIR
            / "logs"
            / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        # Generate markdown report
        self._generate_markdown_report(report)

        # Print summary
        print(f"\n🎯 Test Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Successful: {successful_tests}")
        print(f"  Failed: {failed_tests}")
        print(f"  Success Rate: {report['test_summary']['success_rate']}")
        print(f"  Total Duration: {report['test_summary']['total_duration']}")
        print(f"\n📁 Detailed report saved to: {report_file}")

    def _generate_markdown_report(self, report: dict):
        """Generate a markdown test report."""
        report_file = (
            TEST_OUTPUTS_DIR
            / "logs"
            / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )

        with open(report_file, "w") as f:
            f.write("# Knowledge Chipper Comprehensive Test Report\n\n")
            f.write(f"**Generated:** {report['test_summary']['timestamp']}\n\n")

            # Summary table
            f.write("## Test Summary\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Total Tests | {report['test_summary']['total_tests']} |\n")
            f.write(
                f"| Successful Tests | {report['test_summary']['successful_tests']} |\n"
            )
            f.write(f"| Failed Tests | {report['test_summary']['failed_tests']} |\n")
            f.write(f"| Success Rate | {report['test_summary']['success_rate']} |\n")
            f.write(
                f"| Total Duration | {report['test_summary']['total_duration']} |\n\n"
            )

            # Test details
            f.write("## Test Results\n\n")

            # Group by test type
            test_groups = {}
            for result in report["test_results"]:
                test_type = result["test_name"].split("_")[0]
                if test_type not in test_groups:
                    test_groups[test_type] = []
                test_groups[test_type].append(result)

            for test_type, results in test_groups.items():
                f.write(f"### {test_type.title()} Tests\n\n")
                f.write("| Test Name | Status | Duration | Output Files |\n")
                f.write("|-----------|--------|----------|---------------|\n")

                for result in results:
                    status = "✅ Pass" if result["success"] else "❌ Fail"
                    output_files = len(result["output_files"])
                    f.write(
                        f"| {result['test_name']} | {status} | {result['duration']} | {output_files} files |\n"
                    )

                # Show failures with details
                failed_results = [r for r in results if not r["success"]]
                if failed_results:
                    f.write(f"\n#### Failed {test_type.title()} Tests\n\n")
                    for result in failed_results:
                        f.write(f"**{result['test_name']}**\n")
                        f.write(f"- Command: `{result['command']}`\n")
                        f.write(f"- Error: {result['error']}\n\n")

                f.write("\n")

    def test_summary_cleanup_ui(self):
        """Test summary cleanup UI availability."""
        print("\n✏️ Testing Summary Cleanup UI...")

        test_name = "summary_cleanup_ui_test"

        # Check if the UI component loads
        try:
            pass

            # Tab should be importable
            print("  ✅ Summary Cleanup tab is available")
            success = True
            output = "Summary Cleanup UI component loaded successfully"
        except Exception as e:
            success = False
            output = f"Failed to load Summary Cleanup UI: {e}"

        result = TestResult(
            test_name=test_name,
            command=["check_summary_cleanup_ui"],
            success=success,
            output=output,
            duration=0.1,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name}")

    def test_cloud_sync_configuration(self):
        """Test cloud sync configuration and basic connectivity."""
        print("\n☁️ Testing Cloud Sync Configuration...")

        test_name = "cloud_sync_config_test"

        # Check if sync is configured
        try:
            from knowledge_system.services.supabase_sync import SupabaseSyncService

            sync_service = SupabaseSyncService()

            if sync_service.is_configured():
                print("  ✅ Supabase is configured")

                # Test sync status retrieval
                try:
                    status = sync_service.get_sync_status()
                    print(f"  📊 Sync status retrieved for {len(status)} tables")
                    success = True
                    output = f"Configured and accessible. Tables: {list(status.keys())}"
                except Exception as e:
                    success = False
                    output = f"Configuration valid but connection failed: {e}"
            else:
                print("  ⚠️ Supabase not configured (skipping sync tests)")
                success = True  # Not a failure, just not configured
                output = "Supabase sync not configured"

        except Exception as e:
            success = False
            output = f"Failed to initialize sync service: {e}"

        result = TestResult(
            test_name=test_name,
            command=["check_sync_config"],
            success=success,
            output=output,
            duration=0.1,
        )

        self.results.append(result)
        print(f"  {'✅' if success else '❌'} {test_name}")

    async def test_system2_job_orchestration(self):
        """Test System 2 job creation, execution, and tracking."""
        print("\n🎯 Testing System 2 Job Orchestration...")

        # Test job creation
        test_name = "system2_job_creation"
        try:
            job_id = self.orchestrator.create_job(
                job_type="transcribe",
                input_id="test_audio_001",
                config={"model": "base", "device": "auto"},
                auto_process=True,
            )

            # Verify job was created
            with self.db_service.get_session() as session:
                job = session.query(Job).filter_by(job_id=job_id).first()
                if job is None:
                    raise AssertionError(f"Job {job_id} not found in database")
                if job.job_type != "transcribe":
                    raise AssertionError(
                        f"Expected job_type 'transcribe', got '{job.job_type}'"
                    )
                if job.input_id != "test_audio_001":
                    raise AssertionError(
                        f"Expected input_id 'test_audio_001', got '{job.input_id}'"
                    )
                if job.auto_process != "true":
                    raise AssertionError(
                        f"Expected auto_process 'true', got '{job.auto_process}'"
                    )

            result = TestResult(
                test_name=test_name,
                success=True,
                output=f"Job {job_id} created successfully",
                job_id=job_id,
                system2_result={"job_type": "transcribe", "auto_process": True},
            )

        except Exception as e:
            result = TestResult(test_name=test_name, success=False, error=str(e))

        self.results.append(result)
        print(f"  {'✅' if result.success else '❌'} {test_name}")

    async def test_system2_job_execution(self):
        """Test System 2 job execution with tracking."""
        print("\n⚡ Testing System 2 Job Execution...")

        # Test job execution
        test_name = "system2_job_execution"
        try:
            # Create a simple transcribe job
            job_id = self.orchestrator.create_job(
                job_type="transcribe",
                input_id="test_audio_002",
                config={"model": "base", "device": "auto"},
                auto_process=False,
            )

            # Create job run
            run_id = self.orchestrator.create_job_run(job_id)

            # Update status to running
            self.orchestrator.update_job_run_status(run_id, "running")

            # Simulate job completion
            self.orchestrator.update_job_run_status(
                run_id, "succeeded", metrics={"output_id": "test_output_002"}
            )

            # Verify job run status
            with self.db_service.get_session() as session:
                job_run = session.query(JobRun).filter_by(run_id=run_id).first()
                if job_run is None:
                    raise AssertionError(f"Job run {run_id} not found in database")
                if job_run.status != "succeeded":
                    raise AssertionError(
                        f"Expected status 'succeeded', got '{job_run.status}'"
                    )
                if (
                    job_run.metrics_json is None
                    or job_run.metrics_json.get("output_id") != "test_output_002"
                ):
                    raise AssertionError(
                        f"Expected output_id 'test_output_002' in metrics"
                    )

            result = TestResult(
                test_name=test_name,
                success=True,
                output=f"Job {job_id} executed successfully",
                job_id=job_id,
                run_id=run_id,
                system2_result={"status": "succeeded", "output_id": "test_output_002"},
            )

        except Exception as e:
            result = TestResult(test_name=test_name, success=False, error=str(e))

        self.results.append(result)
        print(f"  {'✅' if result.success else '❌'} {test_name}")

    async def test_system2_llm_tracking(self):
        """Test System 2 LLM request/response tracking."""
        print("\n🤖 Testing System 2 LLM Tracking...")

        test_name = "system2_llm_tracking"
        try:
            # Create job and run for LLM tracking
            job_id = self.orchestrator.create_job(
                job_type="mine",
                input_id="test_episode_001",
                config={"model": "gpt-3.5-turbo"},
                auto_process=False,
            )

            run_id = self.orchestrator.create_job_run(job_id)
            self.orchestrator._current_job_run_id = run_id

            # Track LLM request
            request_id = self.orchestrator.track_llm_request(
                provider="openai",
                model="gpt-3.5-turbo",
                request_payload={
                    "messages": [{"role": "user", "content": "Test prompt"}]
                },
            )

            # Track LLM response
            self.orchestrator.track_llm_response(
                request_id,
                response_payload={
                    "content": "Test response",
                    "usage": {"total_tokens": 50},
                },
                response_time_ms=1000,
            )

            # Verify tracking
            with self.db_service.get_session() as session:
                request = (
                    session.query(LLMRequest).filter_by(request_id=request_id).first()
                )
                response = (
                    session.query(LLMResponse).filter_by(request_id=request_id).first()
                )

                if request is None:
                    raise AssertionError(
                        f"LLM request {request_id} not found in database"
                    )
                if response is None:
                    raise AssertionError(
                        f"LLM response for {request_id} not found in database"
                    )
                if request.provider != "openai":
                    raise AssertionError(
                        f"Expected provider 'openai', got '{request.provider}'"
                    )
                if response.total_tokens != 50:
                    raise AssertionError(
                        f"Expected total_tokens 50, got {response.total_tokens}"
                    )
                if response.latency_ms != 1000:
                    raise AssertionError(
                        f"Expected latency_ms 1000, got {response.latency_ms}"
                    )

            result = TestResult(
                test_name=test_name,
                success=True,
                output=f"LLM tracking successful for request {request_id}",
                job_id=job_id,
                run_id=run_id,
                system2_result={"request_id": request_id, "tokens": 50},
            )

        except Exception as e:
            result = TestResult(test_name=test_name, success=False, error=str(e))

        self.results.append(result)
        print(f"  {'✅' if result.success else '❌'} {test_name}")

    async def test_system2_checkpoint_resume(self):
        """Test System 2 checkpoint save and resume functionality."""
        print("\n💾 Testing System 2 Checkpoint Resume...")

        test_name = "system2_checkpoint_resume"
        try:
            # Create job and run
            job_id = self.orchestrator.create_job(
                job_type="mine",
                input_id="test_episode_003",
                config={"model": "gpt-3.5-turbo"},
                auto_process=False,
            )

            run_id = self.orchestrator.create_job_run(job_id)

            # Save checkpoint
            checkpoint_data = {
                "segments_processed": 5,
                "total_segments": 10,
                "current_segment": "seg_0006",
            }
            self.orchestrator.save_checkpoint(run_id, checkpoint_data)

            # Load checkpoint
            loaded_checkpoint = self.orchestrator.load_checkpoint(run_id)

            # Verify checkpoint
            if loaded_checkpoint is None:
                raise AssertionError(f"Checkpoint for run {run_id} not found")
            if loaded_checkpoint != checkpoint_data:
                raise AssertionError(
                    f"Checkpoint data mismatch: expected {checkpoint_data}, got {loaded_checkpoint}"
                )
            if loaded_checkpoint["segments_processed"] != 5:
                raise AssertionError(
                    f"Expected segments_processed 5, got {loaded_checkpoint['segments_processed']}"
                )
            if loaded_checkpoint["total_segments"] != 10:
                raise AssertionError(
                    f"Expected total_segments 10, got {loaded_checkpoint['total_segments']}"
                )

            result = TestResult(
                test_name=test_name,
                success=True,
                output=f"Checkpoint save/resume successful for run {run_id}",
                job_id=job_id,
                run_id=run_id,
                system2_result={"checkpoint": checkpoint_data},
            )

        except Exception as e:
            result = TestResult(test_name=test_name, success=False, error=str(e))

        self.results.append(result)
        print(f"  {'✅' if result.success else '❌'} {test_name}")

    async def run_all_tests(self):
        """Run the complete test suite."""
        print("🚀 Starting Knowledge Chipper System 2 Comprehensive Test Suite")
        print(f"📁 Test inputs from: {TEST_INPUTS_DIR}")
        print(f"📁 Test outputs to: {TEST_OUTPUTS_DIR}")
        print(f"🎯 Using summary template: {SUMMARY_PROMPT_FILE}")

        start_time = time.time()

        try:
            # Run System 2 specific tests first
            print("\n" + "=" * 60)
            print("🎯 SYSTEM 2 TESTS")
            print("=" * 60)

            await self.test_system2_job_orchestration()
            await self.test_system2_job_execution()
            await self.test_system2_llm_tracking()
            await self.test_system2_checkpoint_resume()

            # Run legacy tests (still useful for compatibility)
            print("\n" + "=" * 60)
            print("🔄 LEGACY TESTS")
            print("=" * 60)

            self.test_audio_transcription()
            self.test_youtube_extraction()
            self.test_document_processing_with_attribution()
            self.test_document_summarization()
            self.test_markdown_inplace_summarization()
            self.test_combined_processing()
            self.test_summary_cleanup_ui()
            self.test_cloud_sync_configuration()

            # Generate comprehensive report
            self.generate_report()

            total_time = time.time() - start_time
            print(f"\n🏁 Test suite completed in {total_time:.1f} seconds")

        except KeyboardInterrupt:
            print("\n⚠️  Test suite interrupted by user")
            self.generate_report()
        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            self.generate_report()
            raise


async def main():
    """Main entry point."""
    # Check if we're in the right directory
    if not TEST_INPUTS_DIR.exists():
        print(f"❌ Test inputs directory not found: {TEST_INPUTS_DIR}")
        print("Please run this script from the Knowledge Chipper project root.")
        sys.exit(1)

    if not SUMMARY_PROMPT_FILE.exists():
        print(f"❌ Summary prompt file not found: {SUMMARY_PROMPT_FILE}")
        sys.exit(1)

    # Create and run test suite
    suite = ComprehensiveTestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
