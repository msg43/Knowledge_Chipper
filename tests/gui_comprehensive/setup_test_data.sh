#!/usr/bin/env bash
set -euo pipefail

# Setup script for GUI comprehensive testing data
# Creates all required test files for Knowledge Chipper GUI testing

# Determine the correct paths relative to script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURES_DIR="$PROJECT_ROOT/tests/fixtures/sample_files"
WORK_DIR="${FIXTURES_DIR}/_work"

# Create directory structure
mkdir -p "${FIXTURES_DIR}/audio" "${FIXTURES_DIR}/video" "${FIXTURES_DIR}/documents" "$WORK_DIR"

echo "==> Setting up test data for GUI comprehensive testing"
echo "Fixtures directory: $FIXTURES_DIR"

# Set up Python virtual environment in work directory
PYENV_DIR="${WORK_DIR}/.venv"
echo "==> Setting up Python virtual environment..."
python3 -m venv "$PYENV_DIR"
source "${PYENV_DIR}/bin/activate"
python -m pip install --upgrade pip >/dev/null

echo "==> Installing dependencies..."
pip install --quiet datasets==2.20.0 pydub==0.25.1 numpy==1.26.4 soundfile==0.12.1 tqdm==4.66.4

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg is not installed or not in PATH."; exit 1; }

# Export paths for Python script
export FIXTURES_DIR
export WORK_DIR

python - << 'PY'
import os, math, csv, random, subprocess, wave
from pathlib import Path
from datasets import load_dataset

FIXTURES_DIR = Path(os.environ["FIXTURES_DIR"])
WORK_DIR = Path(os.environ["WORK_DIR"])
AUDIO = FIXTURES_DIR / "audio"
VIDEO = FIXTURES_DIR / "video"
DOCS = FIXTURES_DIR / "documents"

SAMPLE_RATE=16000
def run(args): subprocess.run(args, check=True)
def ffmpeg(*a): run(["ffmpeg","-y","-hide_banner","-loglevel","error",*a])
def materialize(src, dst): ffmpeg("-i", src, "-ar", str(SAMPLE_RATE), "-ac", "1", str(dst))

def concat_with_transcript(items, out_wav, txt, csvp):
    norms=[]; meta=[]
    for path, text in items:
        n=WORK_DIR/f"n_{random.randint(0,1_000_000)}.wav"; materialize(path, n)
        with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate()
        norms.append(n); meta.append((text,d))
    lst=WORK_DIR/f"c_{out_wav.stem}.txt"
    open(lst,"w").write("".join(f"file '{n.as_posix()}'\n" for n in norms))
    ffmpeg("-f","concat","-safe","0","-i",str(lst),"-c","copy",str(out_wav))
    with open(txt,"w",encoding="utf-8") as ft, open(csvp,"w",newline="",encoding="utf-8") as fc:
        w=csv.writer(fc); w.writerow(["start_sec","end_sec","text"]); t=0.0
        for text,d in meta: w.writerow([f"{t:.2f}",f"{t+d:.2f}",text]); ft.write(text.strip()+"\n"); t+=d

print("==> Fetching Common Voice dataset...")
cv = load_dataset("mozilla-foundation/common_voice_13_0","en",split="train",streaming=True)
cv_samples=[]
for ex in cv:
    if ex.get("sentence") and ex.get("path"):
        cv_samples.append((ex["path"], ex["sentence"], ex.get("client_id","spk")))
        if len(cv_samples)>=500: break

print("==> Generating audio files...")

# --- short_speech_30s (multiple formats) ---
picked=[]; tot=0.0
for i,(p, s, sp) in enumerate(cv_samples):
    n=WORK_DIR/f"s_{i}.wav"; materialize(p,n)
    with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate()
    picked.append((str(n), s)); tot+=d
    if tot>=30: break
wav=WORK_DIR/"short_speech_30s.wav"; txt=AUDIO/"short_speech_30s.txt"; csvp=AUDIO/"short_speech_30s_segments.csv"
concat_with_transcript(picked, wav, txt, csvp)

