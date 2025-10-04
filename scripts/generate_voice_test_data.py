#!/usr/bin/env python3
"""
Generate synthetic test data for voice fingerprinting accuracy testing.

This script creates audio samples and test configurations for validating
the voice fingerprinting system when real speaker data is not available.
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf


def generate_synthetic_voice(
    duration: float,
    fundamental_freq: float,
    sample_rate: int = 16000,
    noise_level: float = 0.01,
) -> np.ndarray:
    """
    Generate synthetic voice-like audio with specified characteristics.

    Args:
        duration: Duration in seconds
        fundamental_freq: Fundamental frequency (pitch) in Hz
        sample_rate: Audio sample rate
        noise_level: Amount of background noise to add

    Returns:
        Audio signal as numpy array
    """
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples)

    # Generate harmonic series (voice-like)
    signal = np.zeros(num_samples)

    # Fundamental frequency and harmonics
    for harmonic in range(1, 8):  # First 7 harmonics
        freq = fundamental_freq * harmonic
        amplitude = 1.0 / harmonic  # Decreasing amplitude for higher harmonics

        # Add some frequency modulation (natural voice variation)
        freq_mod = freq * (1 + 0.02 * np.sin(2 * np.pi * 3 * t))  # 3Hz vibrato

        signal += amplitude * np.sin(2 * np.pi * freq_mod * t)

    # Add formant-like filtering (simple resonance peaks)
    # Simulate vowel-like spectrum
    formant_freqs = [800, 1200, 2500]  # Approximate formant frequencies
    for formant_freq in formant_freqs:
        formant_signal = 0.3 * np.sin(2 * np.pi * formant_freq * t)
        formant_signal *= np.exp(
            -(((np.arange(num_samples) - num_samples // 2) / (num_samples / 4)) ** 2)
        )
        signal += formant_signal

    # Add envelope (speech-like amplitude variation)
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)  # Slow amplitude modulation
    signal *= envelope

    # Add noise
    noise = noise_level * np.random.randn(num_samples)
    signal += noise

    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.8

    return signal.astype(np.float32)


def create_speaker_profile(
    speaker_id: str, base_pitch: float, pitch_variation: float = 10.0
) -> dict[str, Any]:
    """Create a synthetic speaker profile with consistent voice characteristics."""
    return {
        "speaker_id": speaker_id,
        "base_pitch": base_pitch,
        "pitch_range": (base_pitch - pitch_variation, base_pitch + pitch_variation),
        "noise_preference": random.uniform(0.005, 0.02),
        "formant_shift": random.uniform(0.9, 1.1),  # Slight formant frequency variation
    }


def generate_test_dataset(
    output_dir: Path, num_speakers: int = 5, samples_per_speaker: int = 4
) -> dict[str, Any]:
    """
    Generate a complete test dataset with multiple speakers and test cases.

    Args:
        output_dir: Directory to save generated files
        num_speakers: Number of synthetic speakers to create
        samples_per_speaker: Number of audio samples per speaker

    Returns:
        Test configuration dictionary
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define speaker characteristics
    speaker_profiles = []
    pitch_ranges = {
        "male_low": (85, 120),
        "male_mid": (120, 150),
        "male_high": (150, 180),
        "female_low": (165, 200),
        "female_mid": (200, 255),
        "female_high": (255, 300),
    }

    voice_types = list(pitch_ranges.keys())

    for i in range(num_speakers):
        voice_type = voice_types[i % len(voice_types)]
        pitch_min, pitch_max = pitch_ranges[voice_type]
        base_pitch = random.uniform(pitch_min, pitch_max)

        speaker_profile = create_speaker_profile(f"Speaker{i+1}", base_pitch)
        speaker_profiles.append(speaker_profile)

    # Generate audio files
    test_cases = []

    for speaker_idx, profile in enumerate(speaker_profiles):
        speaker_name = profile["speaker_id"]

        # Generate enrollment audio (longer, clean)
        enrollment_duration = random.uniform(15, 25)  # 15-25 seconds
        enrollment_pitch = profile["base_pitch"]
        enrollment_audio = generate_synthetic_voice(
            enrollment_duration,
            enrollment_pitch,
            noise_level=0.005,  # Very clean for enrollment
        )

        enrollment_file = output_dir / f"{speaker_name}_enroll.wav"
        sf.write(enrollment_file, enrollment_audio, 16000)

        # Generate test samples for same speaker
        for sample_idx in range(samples_per_speaker):
            # Same speaker test (positive case)
            test_duration = random.uniform(8, 15)  # 8-15 seconds
            # Add slight pitch variation to simulate natural variation
            test_pitch = enrollment_pitch + random.uniform(-5, 5)
            test_audio = generate_synthetic_voice(
                test_duration, test_pitch, noise_level=profile["noise_preference"]
            )

            test_file = output_dir / f"{speaker_name}_test_{sample_idx+1}.wav"
            sf.write(test_file, test_audio, 16000)

            # Create positive test case
            test_cases.append(
                {
                    "enrollment_audio": enrollment_file.name,
                    "test_audio": test_file.name,
                    "speaker_name": speaker_name,
                    "is_same_speaker": True,
                    "test_segments": [
                        {"start": 1.0, "end": min(test_duration - 1, 10.0)}
                    ],
                    "notes": f"Same speaker, sample {sample_idx+1}",
                }
            )

        # Generate negative test cases (different speakers)
        for other_idx, other_profile in enumerate(speaker_profiles):
            if other_idx != speaker_idx:
                other_speaker = other_profile["speaker_id"]

                # Use one of the existing test files from the other speaker
                other_test_file = f"{other_speaker}_test_1.wav"

                test_cases.append(
                    {
                        "enrollment_audio": enrollment_file.name,
                        "test_audio": other_test_file,
                        "speaker_name": speaker_name,
                        "is_same_speaker": False,
                        "test_segments": [{"start": 1.0, "end": 8.0}],
                        "notes": f"Different speaker: {speaker_name} vs {other_speaker}",
                    }
                )

                # Only add one negative case per speaker to avoid explosion
                break

    # Add some challenging test cases
    challenging_cases = generate_challenging_test_cases(output_dir, speaker_profiles)
    test_cases.extend(challenging_cases)

    # Save test configuration
    test_config = {
        "dataset_info": {
            "num_speakers": num_speakers,
            "samples_per_speaker": samples_per_speaker,
            "total_test_cases": len(test_cases),
            "sample_rate": 16000,
            "generated_by": "generate_voice_test_data.py",
        },
        "speaker_profiles": [
            {
                "speaker_id": p["speaker_id"],
                "base_pitch": p["base_pitch"],
                "voice_type": "synthetic",
            }
            for p in speaker_profiles
        ],
        "test_cases": test_cases,
    }

    config_file = output_dir / "test_config.json"
    with open(config_file, "w") as f:
        json.dump(test_cases, f, indent=2)  # CLI expects just the test cases

    # Save detailed config separately
    detailed_config_file = output_dir / "dataset_info.json"
    with open(detailed_config_file, "w") as f:
        json.dump(test_config, f, indent=2)

    print(f"✅ Generated test dataset:")
    print(f"   📁 Output directory: {output_dir}")
    print(f"   👥 Speakers: {num_speakers}")
    print(f"   🎵 Audio files: {len(list(output_dir.glob('*.wav')))}")
    print(f"   🧪 Test cases: {len(test_cases)}")
    print(f"   📋 Config file: {config_file}")

    return test_config


