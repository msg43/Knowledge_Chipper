# Skip the Podcast Desktop - AI Models v1.0

This release contains pre-bundled AI models for Skip the Podcast Desktop, providing fast and reliable offline functionality.

## 📦 Included Models

### 🎤 Whisper Base Model
- **File:** `ggml-base.bin`
- **Size:** 141.1 MB
- **Purpose:** Speech transcription
- **Source:** OpenAI Whisper (ggml format)

### 🎙️ Pyannote Speaker Diarization
- **File:** `N/A`
- **Size:** 0.0 MB
- **Purpose:** Speaker separation and identification
- **Source:** pyannote/speaker-diarization-3.1

### 🗣️ Wav2Vec2 Base Model
- **File:** `wav2vec2-base-960h.tar.gz`
- **Size:** 631.1 MB
- **Purpose:** Voice feature extraction
- **Source:** facebook/wav2vec2-base-960h

### 🎯 ECAPA-TDNN Speaker Model
- **File:** `spkrec-ecapa-voxceleb.tar.gz`
- **Size:** 79.3 MB
- **Purpose:** Speaker recognition and verification
- **Source:** speechbrain/spkrec-ecapa-voxceleb

## 📥 Installation

The Skip the Podcast Desktop app will automatically download these models from this GitHub release on first use. No manual installation required!

## 🔒 Verification

Each model includes SHA256 checksums in `models_manifest.json` for integrity verification.

## 📄 Licensing

All models retain their original licenses:
- Whisper: MIT License
- Pyannote: MIT License  
- Wav2Vec2: CC-BY-NC 4.0
- ECAPA-TDNN: Apache 2.0

Total download size: **851.5 MB**
