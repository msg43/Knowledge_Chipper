#!/usr/bin/env bash
set -euo pipefail

# Simple setup script for GUI comprehensive testing data
# Creates fast, reliable test files without external dependencies

# Determine the correct paths relative to script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURES_DIR="$PROJECT_ROOT/tests/fixtures/sample_files"

# Create directory structure
mkdir -p "${FIXTURES_DIR}/audio" "${FIXTURES_DIR}/video" "${FIXTURES_DIR}/documents"

echo "==> Setting up simple test data for GUI comprehensive testing"
echo "Fixtures directory: $FIXTURES_DIR"

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg is not installed or not in PATH."; exit 1; }

echo "==> Generating synthetic audio files with speech-like characteristics..."

# Generate short speech (30 seconds) - with speech-like frequency modulation
ffmpeg -f lavfi -i "sine=frequency=200+100*sin(2*PI*t/3):duration=30" -filter_complex "
[0:a]volume=0.5,
aformat=sample_fmts=s16:sample_rates=16000:channel_layouts=mono,
aresample=resampler=soxr[out]" -map "[out]" "${FIXTURES_DIR}/audio/short_speech_30s.mp3" -y 2>/dev/null

# Generate medium speech (2 minutes) - with varying tones like speech
ffmpeg -f lavfi -i "sine=frequency=150+200*sin(2*PI*t/2)+50*sin(2*PI*t*5):duration=120" -filter_complex "
[0:a]volume=0.4,
aformat=sample_fmts=s16:sample_rates=16000:channel_layouts=mono,
aresample=resampler=soxr[out]" -map "[out]" "${FIXTURES_DIR}/audio/medium_speech_2min.wav" -y 2>/dev/null

# Generate long speech (5 minutes) - with speech-like patterns
ffmpeg -f lavfi -i "sine=frequency=180+150*sin(2*PI*t/4)+75*sin(2*PI*t*3):duration=300" -filter_complex "
[0:a]volume=0.45,
aformat=sample_fmts=s16:sample_rates=16000:channel_layouts=mono,
aresample=resampler=soxr[out]" -map "[out]" "${FIXTURES_DIR}/audio/long_speech_5min.m4a" -y 2>/dev/null

# Generate interview (3 minutes) - alternating speakers simulation
ffmpeg -f lavfi -i "sine=frequency=200+100*sin(2*PI*t/8):duration=180" -filter_complex "
[0:a]volume=0.4,
aformat=sample_fmts=s16:sample_rates=16000:channel_layouts=mono,
aresample=resampler=soxr[out]" -map "[out]" "${FIXTURES_DIR}/audio/interview_3min.aac" -y 2>/dev/null

# Generate podcast (10 minutes) - with speech-like modulation
ffmpeg -f lavfi -i "sine=frequency=160+120*sin(2*PI*t/6)+60*sin(2*PI*t*2):duration=600" -filter_complex "
[0:a]volume=0.5,
aformat=sample_fmts=s16:sample_rates=22050:channel_layouts=mono,
aresample=resampler=soxr[out]" -map "[out]" "${FIXTURES_DIR}/audio/podcast_10min.ogg" -y 2>/dev/null

