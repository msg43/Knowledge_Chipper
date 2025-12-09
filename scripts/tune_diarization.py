#!/usr/bin/env python3
"""
Tune pyannote hyperparameters on a small labeled dev set.

Based on Hervé Bredin's "How I won 2022 diarization challenges":
https://herve.niderb.fr/posts/2022-12-02-how-I-won-2022-diarization-challenges.html

Usage:
    python scripts/tune_diarization.py --dev-dir /path/to/labeled/episodes --hf-token YOUR_TOKEN

Expected directory structure:
    dev-dir/
        episode1.wav
        episode1.rttm  # Reference diarization in RTTM format
        episode2.wav
        episode2.rttm
        ...

The RTTM (Rich Transcription Time Marked) format:
    SPEAKER <file_id> 1 <start_time> <duration> <NA> <NA> <speaker_id> <NA> <NA>
    
Example RTTM line:
    SPEAKER episode1 1 0.500 4.200 <NA> <NA> SPEAKER_00 <NA> <NA>

To create RTTM files manually:
    1. Transcribe with your current pipeline
    2. Manually correct speaker labels for a few episodes
    3. Export as RTTM format

This script performs grid search over:
    - clustering.threshold: [0.60, 0.65, 0.70, 0.75, 0.80]
    - clustering.min_cluster_size: [8, 12, 16]
    - segmentation.min_duration_off: [0.0, 0.1, 0.2]

And reports the DER (Diarization Error Rate) for each configuration.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are available."""
    missing = []
    
    try:
        import torch  # noqa: F401
    except ImportError:
        missing.append("torch")
    
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        missing.append("pyannote.audio")
    
    try:
        import pyannote.metrics  # noqa: F401
    except ImportError:
        missing.append("pyannote.metrics")
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install -e '.[diarization]'")
        sys.exit(1)


