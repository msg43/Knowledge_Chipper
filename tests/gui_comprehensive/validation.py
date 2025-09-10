"""
Output validation utilities for GUI comprehensive testing.

Provides validation functions for verifying test outputs and measuring
test success criteria.
"""

import json
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add the src directory to the Python path
try:
    from knowledge_system.logger import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)


logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Container for validation results."""

    is_valid: bool
    score: float  # 0.0 to 1.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OutputValidator:
    """
    Validates test outputs against expected criteria.

    Provides various validation methods for different types of outputs
    produced by the Knowledge Chipper processing pipeline.
    """

    def __init__(self, output_directory: Path):
        """
        Initialize the output validator.

        Args:
            output_directory: Directory containing test outputs
        """
        self.output_directory = Path(output_directory)
        self.validation_rules: dict[str, Any] = {}
        self.load_default_rules()

    def load_default_rules(self) -> None:
        """Load default validation rules for different file types."""
        self.validation_rules = {
            "transcript": {
                "min_length": 10,  # Minimum characters
                "required_sections": [],
                "forbidden_content": ["[Error]", "[Failed]"],
                "file_extensions": [".md", ".txt", ".vtt"],
            },
            "summary": {
                "min_length": 50,
                "max_length": 10000,
                "required_sections": ["Summary", "Key Points"],
                "forbidden_content": ["TODO", "FIXME", "[Error]"],
                "file_extensions": [".md", ".txt"],
            },
            "moc": {
                "min_length": 100,
                "required_sections": ["People", "Jargon", "Mental Models"],
                "forbidden_content": ["[Error]", "[Failed]"],
                "file_extensions": [".md"],
            },
            "audio": {
                "min_size_mb": 0.1,
                "max_size_mb": 1000,
                "file_extensions": [".mp3", ".wav", ".m4a", ".flac"],
            },
            "video": {
                "min_size_mb": 1,
                "max_size_mb": 5000,
                "file_extensions": [".mp4", ".webm", ".avi", ".mov"],
            },
        }

    def validate_file_existence(self, expected_files: list[Path]) -> ValidationResult:
        """
        Validate that expected output files exist.

        Args:
            expected_files: List of expected output file paths

        Returns:
            ValidationResult with existence validation
        """
        errors = []
        warnings = []
        existing_files = 0

        for file_path in expected_files:
            full_path = self.output_directory / file_path
            if full_path.exists():
                existing_files += 1
                logger.debug(f"Found expected file: {file_path}")
            else:
                errors.append(f"Expected file not found: {file_path}")

        score = existing_files / len(expected_files) if expected_files else 0.0
        is_valid = score >= 0.8  # 80% of expected files must exist

        return ValidationResult(
            is_valid=is_valid,
            score=score,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_expected": len(expected_files),
                "total_found": existing_files,
                "missing_files": len(expected_files) - existing_files,
            },
        )

    def validate_transcript_content(self, transcript_file: Path) -> ValidationResult:
        """
        Validate transcript file content quality.

        Args:
            transcript_file: Path to transcript file

        Returns:
            ValidationResult with content validation
        """
        if not transcript_file.exists():
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Transcript file not found: {transcript_file}"],
                warnings=[],
                metadata={},
            )

        try:
            content = transcript_file.read_text(encoding="utf-8")
            return self._validate_text_content(content, "transcript")

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Error reading transcript file: {e}"],
                warnings=[],
                metadata={},
            )

    def validate_summary_content(self, summary_file: Path) -> ValidationResult:
        """
        Validate summary file content quality.

        Args:
            summary_file: Path to summary file

        Returns:
            ValidationResult with content validation
        """
        if not summary_file.exists():
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Summary file not found: {summary_file}"],
                warnings=[],
                metadata={},
            )

        try:
            content = summary_file.read_text(encoding="utf-8")
            return self._validate_text_content(content, "summary")

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Error reading summary file: {e}"],
                warnings=[],
                metadata={},
            )

    def validate_moc_content(self, moc_file: Path) -> ValidationResult:
        """
        Validate Map of Content (MOC) file quality.

        Args:
            moc_file: Path to MOC file

        Returns:
            ValidationResult with MOC validation
        """
        if not moc_file.exists():
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"MOC file not found: {moc_file}"],
                warnings=[],
                metadata={},
            )

        try:
            content = moc_file.read_text(encoding="utf-8")
            return self._validate_text_content(content, "moc")

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Error reading MOC file: {e}"],
                warnings=[],
                metadata={},
            )

    def validate_file_format(
        self, file_path: Path, expected_type: str
    ) -> ValidationResult:
        """
        Validate file format and basic properties.

        Args:
            file_path: Path to file to validate
            expected_type: Expected file type (transcript, summary, moc, audio, video)

        Returns:
            ValidationResult with format validation
        """
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"File not found: {file_path}"],
                warnings=[],
                metadata={},
            )

        errors = []
        warnings = []
        score = 1.0

        # Check file extension
        rules = self.validation_rules.get(expected_type, {})
        expected_extensions = rules.get("file_extensions", [])

        if expected_extensions and file_path.suffix.lower() not in expected_extensions:
            errors.append(
                f"Unexpected file extension: {file_path.suffix}, expected one of {expected_extensions}"
            )
            score -= 0.3

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        min_size = rules.get("min_size_mb", 0)
        max_size = rules.get("max_size_mb", float("inf"))

        if file_size_mb < min_size:
            errors.append(
                f"File too small: {file_size_mb:.2f}MB, minimum: {min_size}MB"
            )
            score -= 0.2
        elif file_size_mb > max_size:
            warnings.append(
                f"File very large: {file_size_mb:.2f}MB, maximum recommended: {max_size}MB"
            )
            score -= 0.1

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))

        metadata = {
            "file_size_mb": file_size_mb,
            "mime_type": mime_type,
            "extension": file_path.suffix.lower(),
        }

        is_valid = score >= 0.7 and not errors

        return ValidationResult(
            is_valid=is_valid,
            score=max(0.0, score),
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def validate_processing_time(
        self,
        start_time: datetime,
        end_time: datetime,
        file_size_mb: float,
        operation_type: str,
    ) -> ValidationResult:
        """
        Validate processing time against expected performance benchmarks.

        Args:
            start_time: Processing start time
            end_time: Processing end time
            file_size_mb: Size of processed file in MB
            operation_type: Type of operation (transcribe, summarize, etc.)

        Returns:
            ValidationResult with performance validation
        """
        duration_seconds = (end_time - start_time).total_seconds()

        # Define performance benchmarks (seconds per MB)
        benchmarks = {
            "transcribe": 30,  # 30 seconds per MB for transcription
            "summarize": 5,  # 5 seconds per MB for summarization
            "moc": 10,  # 10 seconds per MB for MOC generation
            "full_pipeline": 45,  # 45 seconds per MB for full pipeline
        }

        expected_time = benchmarks.get(operation_type, 60) * max(1, file_size_mb)

        errors = []
        warnings = []
        score = 1.0

        if duration_seconds > expected_time * 2:
            errors.append(
                f"Processing too slow: {duration_seconds:.1f}s, expected max: {expected_time * 2:.1f}s"
            )
            score = 0.3
        elif duration_seconds > expected_time * 1.5:
            warnings.append(
                f"Processing slower than expected: {duration_seconds:.1f}s, expected: {expected_time:.1f}s"
            )
            score = 0.7
        elif duration_seconds > expected_time:
            score = 0.9

        metadata = {
            "duration_seconds": duration_seconds,
            "expected_seconds": expected_time,
            "file_size_mb": file_size_mb,
            "operation_type": operation_type,
            "performance_ratio": (
                duration_seconds / expected_time if expected_time > 0 else float("inf")
            ),
        }

        return ValidationResult(
            is_valid=score >= 0.5,
            score=score,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def _validate_text_content(
        self, content: str, content_type: str
    ) -> ValidationResult:
        """
        Validate text content against rules for the specified type.

        Args:
            content: Text content to validate
            content_type: Type of content (transcript, summary, moc)

        Returns:
            ValidationResult with content validation
        """
        rules = self.validation_rules.get(content_type, {})
        errors = []
        warnings = []
        score = 1.0

        # Check minimum length
        min_length = rules.get("min_length", 0)
        if len(content) < min_length:
            errors.append(
                f"Content too short: {len(content)} characters, minimum: {min_length}"
            )
            score -= 0.4

        # Check maximum length
        max_length = rules.get("max_length", float("inf"))
        if len(content) > max_length:
            warnings.append(
                f"Content very long: {len(content)} characters, maximum recommended: {max_length}"
            )
            score -= 0.1

        # Check for required sections
        required_sections = rules.get("required_sections", [])
        missing_sections = []

        for section in required_sections:
            if section.lower() not in content.lower():
                missing_sections.append(section)

        if missing_sections:
            errors.append(f"Missing required sections: {', '.join(missing_sections)}")
            score -= 0.3 * len(missing_sections) / len(required_sections)

        # Check for forbidden content
        forbidden_content = rules.get("forbidden_content", [])
        found_forbidden = []

        for forbidden in forbidden_content:
            if forbidden.lower() in content.lower():
                found_forbidden.append(forbidden)

        if found_forbidden:
            errors.append(f"Found forbidden content: {', '.join(found_forbidden)}")
            score -= 0.2

        # Content quality heuristics
        lines = content.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) < 3:
            warnings.append("Content has very few lines")
            score -= 0.1

        # Check for repeated content (simple heuristic)
        unique_lines = {line.strip().lower() for line in non_empty_lines}
        if len(unique_lines) < len(non_empty_lines) * 0.8:
            warnings.append("Content may have significant repetition")
            score -= 0.1

        metadata = {
            "content_length": len(content),
            "line_count": len(lines),
            "non_empty_lines": len(non_empty_lines),
            "unique_lines": len(unique_lines),
            "required_sections_found": len(required_sections) - len(missing_sections),
            "forbidden_content_found": len(found_forbidden),
        }

        return ValidationResult(
            is_valid=score >= 0.6 and not errors,
            score=max(0.0, score),
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def generate_validation_report(
        self, results: list[ValidationResult], test_name: str
    ) -> dict[str, Any]:
        """
        Generate a comprehensive validation report.

        Args:
            results: List of validation results
            test_name: Name of the test

        Returns:
            Dictionary containing the validation report
        """
        total_results = len(results)
        valid_results = sum(1 for r in results if r.is_valid)
        average_score = (
            sum(r.score for r in results) / total_results if total_results > 0 else 0.0
        )

        all_errors = []
        all_warnings = []

        for result in results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        report = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_validations": total_results,
                "valid_count": valid_results,
                "invalid_count": total_results - valid_results,
                "success_rate": (
                    (valid_results / total_results * 100) if total_results > 0 else 0.0
                ),
                "average_score": average_score,
            },
            "errors": all_errors,
            "warnings": all_warnings,
            "detailed_results": [
                {
                    "is_valid": r.is_valid,
                    "score": r.score,
                    "errors": r.errors,
                    "warnings": r.warnings,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }

        return report

    def save_validation_report(self, report: dict[str, Any], output_file: Path) -> None:
        """
        Save validation report to file.

        Args:
            report: Validation report dictionary
            output_file: Path to save the report
        """
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Validation report saved to: {output_file}")

        except Exception as e:
            logger.error(f"Error saving validation report: {e}")