# Generate multiple formats for short speech
ffmpeg("-i",str(wav),"-b:a","96k",str(AUDIO/"short_speech_30s.mp3"))
ffmpeg("-i",str(wav),"-c:a","aac","-b:a","128k",str(AUDIO/"short_speech_30s.aac"))
ffmpeg("-i",str(wav),"-c:a","flac",str(AUDIO/"short_speech_30s.flac"))

# --- conversation_2min.wav ---
by={}; [by.setdefault(sp,[]).append((p,s)) for p,s,sp in cv_samples]
spks=list(by.keys())[:2]
seq=[]; tot=0.0; idx=0
while tot<120 and spks:
    sp=spks[idx%len(spks)]
    if not by[sp]: break
    p,s=by[sp].pop(0); n=WORK_DIR/f"c_{idx}.wav"; materialize(p,n)
    with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate(); tot+=d
    seq.append((str(n), f"[{sp}] {s}")); idx+=1
wav=AUDIO/"conversation_2min.wav"; txt=AUDIO/"conversation_2min.txt"; csvp=AUDIO/"conversation_2min_segments.csv"
concat_with_transcript(seq, wav, txt, csvp)

# --- music_with_speech.m4a ---
seq=[]; tot=0.0
for i,(p,s,sp) in enumerate(cv_samples):
    n=WORK_DIR/f"m_{i}.wav"; materialize(p,n)
    with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate()
    seq.append((str(n), s)); tot+=d
    if tot>=45: break
sp=WORK_DIR/"music_speech.wav"; txt=AUDIO/"music_with_speech.txt"; csvp=AUDIO/"music_with_speech_segments.csv"
concat_with_transcript(seq, sp, txt, csvp)
bed=WORK_DIR/"bed.wav"; ffmpeg("-f","lavfi","-i","sine=frequency=440:sample_rate=44100","-t","60",str(bed))
mix=WORK_DIR/"mix.wav"
ffmpeg("-i",str(bed),"-i",str(sp),"-filter_complex","[0:a]volume=0.2[a0];[1:a]volume=1.0,adelay=500|500[a1];[a0][a1]amix=inputs=2:duration=longest",str(mix))
ffmpeg("-i",str(mix),"-b:a","128k",str(AUDIO/"music_with_speech.m4a"))

# --- Poor quality recording for robustness testing ---
poor_audio = WORK_DIR/"poor_quality_base.wav"
ffmpeg("-i", str(AUDIO/"short_speech_30s.mp3"), "-af", "lowpass=f=3000,highpass=f=300,volume=0.3", str(poor_audio))
ffmpeg("-i", str(poor_audio), "-b:a", "64k", str(AUDIO/"poor_quality_recording.mp3"))

print("==> Fetching LJ Speech dataset...")
lj = load_dataset("lj_speech", split="train")

def build_lj_minutes(minutes, outpath_base):
    need=minutes*60+15; tot=0.0; items=[]
    for ex in lj:
        p=ex["audio"]["path"]; s=ex["text"]; n=WORK_DIR/f"lj_{ex['id']}.wav"; ffmpeg("-i",p,str(n))
        with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate()
        items.append((str(n), s)); tot+=d
        if tot>=need: break
    wav=WORK_DIR/f"{outpath_base}.wav"; txt=AUDIO/f"{outpath_base}.txt"; csv=AUDIO/f"{outpath_base}_segments.csv"
    concat_with_transcript(items, wav, txt, csv)
    return wav

# --- Long-form audio files ---
base=build_lj_minutes(10,"interview_10min")
ffmpeg("-i",str(base),"-t","600","-ar","16000","-ac","1",str(WORK_DIR/"interview_10min.trim.wav"))
ffmpeg("-i",str(WORK_DIR/"interview_10min.trim.wav"),"-compression_level","5",str(AUDIO/"interview_10min.flac"))

base=build_lj_minutes(30,"conference_talk_30min")
ffmpeg("-i",str(base),"-t","1800","-ar","16000","-ac","1",str(AUDIO/"conference_talk_30min.wav"))

# Create audiobook chapter (using long-form LJ speech)
base=build_lj_minutes(45,"audiobook_chapter")
ffmpeg("-i",str(base),"-t","2700","-ar","22050","-ac","1","-b:a","64k",str(AUDIO/"audiobook_chapter.mp3"))