def load_rttm(rttm_path: Path) -> "pyannote.core.Annotation":
    """Load RTTM file and convert to pyannote Annotation."""
    from pyannote.core import Annotation, Segment
    
    annotation = Annotation()
    
    with open(rttm_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8 and parts[0] == "SPEAKER":
                start = float(parts[3])
                duration = float(parts[4])
                speaker = parts[7]
                
                segment = Segment(start, start + duration)
                annotation[segment] = speaker
    
    return annotation


def evaluate_on_dev_set(pipeline, dev_files: list[Path], der_metric) -> float:
    """Evaluate pipeline on dev set and return average DER."""
    import torchaudio
    
    total_der = 0.0
    count = 0
    
    for audio_file in dev_files:
        rttm_file = audio_file.with_suffix(".rttm")
        if not rttm_file.exists():
            print(f"  Skipping {audio_file.name} - no RTTM file")
            continue
        
        # Load reference
        reference = load_rttm(rttm_file)
        
        # Run pipeline
        try:
            # Load audio with torchaudio (avoids torchcodec issues)
            waveform, sample_rate = torchaudio.load(str(audio_file))
            audio_input = {"waveform": waveform, "sample_rate": sample_rate}
            hypothesis = pipeline(audio_input)
            
            # Calculate DER
            der = der_metric(reference, hypothesis)
            total_der += der
            count += 1
            
            print(f"  {audio_file.name}: DER={der:.2%}")
            
        except Exception as e:
            print(f"  Error processing {audio_file.name}: {e}")
            continue
    
    return total_der / count if count > 0 else float("inf")


def tune_parameters(dev_dir: Path, hf_token: str, output_file: Path | None = None):
    """Run grid search over pyannote hyperparameters."""
    from pyannote.audio import Pipeline
    from pyannote.metrics.diarization import DiarizationErrorRate
    
    print(f"Loading pyannote pipeline with HuggingFace token...")
    
    # Load dev files
    dev_files = sorted(dev_dir.glob("*.wav"))
    if not dev_files:
        print(f"No .wav files found in {dev_dir}")
        sys.exit(1)
    
    print(f"Found {len(dev_files)} audio files in dev set")
    
    # Initialize pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    
    # Initialize metric
    der = DiarizationErrorRate()
    
    # Grid search parameters (Bredin's recommended ranges)
    thresholds = [0.60, 0.65, 0.70, 0.75, 0.80]
    min_cluster_sizes = [8, 12, 16]
    min_duration_offs = [0.0, 0.1, 0.2]
    
    best_params = None
    best_der = float("inf")
    results = []
    
    total_configs = len(thresholds) * len(min_cluster_sizes) * len(min_duration_offs)
    config_num = 0
    
    print(f"\nStarting grid search over {total_configs} configurations...\n")
    
    for threshold in thresholds:
        for min_cluster_size in min_cluster_sizes:
            for min_duration_off in min_duration_offs:
                config_num += 1
                
                params = {
                    "clustering": {
                        "method": "centroid",
                        "threshold": threshold,
                        "min_cluster_size": min_cluster_size,
                    },
                    "segmentation": {
                        "min_duration_off": min_duration_off,
                    },
                }
                
                print(f"[{config_num}/{total_configs}] Testing: "
                      f"threshold={threshold}, "
                      f"min_cluster_size={min_cluster_size}, "
                      f"min_duration_off={min_duration_off}")
                
                # Apply parameters
                pipeline.instantiate(params)
                
                # Evaluate
                avg_der = evaluate_on_dev_set(pipeline, dev_files, der)
                
                result = {
                    "threshold": threshold,
                    "min_cluster_size": min_cluster_size,
                    "min_duration_off": min_duration_off,
                    "der": avg_der,
                }
                results.append(result)
                
                print(f"  → Average DER: {avg_der:.2%}\n")
                
                if avg_der < best_der:
                    best_der = avg_der
                    best_params = params
    
    # Sort results by DER
    results.sort(key=lambda x: x["der"])
    
    print("\n" + "=" * 60)
    print("RESULTS (sorted by DER)")
    print("=" * 60)
    
    for i, result in enumerate(results[:10]):  # Top 10
        marker = "★" if i == 0 else " "
        print(f"{marker} DER={result['der']:.2%} | "
              f"threshold={result['threshold']}, "
              f"min_cluster={result['min_cluster_size']}, "
              f"min_off={result['min_duration_off']}")
    
    print("\n" + "=" * 60)
    print("BEST CONFIGURATION")
    print("=" * 60)
    print(f"DER: {best_der:.2%}")
    print(f"Parameters: {json.dumps(best_params, indent=2)}")
    
    # Save results if output file specified
    if output_file:
        output = {
            "best_params": best_params,
            "best_der": best_der,
            "all_results": results,
            "dev_set_size": len(dev_files),
        }
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    # Print YAML snippet for settings.yaml
    print("\n" + "=" * 60)
    print("YAML SNIPPET for config/settings.yaml")
    print("=" * 60)
    print(f"""
speaker_identification:
  diarization_sensitivity: "bredin"
  clustering_threshold: {best_params['clustering']['threshold']}
  min_cluster_size: {best_params['clustering']['min_cluster_size']}
  min_duration_off: {best_params['segmentation']['min_duration_off']}
""")
    
    return best_params, best_der


def main():
    parser = argparse.ArgumentParser(
        description="Tune pyannote diarization hyperparameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dev-dir",
        type=Path,
        required=True,
        help="Directory containing .wav and .rttm files for evaluation"
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=os.environ.get("HF_TOKEN"),
        help="HuggingFace access token (or set HF_TOKEN env var)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file for results"
    )
    
    args = parser.parse_args()
    
    if not args.hf_token:
        print("Error: HuggingFace token required. Set --hf-token or HF_TOKEN env var")
        print("Get your token at: https://huggingface.co/settings/tokens")
        sys.exit(1)
    
    if not args.dev_dir.exists():
        print(f"Error: Dev directory not found: {args.dev_dir}")
        sys.exit(1)
    
    # Check dependencies
    check_dependencies()
    
    # Run tuning
    tune_parameters(args.dev_dir, args.hf_token, args.output)


if __name__ == "__main__":
    main()
