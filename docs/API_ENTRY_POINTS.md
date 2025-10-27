# Knowledge Chipper API Entry Points

This document clarifies the correct entry points for using Knowledge Chipper programmatically after the 2025-10 refactoring that eliminated duplicate code paths.

---

## Quick Reference

| Task | Entry Point | Location |
|------|-------------|----------|
| **Transcribe Audio** | `AudioProcessor.process()` | `processors/audio_processor.py` |
| **Transcribe YouTube** | Download → `AudioProcessor` | See [YouTube section](#youtube-transcription) |
| **Summarize/Mine** | `System2Orchestrator.create_job()` | `core/system2_orchestrator.py` |
| **Batch Processing** | `UnifiedBatchProcessor` | `processors/unified_batch_processor.py` |
| **Job Tracking** | `System2Orchestrator` | `core/system2_orchestrator.py` |

---

## Transcription

### Local Audio Files (CANONICAL)

```python
from knowledge_system.processors.audio_processor import AudioProcessor

# Basic transcription
processor = AudioProcessor(
    model="base",  # tiny/base/small/medium/large
    device="cpu",  # cpu/mps/cuda
    use_whisper_cpp=True,  # Core ML acceleration on Apple Silicon
)

result = processor.process("path/to/audio.mp3")

if result.success:
    print(result.data["transcript"])
    print(f"Language: {result.data['language']}")
    print(f"Duration: {result.data['duration']}s")
else:
    print(f"Error: {result.errors}")
```

### With Speaker Diarization

```python
processor = AudioProcessor(
    model="base",
    device="cpu",
    enable_diarization=True,
    hf_token="your_huggingface_token",  # Required for diarization
    speaker_assignment_callback=None,  # GUI will provide this
)

result = processor.process(
    "path/to/audio.mp3",
    output_dir="path/to/output",
    include_timestamps=True,
)

# Result includes speaker-attributed segments
speakers = result.metadata.get("speakers", [])
print(f"Detected {len(speakers)} speakers")
```

### YouTube Transcription

```python
from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
from knowledge_system.processors.audio_processor import AudioProcessor

# Step 1: Download audio
downloader = YouTubeDownloadProcessor(
    download_thumbnails=True,
    enable_cookies=False,  # Set True for throwaway account cookies
)

download_result = downloader.process(
    "https://youtube.com/watch?v=VIDEO_ID",
    output_dir="./downloads",
)

if download_result.success:
    # Step 2: Transcribe downloaded audio
    audio_path = download_result.data["audio_path"]
    
    processor = AudioProcessor(model="base", device="cpu")
    transcript_result = processor.process(
        audio_path,
        output_dir="./transcripts",
        video_metadata=download_result.metadata,  # Includes title, uploader, tags
    )
    
    if transcript_result.success:
        print(transcript_result.data["transcript"])
```

### Using System2 Job Tracking (NEW!)

```python
from knowledge_system.core.system2_orchestrator import System2Orchestrator

orchestrator = System2Orchestrator()

# Create transcription job
job_id = orchestrator.create_job(
    job_type="transcribe",
    input_id="audio_001",
    config={
        "file_path": "path/to/audio.mp3",
        "model": "base",
        "device": "cpu",
        "enable_diarization": False,
        "output_dir": "./output",
    },
    auto_process=False,
)

# Execute job (async)
import asyncio
result = asyncio.run(orchestrator.process_job(job_id))

if result["status"] == "succeeded":
    print(f"Transcript: {result['result']['transcript_path']}")
    print(f"Language: {result['result']['language']}")
```

**Benefits of System2 job tracking:**
- Automatic database persistence
- Job status tracking
- Resume from checkpoints (future)
- LLM request/response logging
- Metrics collection

---

## Summarization / Mining

### Standard Summarization (CANONICAL)

```python
from knowledge_system.core.system2_orchestrator import System2Orchestrator
import asyncio

orchestrator = System2Orchestrator()

# Create mining job (performs HCE analysis)
job_id = orchestrator.create_job(
    job_type="mine",
    input_id="my_document",
    config={
        "file_path": "path/to/transcript.md",
        "miner_model": "ollama:qwen2.5:7b-instruct",
        "output_dir": "./output",
    },
    auto_process=False,
)

# Execute job
result = asyncio.run(orchestrator.process_job(job_id))

if result["status"] == "succeeded":
    print(f"Claims extracted: {result['result']['claims_extracted']}")
    print(f"People: {result['result']['people_extracted']}")
    print(f"Concepts: {result['result']['mental_models_extracted']}")
    print(f"Summary file: {result['summary_file']}")
```

### What Happens During Mining

The HCE (Hybrid Claim Extraction) pipeline performs **4 passes**:

1. **Pass 0: Short Summary** - Generate contextual overview
2. **Pass 1: Unified Mining** - Extract claims, jargon, people, mental models (PARALLEL)
3. **Pass 2: Flagship Evaluation** - Rank claims A/B/C, filter noise
4. **Pass 3: Long Summary** - Generate comprehensive narrative synthesis
5. **Pass 4: Structured Categories** - WikiData topic categorization

### Output Storage

All mining results are stored in unified SQLite database tables:
- `claims` - Extracted claims with A/B/C tier rankings
- `evidence_spans` - Timestamped evidence for each claim
- `jargon` - Technical terms with definitions
- `people` - Person mentions with roles
- `concepts` - Mental models and frameworks
- `relations` - Relationships between claims
- `categories` - WikiData topic categories
- `summaries` - Generated narrative summaries

---

## Batch Processing

### For Multiple Files/URLs

```python
from knowledge_system.processors.unified_batch_processor import UnifiedBatchProcessor
from knowledge_system.utils.cancellation import CancellationToken

# Mix of YouTube URLs and local files
items = [
    "https://youtube.com/watch?v=VIDEO1",
    "https://youtube.com/playlist?list=PLAYLIST_ID",
    "path/to/local_audio.mp3",
    "path/to/local_video.mp4",
]

config = {
    "model": "base",
    "device": "cpu",
    "output_dir": "./output",
    "enable_diarization": False,
    "use_whisper_cpp": True,
    "timestamps": True,
}

def progress_callback(current, total, message):
    print(f"[{current}/{total}] {message}")

def url_completed_callback(item, success, message):
    status = "✅" if success else "❌"
    print(f"{status} {item}: {message}")

processor = UnifiedBatchProcessor(
    items=items,
    config=config,
    progress_callback=progress_callback,
    url_completed_callback=url_completed_callback,
)

results = processor.process_all()

print(f"Successful: {results['successful_count']}")
print(f"Failed: {results['failed_count']}")
```

**Features:**
- Automatic playlist expansion
- Parallel processing (based on hardware)
- Memory pressure handling
- Duplicate detection
- Proxy management for YouTube

---

## YouTube Download Service (NEW!)

For advanced YouTube download scenarios:

```python
from knowledge_system.services.youtube_download_service import YouTubeDownloadService
from pathlib import Path

service = YouTubeDownloadService(
    enable_cookies=True,
    cookie_file_path="path/to/cookies.txt",
    youtube_delay=5,  # Seconds between downloads
)

# Expand playlists
urls = ["https://youtube.com/playlist?list=..."]
expanded_urls, playlist_info = service.expand_urls(urls)

print(f"Expanded to {len(expanded_urls)} videos")

# Download sequentially (avoid bot detection)
downloads_dir = Path("./downloads")
results = service.download_sequential(
    expanded_urls,
    downloads_dir,
    progress_callback=lambda url, idx, total, status: print(f"[{idx}/{total}] {status}: {url}"),
)

# Check for failures
failed = service.get_failed_urls()
if failed:
    service.save_failed_urls(downloads_dir)
    print(f"{len(failed)} URLs failed")
```

---

## ⛔ DEPRECATED / REMOVED

### DO NOT USE - Deleted in 2025-10 Refactoring:

```python
# ❌ REMOVED: TranscriptionService (was just a wrapper around AudioProcessor)
from knowledge_system.services.transcription_service import TranscriptionService

# Instead use AudioProcessor directly (see above)
```

```python
# ❌ REMOVED: Duplicate worker classes in processing_workers.py
from knowledge_system.gui.workers import EnhancedTranscriptionWorker
from knowledge_system.gui.workers import EnhancedSummarizationWorker

# Workers are now defined in their respective tabs:
# - EnhancedTranscriptionWorker: gui/tabs/transcription_tab.py
# - EnhancedSummarizationWorker: gui/tabs/summarization_tab.py
```

---

## GUI Integration

### For GUI Developers

**DO NOT** import processors directly in GUI code. Use the tab-specific workers:

```python
# ✅ CORRECT: Use tab's worker
from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab
from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

# Workers are defined WITHIN the tab files
# They handle GUI-specific concerns (signals, dialogs, progress bars)
```

**Workers are NOT exported** from `gui/workers/__init__.py` because they're tab-specific.

---

## Architecture Principles

### Single Responsibility

1. **`AudioProcessor`** - Core transcription engine (Whisper.cpp, diarization, file I/O)
2. **`System2Orchestrator`** - Job management, database tracking, checkpointing
3. **`UnifiedBatchProcessor`** - Batch operations with resource management
4. **`YouTubeDownloadProcessor`** - YouTube audio download with proxy support
5. **Tab Workers** - GUI integration (signals, dialogs, progress)

### Layering

```
GUI Layer (Tabs + Workers)
    ↓
Service Layer (System2Orchestrator, UnifiedBatchProcessor)
    ↓
Processor Layer (AudioProcessor, YouTubeDownloadProcessor)
    ↓
Core Libraries (Whisper.cpp, pyannote.audio, yt-dlp)
```

### When to Use What

| Scenario | Use This | Why |
|----------|----------|-----|
| GUI transcription | TranscriptionTab worker | Handles dialogs, signals, speaker assignment |
| API transcription | AudioProcessor directly | No GUI overhead |
| Batch transcription | UnifiedBatchProcessor | Resource optimization |
| Job tracking | System2Orchestrator | Database persistence, resumability |
| YouTube download | YouTubeDownloadProcessor | Proxy support, metadata extraction |

---

## Migration Guide

### If You Were Using TranscriptionService:

```python
# OLD (DELETED):
from knowledge_system.services.transcription_service import TranscriptionService
service = TranscriptionService(whisper_model="base")
result = service.transcribe_audio_file("audio.mp3")
text = result.get("transcript")

# NEW (CURRENT):
from knowledge_system.processors.audio_processor import AudioProcessor
processor = AudioProcessor(model="base")
result = processor.process("audio.mp3")
text = result.data["transcript"] if result.success else None
```

**Changes:**
- `result` is now a `ProcessorResult` object, not a dict
- Access data via `result.data`, `result.metadata`, `result.success`
- Errors via `result.errors` (list)

---

## Testing

### Unit Tests

```python
# Test transcription
def test_transcription():
    from knowledge_system.processors.audio_processor import AudioProcessor
    
    processor = AudioProcessor(model="tiny")  # Fast for testing
    result = processor.process("tests/fixtures/sample_audio.mp3")
    
    assert result.success
    assert len(result.data["transcript"]) > 0
```

### Integration Tests

```python
# Test full System2 workflow
async def test_system2_transcription():
    from knowledge_system.core.system2_orchestrator import System2Orchestrator
    
    orchestrator = System2Orchestrator()
    job_id = orchestrator.create_job(
        "transcribe",
        "test_audio",
        {"file_path": "test.mp3", "model": "tiny"}
    )
    
    result = await orchestrator.process_job(job_id)
    assert result["status"] == "succeeded"
```

---

## Performance Considerations

### Model Selection

- **tiny** (~40MB) - 2-3x real-time, good for quick tests, lower accuracy
- **base** (~150MB) - 1-2x real-time, **recommended default**, good accuracy
- **small** (~500MB) - ~1x real-time, better accuracy
- **medium** (~1.5GB) - 0.5x real-time, high accuracy
- **large** (~3GB) - 0.3x real-time, highest accuracy, risk of hallucination

### Diarization Overhead

- **Without diarization:** ~1x audio duration
- **With diarization:** ~2-3x audio duration
- Diarization adds speaker detection but is significantly slower

### Parallel Processing

- **UnifiedBatchProcessor** automatically scales based on available CPU/RAM
- **TranscriptionTab** processes files sequentially (GUI stability)
- **HCE Mining** parallelizes at segment level (3-8x speedup)

---

## Support & Documentation

- **Main README:** `/README.md`
- **Summarization Flow:** `/SUMMARIZATION_FLOW_ANALYSIS.md`
- **Transcription Flow:** `/TRANSCRIPTION_FLOW_ANALYSIS.md`
- **Process Summary:** `/PROCESS_ANALYSIS_SUMMARY.md`

**Last Updated:** October 26, 2025
**Refactoring:** Post-duplicate-code-elimination