# --- podcast_excerpt.ogg ---
seq=[]; tot=0.0
for i,(p,s,sp) in enumerate(cv_samples):
    n=WORK_DIR/f"p_{i}.wav"; materialize(p,n)
    with wave.open(str(n),"rb") as wf: d=wf.getnframes()/wf.getframerate()
    seq.append((str(n), f"[{sp}] {s}")); tot+=d
    if tot>=600: break
wav=WORK_DIR/"podcast_excerpt.wav"; txt=AUDIO/"podcast_excerpt.txt"; csvp=AUDIO/"podcast_excerpt_segments.csv"
concat_with_transcript(seq, wav, txt, csvp)
ffmpeg("-i",str(wav),"-c:a","libvorbis","-qscale:a","4",str(AUDIO/"podcast_excerpt.ogg"))

# --- Webinar audio (AAC format) ---
webinar_base = WORK_DIR/"webinar_audio.wav"
ffmpeg("-i", str(AUDIO/"interview_10min.flac"), "-t", "900", str(webinar_base))
ffmpeg("-i", str(webinar_base), "-c:a", "aac", "-b:a", "128k", str(AUDIO/"webinar_audio.aac"))

print("==> Generating video files...")

# --- Videos (synthetic visuals, real audio) ---
aud=WORK_DIR/"tutorial_3min.wav"; ffmpeg("-i",str(AUDIO/"short_speech_30s.mp3"),"-ar","16000","-ac","1",str(aud))
ffmpeg("-f","lavfi","-i","testsrc2=size=1280x720:rate=30","-i",str(aud),"-t","180","-vf","format=yuv420p,drawtext=text='tutorial_3min':x=20:y=40:fontsize=28","-shortest","-c:v","libx264","-preset","veryfast","-crf","28","-c:a","aac","-b:a","128k",str(VIDEO/"tutorial_3min.mp4"))

aud=WORK_DIR/"interview_5min.wav"; ffmpeg("-i",str(AUDIO/"conversation_2min.wav"),"-ar","16000","-ac","1",str(aud))
ffmpeg("-f","lavfi","-i","color=color=gray:size=1280x720:rate=30","-i",str(aud),"-t","300","-vf","format=yuv420p,drawtext=text='%{pts\\:hms}':x=20:y=h-60:fontsize=24","-shortest","-c:v","libvpx-vp9","-b:v","1M","-c:a","libopus","-b:a","96k",str(VIDEO/"interview_5min.webm"))

ffmpeg("-f","lavfi","-i","color=color=white:size=1920x1080:rate=30","-i",str(AUDIO/"interview_10min.flac"),"-t","600","-vf","format=yuv420p,drawtext=text='webinar_10min':x=20:y=40:fontsize=28","-shortest","-c:v","libx264","-preset","veryfast","-crf","26","-c:a","aac","-b:a","128k",str(VIDEO/"webinar_10min.mp4"))

aud=WORK_DIR/"conf15.wav"; ffmpeg("-i",str(AUDIO/"conference_talk_30min.wav"),"-t","900","-ar","16000","-ac","1",str(aud))
ffmpeg("-f","lavfi","-i","smptebars=size=1920x1080:rate=30","-i",str(aud),"-t","900","-vf","format=yuv422p10le","-shortest","-c:v","prores_ks","-profile:v","0","-c:a","pcm_s16le",str(VIDEO/"conference_talk_15min.mov"))

aud=WORK_DIR/"lecture45.wav"; ffmpeg("-i",str(AUDIO/"conference_talk_30min.wav"),"-ar","16000","-ac","1",str(aud))
ffmpeg("-f","lavfi","-i","testsrc=size=1280x720:rate=30","-i",str(aud),"-t","2700","-vf","format=yuv420p,drawtext=text='%{pts\\:hms}':x=20:y=h-60:fontsize=24","-shortest","-c:v","libx264","-preset","veryfast","-crf","27","-c:a","aac","-b:a","128k",str(VIDEO/"full_lecture_45min.mp4"))

# --- Additional video formats for comprehensive testing ---

