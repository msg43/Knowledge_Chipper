"""
Voice Fingerprinting Accuracy Testing Framework

Comprehensive testing system to validate speaker verification accuracy,
calculate performance metrics (FAR, FRR, EER), and benchmark against
standard datasets.
"""

import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import roc_curve

from ..logger import get_logger
from .speaker_verification_service import SpeakerVerificationService
from .voice_fingerprinting import (
    VoiceFingerprintProcessor,
    load_audio_for_voice_processing,
)

logger = get_logger(__name__)


class VoiceAccuracyTester:
    """Framework for testing voice fingerprinting accuracy and performance metrics."""

    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self.voice_processor = VoiceFingerprintProcessor()
        self.verification_service = SpeakerVerificationService(confidence_threshold)
        self.test_results = []

    def test_feature_extraction_consistency(
        self, audio_file: Path, num_runs: int = 5
    ) -> dict[str, Any]:
        """
        Test consistency of feature extraction across multiple runs.

        Args:
            audio_file: Path to test audio file
            num_runs: Number of extraction runs to perform

        Returns:
            Dictionary containing consistency metrics
        """
        logger.info(f"Testing feature extraction consistency with {num_runs} runs")

        try:
            # Load audio once
            audio = load_audio_for_voice_processing(audio_file)

            # Extract features multiple times
            fingerprints = []
            extraction_times = []

            for run in range(num_runs):
                start_time = time.time()
                fingerprint = self.voice_processor.extract_voice_fingerprint(audio)
                extraction_time = time.time() - start_time

                fingerprints.append(fingerprint)
                extraction_times.append(extraction_time)
                logger.debug(f"Run {run+1}: {extraction_time:.3f}s")

            # Calculate consistency metrics
            consistency_results = {
                "num_runs": num_runs,
                "avg_extraction_time": np.mean(extraction_times),
                "std_extraction_time": np.std(extraction_times),
                "feature_consistency": {},
            }

            # Check consistency for each feature type
            for feature_type in ["mfcc", "spectral", "prosodic", "wav2vec2", "ecapa"]:
                if feature_type in fingerprints[0] and fingerprints[0][feature_type]:
                    feature_vectors = []
                    for fp in fingerprints:
                        if feature_type in fp and fp[feature_type]:
                            feature_vectors.append(np.array(fp[feature_type]))

                    if len(feature_vectors) == num_runs:
                        # Calculate standard deviation across runs
                        feature_matrix = np.stack(feature_vectors)
                        consistency_score = 1.0 - np.mean(
                            np.std(feature_matrix, axis=0)
                        )
                        consistency_results["feature_consistency"][feature_type] = {
                            "consistency_score": float(consistency_score),
                            "mean_std": float(np.mean(np.std(feature_matrix, axis=0))),
                            "available": True,
                        }
                    else:
                        consistency_results["feature_consistency"][feature_type] = {
                            "available": False,
                            "reason": "inconsistent_extraction",
                        }
                else:
                    consistency_results["feature_consistency"][feature_type] = {
                        "available": False,
                        "reason": "feature_not_extracted",
                    }

            logger.info(f"Feature extraction consistency test completed")
            return consistency_results

        except Exception as e:
            logger.error(f"Error in consistency test: {e}")
            return {"error": str(e)}

    def test_similarity_calculation(
        self, audio_file1: Path, audio_file2: Path
    ) -> dict[str, Any]:
        """
        Test similarity calculation between two audio files.

        Args:
            audio_file1: First audio file
            audio_file2: Second audio file

        Returns:
            Dictionary containing similarity metrics
        """
        logger.info(
            f"Testing similarity calculation between {audio_file1.name} and {audio_file2.name}"
        )

        try:
            # Load and process both audio files
            audio1 = load_audio_for_voice_processing(audio_file1)
            audio2 = load_audio_for_voice_processing(audio_file2)

            fingerprint1 = self.voice_processor.extract_voice_fingerprint(audio1)
            fingerprint2 = self.voice_processor.extract_voice_fingerprint(audio2)

            # Calculate overall similarity
            similarity = self.voice_processor.calculate_voice_similarity(
                fingerprint1, fingerprint2
            )

            # Calculate feature-specific similarities
            feature_similarities = {}
            for feature_type in ["mfcc", "spectral", "prosodic", "wav2vec2", "ecapa"]:
                if (
                    feature_type in fingerprint1
                    and feature_type in fingerprint2
                    and fingerprint1[feature_type]
                    and fingerprint2[feature_type]
                ):
                    try:
                        from scipy.spatial.distance import cosine

                        vec1 = np.array(fingerprint1[feature_type])
                        vec2 = np.array(fingerprint2[feature_type])

                        if vec1.shape == vec2.shape:
                            feature_sim = 1 - cosine(vec1, vec2)
                            feature_similarities[feature_type] = float(feature_sim)
                    except Exception as e:
                        feature_similarities[feature_type] = f"error: {e}"
                else:
                    feature_similarities[feature_type] = "unavailable"

            results = {
                "overall_similarity": float(similarity),
                "feature_similarities": feature_similarities,
                "file1": str(audio_file1),
                "file2": str(audio_file2),
                "duration1": len(audio1) / 16000,
                "duration2": len(audio2) / 16000,
            }

            logger.info(f"Similarity calculation completed: {similarity:.3f}")
            return results

        except Exception as e:
            logger.error(f"Error in similarity test: {e}")
            return {"error": str(e)}

    def test_speaker_verification_accuracy(
        self, test_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Test speaker verification accuracy using labeled test data.

        Args:
            test_data: List of test cases with format:
                [
                    {
                        "enrollment_audio": "path/to/enroll.wav",
                        "test_audio": "path/to/test.wav",
                        "speaker_name": "John Doe",
                        "is_same_speaker": True/False,
                        "test_segments": [{"start": 0, "end": 10}] (optional)
                    },
                    ...
                ]

        Returns:
            Dictionary containing accuracy metrics
        """
        logger.info(
            f"Testing speaker verification accuracy with {len(test_data)} test cases"
        )

        true_positives = 0
        true_negatives = 0
        false_positives = 0
        false_negatives = 0

        verification_scores = []
        true_labels = []

        detailed_results = []

        for i, test_case in enumerate(test_data):
            try:
                logger.info(f"Processing test case {i+1}/{len(test_data)}")

                speaker_name = test_case["speaker_name"]
                enrollment_audio = Path(test_case["enrollment_audio"])
                test_audio = Path(test_case["test_audio"])
                is_same_speaker = test_case["is_same_speaker"]

                # Enroll speaker
                enrollment_success = self.verification_service.enroll_speaker_from_file(
                    speaker_name, enrollment_audio
                )

                if not enrollment_success:
                    logger.warning(f"Failed to enroll speaker for test case {i+1}")
                    continue

                # Prepare test segments
                test_segments = test_case.get("test_segments")
                if not test_segments:
                    # Use entire audio as one segment
                    audio = load_audio_for_voice_processing(test_audio)
                    duration = len(audio) / 16000
                    test_segments = [{"start": 0, "end": duration}]

                # Verify speaker
                (
                    is_match,
                    confidence,
                    details,
                ) = self.verification_service.verify_speaker_from_segments(
                    speaker_name, test_segments, test_audio
                )

                # Record results
                verification_scores.append(confidence)
                true_labels.append(1 if is_same_speaker else 0)

                # Count outcomes
                if is_same_speaker and is_match:
                    true_positives += 1
                elif is_same_speaker and not is_match:
                    false_negatives += 1
                elif not is_same_speaker and is_match:
                    false_positives += 1
                elif not is_same_speaker and not is_match:
                    true_negatives += 1

                detailed_results.append(
                    {
                        "test_case": i + 1,
                        "speaker_name": speaker_name,
                        "is_same_speaker": is_same_speaker,
                        "predicted_match": is_match,
                        "confidence": confidence,
                        "correct": (is_same_speaker == is_match),
                    }
                )

                logger.debug(
                    f"Test case {i+1}: Expected={is_same_speaker}, Got={is_match}, Confidence={confidence:.3f}"
                )

            except Exception as e:
                logger.error(f"Error in test case {i+1}: {e}")
                continue

        # Calculate metrics
        total_tests = (
            true_positives + true_negatives + false_positives + false_negatives
        )

        if total_tests == 0:
            return {"error": "No valid test cases processed"}

        accuracy = (true_positives + true_negatives) / total_tests

        # False Acceptance Rate (FAR) - false positives / total negatives
        total_negatives = true_negatives + false_positives
        far = false_positives / total_negatives if total_negatives > 0 else 0

        # False Rejection Rate (FRR) - false negatives / total positives
        total_positives = true_positives + false_negatives
        frr = false_negatives / total_positives if total_positives > 0 else 0

        # Calculate EER (Equal Error Rate) using ROC curve
        eer = self._calculate_eer(verification_scores, true_labels)

        results = {
            "accuracy": accuracy,
            "false_acceptance_rate": far,
            "false_rejection_rate": frr,
            "equal_error_rate": eer,
            "true_positives": true_positives,
            "true_negatives": true_negatives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "total_tests": total_tests,
            "confidence_threshold": self.confidence_threshold,
            "detailed_results": detailed_results,
        }

        logger.info(f"Verification accuracy test completed:")
        logger.info(f"  Accuracy: {accuracy:.3f} ({accuracy*100:.1f}%)")
        logger.info(f"  FAR: {far:.3f}")
        logger.info(f"  FRR: {frr:.3f}")
        logger.info(f"  EER: {eer:.3f}")

        return results

    def _calculate_eer(self, scores: list[float], labels: list[int]) -> float:
        """Calculate Equal Error Rate from verification scores and labels."""
        try:
            # Convert to numpy arrays
            scores = np.array(scores)
            labels = np.array(labels)

            # Calculate ROC curve
            fpr, tpr, thresholds = roc_curve(labels, scores)

            # Calculate FRR (1 - TPR)
            frr = 1 - tpr

            # Find threshold where FAR = FRR
            eer_idx = np.argmin(np.abs(fpr - frr))
            eer = (fpr[eer_idx] + frr[eer_idx]) / 2

            return float(eer)

        except Exception as e:
            logger.warning(f"Could not calculate EER: {e}")
            return 0.0

    def benchmark_performance(
        self, audio_files: list[Path], segment_lengths: list[float] = [5, 10, 15, 30]
    ) -> dict[str, Any]:
        """
        Benchmark processing performance with different audio lengths.

        Args:
            audio_files: List of audio files for testing
            segment_lengths: List of segment lengths to test (in seconds)

        Returns:
            Dictionary containing performance benchmarks
        """
        logger.info(
            f"Benchmarking performance with {len(audio_files)} files and {len(segment_lengths)} segment lengths"
        )

        benchmark_results = {
            "test_files": len(audio_files),
            "segment_lengths": segment_lengths,
            "results": {},
        }

        for segment_length in segment_lengths:
            logger.info(f"Testing {segment_length}s segments...")

            processing_times = []
            feature_counts = []

            for audio_file in audio_files:
                try:
                    # Load and segment audio
                    audio = load_audio_for_voice_processing(audio_file)

                    # Extract segment
                    segment_samples = int(segment_length * 16000)
                    if len(audio) >= segment_samples:
                        audio_segment = audio[:segment_samples]
                    else:
                        continue  # Skip if audio too short

                    # Measure processing time
                    start_time = time.time()
                    fingerprint = self.voice_processor.extract_voice_fingerprint(
                        audio_segment
                    )
                    processing_time = time.time() - start_time

                    processing_times.append(processing_time)

                    # Count available features
                    available_features = sum(
                        1 for k, v in fingerprint.items() if isinstance(v, list) and v
                    )
                    feature_counts.append(available_features)

                except Exception as e:
                    logger.warning(f"Error processing {audio_file}: {e}")
                    continue

            if processing_times:
                benchmark_results["results"][f"{segment_length}s"] = {
                    "avg_processing_time": np.mean(processing_times),
                    "std_processing_time": np.std(processing_times),
                    "min_processing_time": np.min(processing_times),
                    "max_processing_time": np.max(processing_times),
                    "avg_features_extracted": np.mean(feature_counts),
                    "files_processed": len(processing_times),
                }

        logger.info("Performance benchmarking completed")
        return benchmark_results

    def generate_test_report(self, output_file: Path = None) -> dict[str, Any]:
        """
        Generate a comprehensive test report combining all test results.

        Args:
            output_file: Optional path to save the report

        Returns:
            Complete test report dictionary
        """
        report = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "confidence_threshold": self.confidence_threshold,
            "system_info": {
                "voice_processor_available": self.voice_processor is not None,
                "verification_service_available": self.verification_service is not None,
            },
            "test_results": self.test_results,
        }

        if output_file:
            try:
                with open(output_file, "w") as f:
                    json.dump(report, f, indent=2, default=str)
                logger.info(f"Test report saved to {output_file}")
            except Exception as e:
                logger.error(f"Error saving test report: {e}")

        return report


def create_sample_test_data() -> list[dict[str, Any]]:
    """Create sample test data structure for demonstration."""
    return [
        {
            "enrollment_audio": "speaker1_enroll.wav",
            "test_audio": "speaker1_test.wav",
            "speaker_name": "John Doe",
            "is_same_speaker": True,
            "test_segments": [{"start": 0, "end": 10}],
        },
        {
            "enrollment_audio": "speaker1_enroll.wav",
            "test_audio": "speaker2_test.wav",
            "speaker_name": "John Doe",
            "is_same_speaker": False,
            "test_segments": [{"start": 0, "end": 10}],
        },
        # Add more test cases...
    ]


def run_comprehensive_accuracy_test(
    test_data_dir: Path, confidence_threshold: float = 0.85
) -> dict[str, Any]:
    """
    Run comprehensive accuracy testing on a directory of test data.

    Args:
        test_data_dir: Directory containing test audio files and metadata
        confidence_threshold: Threshold for verification decisions

    Returns:
        Complete test results
    """
    logger.info(f"Running comprehensive accuracy test on {test_data_dir}")

    tester = VoiceAccuracyTester(confidence_threshold)

    # Look for test configuration file
    test_config_file = test_data_dir / "test_config.json"
    if test_config_file.exists():
        with open(test_config_file) as f:
            test_data = json.load(f)
    else:
        logger.warning("No test_config.json found, using sample data")
        test_data = create_sample_test_data()

    # Run all tests
    results = {
        "accuracy_test": tester.test_speaker_verification_accuracy(test_data),
        "performance_benchmark": tester.benchmark_performance(
            list(test_data_dir.glob("*.wav"))
        ),
    }

    # Generate report
    report_file = test_data_dir / f"accuracy_test_report_{int(time.time())}.json"
    tester.test_results = [results]
    full_report = tester.generate_test_report(report_file)

    return full_report