def generate_challenging_test_cases(
    output_dir: Path, speaker_profiles: list[dict]
) -> list[dict[str, Any]]:
    """Generate challenging test cases to stress-test the system."""
    challenging_cases = []

    if len(speaker_profiles) >= 2:
        # Similar pitch speakers (hardest to distinguish)
        profile1 = speaker_profiles[0]
        profile2 = speaker_profiles[1]

        # Make them have similar pitch
        similar_pitch = (profile1["base_pitch"] + profile2["base_pitch"]) / 2

        # Generate very similar sounding voices
        similar_audio1 = generate_synthetic_voice(12.0, similar_pitch, noise_level=0.01)
        similar_audio2 = generate_synthetic_voice(
            10.0, similar_pitch + 2, noise_level=0.01  # Just 2Hz difference
        )

        similar_file1 = output_dir / "challenging_similar1.wav"
        similar_file2 = output_dir / "challenging_similar2.wav"

        sf.write(similar_file1, similar_audio1, 16000)
        sf.write(similar_file2, similar_audio2, 16000)

        challenging_cases.append(
            {
                "enrollment_audio": similar_file1.name,
                "test_audio": similar_file2.name,
                "speaker_name": "ChallengingSpeaker",
                "is_same_speaker": False,
                "test_segments": [{"start": 1.0, "end": 8.0}],
                "notes": "Challenging case: very similar pitch",
            }
        )

        # Noisy audio test
        noisy_audio = generate_synthetic_voice(
            10.0, profile1["base_pitch"], noise_level=0.1  # High noise
        )
        noisy_file = output_dir / "challenging_noisy.wav"
        sf.write(noisy_file, noisy_audio, 16000)

        challenging_cases.append(
            {
                "enrollment_audio": f"{profile1['speaker_id']}_enroll.wav",
                "test_audio": noisy_file.name,
                "speaker_name": profile1["speaker_id"],
                "is_same_speaker": True,
                "test_segments": [{"start": 1.0, "end": 8.0}],
                "notes": "Challenging case: high noise level",
            }
        )

    return challenging_cases


def main():
    """Generate test data and run sample accuracy test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate voice fingerprinting test data"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default="./voice_test_data",
        help="Output directory for test data",
    )
    parser.add_argument(
        "--speakers", type=int, default=5, help="Number of synthetic speakers"
    )
    parser.add_argument(
        "--samples", type=int, default=3, help="Number of samples per speaker"
    )
    parser.add_argument(
        "--run-test",
        action="store_true",
        help="Run accuracy test after generating data",
    )

    args = parser.parse_args()

    print("🎙️ Generating synthetic voice test data...")

    try:
        # Generate test dataset
        test_config = generate_test_dataset(
            args.output_dir,
            num_speakers=args.speakers,
            samples_per_speaker=args.samples,
        )

        print(f"\n📊 Dataset Summary:")
        positive_cases = sum(
            1 for case in test_config["test_cases"] if case["is_same_speaker"]
        )
        negative_cases = len(test_config["test_cases"]) - positive_cases
        print(f"   ✅ Positive cases (same speaker): {positive_cases}")
        print(f"   ❌ Negative cases (different speaker): {negative_cases}")

        if args.run_test:
            print(f"\n🧪 Running accuracy test...")
            import subprocess

            result = subprocess.run(
                [
                    "knowledge-system",
                    "voice",
                    "test-accuracy",
                    str(args.output_dir),
                    "--confidence",
                    "0.85",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"❌ Test failed: {result.stderr}")
        else:
            print(f"\n🚀 To run accuracy test:")
            print(f"   knowledge-system voice test-accuracy {args.output_dir}")

    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Install with: pip install soundfile numpy")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