# Create AVI format video (presentation_short.avi)
ffmpeg("-f","lavfi","-i","testsrc=size=1024x768:rate=30","-i",str(AUDIO/"short_speech_30s.mp3"),"-t","180","-vf","format=yuv420p,drawtext=text='Presentation':x=20:y=40:fontsize=28","-shortest","-c:v","libxvid","-c:a","mp3","-b:a","128k",str(VIDEO/"presentation_short.avi"))

# Create MKV format video (documentary_excerpt.mkv)
ffmpeg("-i",str(VIDEO/"interview_5min.webm"),"-c","copy",str(VIDEO/"documentary_excerpt.mkv"))

# Create panel discussion (60min, large file)
aud_panel = WORK_DIR/"panel_60min.wav"
ffmpeg("-i", str(AUDIO/"conference_talk_30min.wav"), "-i", str(AUDIO/"conversation_2min.wav"), "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", "-t", "3600", str(aud_panel))
ffmpeg("-f","lavfi","-i","color=color=blue:size=1920x1080:rate=30","-i",str(aud_panel),"-t","3600","-vf","format=yuv420p,drawtext=text='Panel Discussion':x=20:y=40:fontsize=32","-shortest","-c:v","libx264","-preset","veryfast","-crf","30","-c:a","aac","-b:a","96k",str(VIDEO/"panel_discussion_60min.webm"))

print("==> Generating document files...")

# --- Enhanced document content generation ---

# Meeting notes with realistic content
meeting_content = """Team Sync - ASR Pipeline Development
Date: 2024-01-15
Attendees: Sarah Chen (Lead Engineer), Mike Rodriguez (ML Specialist), Anna Kim (QA)

Agenda:
1. Performance review of current transcription accuracy
2. Integration of new speaker diarization models
3. Latency optimization for real-time processing
4. Quality assurance testing protocols

Discussion Points:
- Current WER (Word Error Rate) is at 8.2% for clean audio
- Need to improve performance on noisy environments
- Diarization accuracy improved to 94.3% after model update
- Real-time processing now achieving <200ms latency

Action Items:
- Sarah: Implement noise reduction preprocessing by Jan 30
- Mike: Test new acoustic models with diverse accents
- Anna: Develop comprehensive testing suite for edge cases

Next Meeting: January 22, 2024
"""

# Technical specification with detailed content
tech_spec_content = """Streaming ASR Pipeline - Technical Specification (v2.1)
========================================================

1. Overview
-----------
This document outlines the technical architecture for a real-time Automatic Speech Recognition (ASR) pipeline designed for high-throughput, low-latency speech processing.

2. System Architecture
----------------------
2.1 Input Layer
- Audio ingestion from multiple sources (microphone, file upload, streaming)
- Support for formats: WAV, MP3, FLAC, OGG, AAC
- Sample rates: 8kHz, 16kHz, 22kHz, 44.1kHz, 48kHz

2.2 Preprocessing Layer
- Voice Activity Detection (VAD)
- Noise reduction using spectral subtraction
- Audio normalization and resampling
- Chunking for real-time processing (25ms windows)

2.3 ASR Engine
- Deep neural network architecture (Transformer-based)
- Context length: 2048 tokens
- Vocabulary size: 50,000 tokens
- Language support: English (primary), Spanish, French

2.4 Post-processing
- Grammar correction using language models
- Punctuation restoration
- Speaker diarization (optional)
- Confidence scoring

3. Performance Requirements
---------------------------
- Latency: <200ms for real-time processing
- Accuracy: >92% WER on clean speech
- Throughput: 100 concurrent streams
- Availability: 99.9% uptime

4. API Specifications
---------------------
REST API endpoints:
- POST /transcribe - Single file transcription
- WebSocket /stream - Real-time streaming
- GET /status - System health check

5. Quality Metrics
------------------
- Word Error Rate (WER)
- Real-Time Factor (RTF)
- Speaker diarization accuracy
- End-to-end latency measurements
"""

