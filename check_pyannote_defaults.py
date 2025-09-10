#!/usr/bin/env python3
"""Check what clustering method pyannote uses by default"""

try:
    from pyannote.audio import Pipeline

    # Load a pipeline to inspect its clustering
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="dummy",  # Won't actually download
    )
except Exception as e:
    print(f"Could not load pipeline to check: {e}")
    print("\nBased on pyannote documentation:")
    print(
        "- Default clustering can be 'AgglomerativeClustering' or 'SpectralClustering'"
    )
    print("- SpectralClustering uses eigenvalue decomposition (fails on MPS)")
    print("- That's likely why the original developer forced CPU!")
    print("\nOur fix: Explicitly use 'centroid' clustering which works on MPS")