# Generate music (3 minutes) - harmonic content
ffmpeg -f lavfi -i "sine=frequency=440:duration=180,sine=frequency=880:duration=180" -filter_complex "
[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3,
aformat=sample_fmts=s16:sample_rates=44100:channel_layouts=stereo[out]" -map "[out]" "${FIXTURES_DIR}/audio/music_3min.flac" -y 2>/dev/null

echo "==> Generating video files with synthetic content..."

# Generate tutorial video (3 minutes) - SHORT for quick testing
ffmpeg -f lavfi -i "testsrc2=size=1280x720:rate=30" -f lavfi -i "sine=frequency=300+100*sin(2*PI*t/2):duration=180" \
-vf "format=yuv420p,drawtext=text='Tutorial Video':x=20:y=40:fontsize=28" \
-shortest -c:v libx264 -preset veryfast -crf 28 -c:a aac -b:a 128k \
"${FIXTURES_DIR}/video/tutorial_3min.mp4" -y 2>/dev/null

# Generate webinar video (10 minutes) - MEDIUM length
ffmpeg -f lavfi -i "color=color=white:size=1920x1080:rate=30" -f lavfi -i "sine=frequency=250+150*sin(2*PI*t/4):duration=600" \
-vf "format=yuv420p,drawtext=text='Webinar %{pts\\:hms}':x=20:y=40:fontsize=28" \
-shortest -c:v libx264 -preset veryfast -crf 26 -c:a aac -b:a 128k \
"${FIXTURES_DIR}/video/webinar_10min.mp4" -y 2>/dev/null

# Generate full lecture (45 minutes) - LONG for stress testing
ffmpeg -f lavfi -i "testsrc=size=1280x720:rate=30" -f lavfi -i "sine=frequency=200+120*sin(2*PI*t/8):duration=2700" \
-vf "format=yuv420p,drawtext=text='Lecture %{pts\\:hms}':x=20:y=h-60:fontsize=24" \
-shortest -c:v libx264 -preset veryfast -crf 27 -c:a aac -b:a 128k \
"${FIXTURES_DIR}/video/full_lecture_45min.mp4" -y 2>/dev/null

# Generate interview video (5 minutes)
ffmpeg -f lavfi -i "color=color=gray:size=1280x720:rate=30" -f lavfi -i "sine=frequency=220+80*sin(2*PI*t/3):duration=300" \
-vf "format=yuv420p,drawtext=text='Interview %{pts\\:hms}':x=20:y=h-60:fontsize=24" \
-shortest -c:v libvpx-vp9 -b:v 1M -c:a libopus -b:a 96k \
"${FIXTURES_DIR}/video/interview_5min.webm" -y 2>/dev/null

# Create AVI format (short for compatibility)
ffmpeg -f lavfi -i "testsrc=size=1024x768:rate=30" -f lavfi -i "sine=frequency=300:duration=180" \
-vf "format=yuv420p,drawtext=text='Presentation':x=20:y=40:fontsize=28" \
-shortest -c:v libxvid -c:a mp3 -b:a 128k \
"${FIXTURES_DIR}/video/presentation_short.avi" -y 2>/dev/null

# Create MKV format (copy from webm)
ffmpeg -i "${FIXTURES_DIR}/video/interview_5min.webm" -c copy "${FIXTURES_DIR}/video/documentary_excerpt.mkv" -y 2>/dev/null

echo "==> Generating document files..."

# Create realistic document content
cat > "${FIXTURES_DIR}/documents/meeting_notes.txt" << 'EOF'
Team Sync - Speech Processing Pipeline
Date: 2024-01-15
Attendees: Sarah Chen, Mike Rodriguez, Anna Kim

Agenda:
1. Review transcription accuracy metrics
2. Speaker diarization improvements
3. Performance optimization
4. Quality assurance protocols

Discussion:
- Current WER at 8.2% for clean audio
- Diarization accuracy improved to 94.3%
- Real-time latency now under 200ms
- Need better noise handling

Action Items:
- Sarah: Implement noise reduction by Jan 30
- Mike: Test new acoustic models
- Anna: Develop edge case testing

Next Meeting: January 22, 2024
EOF

cat > "${FIXTURES_DIR}/documents/technical_spec.md" << 'EOF'
# Streaming ASR Pipeline - Technical Specification

## Overview
Real-time Automatic Speech Recognition pipeline for high-throughput processing.

## Architecture
- Input Layer: Multi-format audio ingestion
- Preprocessing: VAD, noise reduction, normalization
- ASR Engine: Transformer-based neural network
- Post-processing: Grammar correction, punctuation

## Performance Requirements
- Latency: <200ms real-time
- Accuracy: >92% WER clean speech
- Throughput: 100 concurrent streams
- Availability: 99.9% uptime

## API Endpoints
- POST /transcribe - Single file
- WebSocket /stream - Real-time
- GET /status - Health check
EOF

cat > "${FIXTURES_DIR}/documents/research_paper.txt" << 'EOF'
A Study on Robust Speaker Diarization under Realistic Noise Conditions

Abstract
Speaker diarization faces challenges in real-world scenarios with background noise,
overlapping speech, and varying acoustic conditions. This study analyzes state-of-the-art
systems under realistic noise and proposes robustness improvements.

1. Introduction
Speaker diarization determines "who spoke when" in audio recordings. Applications include
meeting transcription, broadcast analysis, and conversational AI.

2. Methodology
We evaluated five diarization systems using:
- AMI Meeting Corpus (clean)
- DIHARD III Challenge (realistic)
- Custom noisy recordings (0-20dB SNR)

Metrics: DER, SCR, FAR, MSR

3. Results
Significant degradation in noisy conditions:
- DER: 12.3% (clean) to 28.7% (10dB SNR)
- Primary issue: speaker confusion
- Proposed clustering improved DER by 15.2%

4. Conclusions
Critical need for noise-robust diarization with practical improvement techniques.
EOF

cat > "${FIXTURES_DIR}/documents/blog_post.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Speech Recognition Latency vs Accuracy</title>
</head>
<body>
    <h1>Latency vs Accuracy Trade-offs in Speech Recognition</h1>
    <p><em>By Dr. Alexandra Martinez - January 15, 2024</em></p>

    <h2>The Challenge</h2>
    <p>Modern applications demand different balance points:</p>
    <ul>
        <li>Live captioning: &lt;200ms latency</li>
        <li>Voice assistants: &lt;100ms</li>
        <li>Conference transcription: 500-1000ms acceptable</li>
    </ul>

    <h2>Optimization Strategies</h2>
    <p>Model architecture choices include streaming vs bidirectional models,
    with hardware considerations for GPU acceleration and edge deployment.</p>

    <h2>Conclusion</h2>
    <p>Optimal balance depends on application requirements and constraints.</p>
</body>
</html>
EOF

# Create a large document for stress testing
cat > "${FIXTURES_DIR}/documents/large_manual.txt" << 'EOF'
Knowledge Chipper User Manual

Table of Contents
1. Introduction
2. Installation
3. Configuration
4. Audio Processing
5. Video Processing
6. Document Processing
7. Advanced Features
8. Troubleshooting
9. API Reference
10. Appendices

Chapter 1: Introduction
Welcome to Knowledge Chipper, a comprehensive tool for processing audio, video,
and document content with advanced AI capabilities.

Chapter 2: Installation
System requirements and installation procedures for various platforms.

Chapter 3: Configuration
Detailed configuration options for optimal performance in your environment.

Chapter 4: Audio Processing
Complete guide to audio transcription, speaker diarization, and quality settings.

Chapter 5: Video Processing
Video file handling, audio extraction, and processing workflows.

Chapter 6: Document Processing
Text extraction, summarization, and knowledge extraction from documents.

Chapter 7: Advanced Features
Custom models, API integration, and enterprise deployment options.

Chapter 8: Troubleshooting
Common issues and solutions for optimal system performance.

Chapter 9: API Reference
Complete API documentation with examples and best practices.

Chapter 10: Appendices
Additional resources, references, and technical specifications.
EOF

echo "==> Creating small test files for quick validation..."

# Create very small files for the fastest possible tests
ffmpeg -f lavfi -i "sine=frequency=400:duration=5" -ar 16000 -ac 1 "${FIXTURES_DIR}/audio/quick_test_5s.mp3" -y 2>/dev/null
ffmpeg -f lavfi -i "testsrc2=size=640x480:rate=30" -f lavfi -i "sine=frequency=400:duration=10" \
-vf "format=yuv420p" -shortest -c:v libx264 -preset ultrafast -crf 30 -c:a aac \
"${FIXTURES_DIR}/video/quick_test_10s.mp4" -y 2>/dev/null

echo "Simple test document content" > "${FIXTURES_DIR}/documents/quick_test.txt"

echo "==> Setup complete!"
echo "Generated simple test files in: $FIXTURES_DIR"
echo ""
echo "File sizes optimized for GUI testing:"
echo "- Quick tests: 5-10 seconds"
echo "- Standard tests: 2-5 minutes"
echo "- Stress tests: 10-45 minutes"
echo ""
echo "Run tests with:"
echo "  cd $PROJECT_ROOT"
echo "  python -m tests.gui_comprehensive.main_test_runner smoke"