# Research paper abstract and content
research_content = """A Study on Robust Speaker Diarization under Realistic Noise Conditions

Abstract
--------
Speaker diarization, the task of determining "who spoke when" in an audio recording, faces significant challenges in real-world scenarios where background noise, overlapping speech, and varying acoustic conditions are prevalent. This study presents a comprehensive analysis of state-of-the-art diarization systems under realistic noise conditions and proposes novel techniques for improving robustness.

1. Introduction
---------------
Speaker diarization has gained considerable attention in recent years due to its applications in meeting transcription, broadcast news analysis, and conversational AI systems. However, most existing research focuses on clean audio conditions that rarely represent real-world scenarios.

2. Methodology
--------------
We evaluated five leading diarization systems using the following datasets:
- AMI Meeting Corpus (clean conditions)
- DIHARD III Challenge data (realistic conditions)
- Custom noisy meeting recordings (SNR: 0-20dB)

Evaluation metrics included:
- Diarization Error Rate (DER)
- Speaker Confusion Rate (SCR)
- False Alarm Rate (FAR)
- Missed Speaker Rate (MSR)

3. Results
----------
Our experiments revealed significant performance degradation in noisy conditions:
- Average DER increased from 12.3% (clean) to 28.7% (10dB SNR)
- Speaker confusion errors were the primary contributor to degradation
- Proposed noise-robust clustering improved DER by 15.2%

4. Conclusions
--------------
This work demonstrates the critical need for noise-robust diarization systems and provides practical techniques for improving performance in challenging acoustic environments.
"""

# Blog post with markdown formatting
blog_content = """# Latency vs Accuracy Trade-offs in Practical Speech Recognition Pipelines

*Published on January 15, 2024 by Dr. Alexandra Martinez*

## Introduction

In the rapidly evolving field of speech recognition, engineers and researchers constantly face the fundamental trade-off between system latency and transcription accuracy. This blog post explores practical strategies for optimizing this balance in production environments.

## The Latency Challenge

Modern applications demand near-real-time speech processing:

- **Live captioning** requires <200ms latency
- **Voice assistants** need <100ms for natural interaction
- **Conference transcription** can tolerate 500-1000ms delays

## Accuracy Requirements

Different use cases have varying accuracy thresholds:

1. **Mission-critical applications**: 98%+ accuracy required
2. **General transcription**: 92-95% typically acceptable
3. **Draft generation**: 85-90% may suffice for rapid editing

## Optimization Strategies

### Model Architecture Choices

- **Streaming models**: Lower latency but may sacrifice context
- **Bidirectional models**: Higher accuracy but increased delay
- **Hybrid approaches**: Dynamic switching based on content

### Hardware Considerations

- **GPU acceleration**: 10-50x speedup for large models
- **Edge deployment**: Reduced network latency, privacy benefits
- **Distributed processing**: Parallel processing for batch jobs

## Real-World Case Studies

### Case Study 1: Medical Transcription
- **Requirement**: High accuracy (>98%) for patient records
- **Solution**: Offline processing with large bidirectional models
- **Result**: 99.2% accuracy, 5-second processing time per minute of audio

### Case Study 2: Live Event Captioning
- **Requirement**: <200ms latency for accessibility
- **Solution**: Streaming transformer with sliding window
- **Result**: 91.5% accuracy, 150ms average latency

## Conclusion

The optimal balance between latency and accuracy depends heavily on application requirements. By carefully considering model architecture, hardware deployment, and use case constraints, developers can achieve the right trade-off for their specific needs.

---

*Dr. Alexandra Martinez is a Senior Research Scientist at Speech Technologies Inc. and author of "Modern Speech Recognition Systems" (MIT Press, 2023).*
"""

# Large manual content (100 pages simulation)
large_manual_content = []
for i in range(1, 101):
    page_content = f"""Page {i}
{'='*50}

Section {((i-1)//10)+1}.{((i-1)%10)+1}: Advanced Configuration Options

This section covers detailed configuration parameters for the Knowledge Chipper system.
Understanding these settings is crucial for optimal performance in your specific environment.

Configuration Parameters:
- audio_sample_rate: {16000 + (i*100)}
- max_file_size_mb: {50 + i}
- processing_timeout: {300 + (i*5)}
- enable_diarization: {'true' if i % 2 == 0 else 'false'}
- model_precision: {'fp16' if i % 3 == 0 else 'fp32'}

Example configuration for page {i}:
```yaml
audio:
  sample_rate: {16000 + (i*100)}
  channels: {1 if i % 2 == 0 else 2}
  format: {'wav' if i % 3 == 0 else 'mp3'}

processing:
  max_concurrent_jobs: {min(10, max(1, i//10))}
  queue_size: {100 + (i*2)}
  retry_attempts: {min(5, max(1, i//20))}

output:
  format: markdown
  include_timestamps: {'true' if i % 4 == 0 else 'false'}
  speaker_labels: {'enabled' if i % 3 == 0 else 'disabled'}
```

Performance Notes:
- Memory usage scales with file size and model complexity
- GPU acceleration recommended for files larger than {i*5}MB
- Network latency affects cloud-based processing by {i}ms average

Troubleshooting:
If you encounter issues on page {i}, check the following:
1. Verify audio file format compatibility
2. Ensure sufficient system memory ({i*2}GB recommended)
3. Check network connectivity for cloud services
4. Review log files for detailed error messages

Advanced Topics:
- Custom model training (see Appendix {chr(65 + (i % 26))})
- Integration with external APIs (page {min(200, 150+i)})
- Performance tuning guidelines (section {i//10 + 10})

"""
    large_manual_content.append(page_content)

# Write all document files
(DOCS/"meeting_notes.txt").write_text(meeting_content, encoding="utf-8")
(DOCS/"technical_spec.txt").write_text(tech_spec_content, encoding="utf-8")
(DOCS/"research_paper.txt").write_text(research_content, encoding="utf-8")
(DOCS/"blog_post.md").write_text(blog_content, encoding="utf-8")
(DOCS/"large_manual_100pages.txt").write_text("\n\n".join(large_manual_content), encoding="utf-8")

# HTML documents
news_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speech Tech Summit Draws Record Crowd</title>
</head>
<body>
    <header>
        <h1>Speech Tech Summit Draws Record Crowd</h1>
        <p><em>Published: January 15, 2024 | By: Tech News Reporter</em></p>
    </header>

    <main>
        <p>The annual Speech Technology Summit concluded yesterday with record attendance of over 5,000 participants from around the globe, marking a 40% increase from last year's event.</p>

        <h2>Key Highlights</h2>
        <ul>
            <li>Breakthrough in real-time multilingual translation</li>
            <li>New open-source ASR models achieving 98% accuracy</li>
            <li>Privacy-preserving edge computing solutions</li>
            <li>Integration of speech tech with AR/VR platforms</li>
        </ul>

        <h2>Industry Impact</h2>
        <p>The summit showcased significant advances in automatic speech recognition, with several companies demonstrating systems capable of real-time transcription in noisy environments with unprecedented accuracy.</p>

        <blockquote>
            "We're witnessing a paradigm shift in how speech technology integrates with our daily lives," said Dr. Sarah Chen, keynote speaker and AI research director at Stanford University.
        </blockquote>

        <h2>Future Outlook</h2>
        <p>Looking ahead, the industry consensus points toward increased focus on:</p>
        <ol>
            <li>Edge-based processing for improved privacy</li>
            <li>Multimodal AI combining speech, vision, and text</li>
            <li>Accessibility improvements for diverse populations</li>
            <li>Energy-efficient model architectures</li>
        </ol>

        <p>The next Speech Tech Summit is scheduled for January 2025 in San Francisco.</p>
    </main>

    <footer>
        <p>&copy; 2024 Tech News Network. All rights reserved.</p>
    </footer>
</body>
</html>"""

(DOCS/"news_article.html").write_text(news_html, encoding="utf-8")

# Generate PDF files using reportlab if available, otherwise create placeholder text files
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    # Create research paper PDF
    pdf_path = DOCS / "research_paper.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    # Title page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "A Study on Robust Speaker Diarization")
    c.drawString(50, height - 70, "under Realistic Noise Conditions")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 120, "Abstract")

    # Split text into lines and add to PDF
    text_lines = research_content.split('\n')
    y_position = height - 150
    for line in text_lines[:50]:  # First 50 lines
        if y_position < 50:  # New page
            c.showPage()
            y_position = height - 50
        c.drawString(50, y_position, line[:80])  # Truncate long lines
        y_position -= 15

    c.save()

    print("Created PDF files using reportlab")

except ImportError:
    # Create text versions if reportlab not available
    (DOCS/"research_paper.pdf.txt").write_text(f"PDF placeholder: {research_content}", encoding="utf-8")
    print("Note: reportlab not available, created text placeholders for PDF files")

print("==> Document generation complete!")
print(f"Created test files in: {FIXTURES_DIR}")

# Summary of generated files
audio_files = list(AUDIO.glob("*"))
video_files = list(VIDEO.glob("*"))
doc_files = list(DOCS.glob("*"))

print(f"\nGenerated files summary:")
print(f"Audio files ({len(audio_files)}): {', '.join(f.name for f in audio_files)}")
print(f"Video files ({len(video_files)}): {', '.join(f.name for f in video_files)}")
print(f"Document files ({len(doc_files)}): {', '.join(f.name for f in doc_files)}")

PY

# Create a summary README in the fixtures directory
cat > "${FIXTURES_DIR}/README_generated.md" << 'README'
# Generated Test Files for GUI Comprehensive Testing

This directory contains automatically generated test files for comprehensive GUI testing of Knowledge Chipper.

## Generated Files

### Audio Files
- `short_speech_30s.mp3`, `short_speech_30s.aac`, `short_speech_30s.flac` - 30-second speech samples
- `conversation_2min.wav` - 2-minute multi-speaker conversation
- `music_with_speech.m4a` - Speech with background music
- `poor_quality_recording.mp3` - Low-quality audio for robustness testing
- `interview_10min.flac` - 10-minute interview for diarization
- `podcast_excerpt.ogg` - Podcast-style content
- `conference_talk_30min.wav` - 30-minute conference presentation
- `audiobook_chapter.mp3` - 45-minute audiobook chapter
- `webinar_audio.aac` - Webinar audio in AAC format

### Video Files
- `tutorial_3min.mp4` - Educational tutorial video
- `interview_5min.webm` - Interview with visual elements
- `webinar_10min.mp4` - Presentation-style video
- `conference_talk_15min.mov` - Conference talk in MOV format
- `full_lecture_45min.mp4` - Full-length lecture
- `presentation_short.avi` - Short presentation in AVI format
- `documentary_excerpt.mkv` - Documentary segment in MKV format
- `panel_discussion_60min.webm` - Extended panel discussion

### Document Files
- `meeting_notes.txt` - Realistic meeting notes
- `technical_spec.txt` - Detailed technical specification
- `research_paper.txt` - Academic research paper
- `blog_post.md` - Markdown blog post with formatting
- `news_article.html` - HTML news article
- `large_manual_100pages.txt` - Large document for stress testing
- `research_paper.pdf` - PDF research paper (if reportlab available)

## File Characteristics

### Coverage of Required Formats
✅ Audio: .mp3, .wav, .m4a, .flac, .ogg, .aac
✅ Video: .mp4, .webm, .mov, .avi, .mkv
✅ Documents: .txt, .md, .html, .pdf (when available)

### Size Categories
- **Small files** (<5MB): For quick smoke tests
- **Medium files** (5-50MB): For standard testing
- **Large files** (>50MB): For stress testing

### Content Variety
- Single speaker and multi-speaker audio
- Various audio quality levels
- Different video formats and codecs
- Documents with varying complexity and length

## Usage with GUI Testing

These files are designed to work with:
```bash
python -m tests.gui_comprehensive.main_test_runner smoke
python -m tests.gui_comprehensive.main_test_runner comprehensive
```

All files include appropriate transcripts and metadata for validation testing.

## Sources
- Audio content: Mozilla Common Voice 13.0 (CC0 license)
- Long-form audio: LJ Speech Dataset (Public Domain)
- Video: Synthetic content with real audio
- Documents: Original content created for testing
README

echo "==> Setup complete!"
echo "Test data has been generated in: $FIXTURES_DIR"
echo ""
echo "You can now run GUI comprehensive tests with:"
echo "  cd $PROJECT_ROOT"
echo "  python -m tests.gui_comprehensive.main_test_runner smoke"
echo "  python -m tests.gui_comprehensive.main_test_runner comprehensive"
echo ""
echo "Generated files are compatible with all GUI testing requirements."
