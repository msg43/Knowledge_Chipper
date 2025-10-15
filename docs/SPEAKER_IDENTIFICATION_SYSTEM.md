# Speaker Identification and Attribution System

## Overview

The Knowledge Chipper system uses a sophisticated multi-stage pipeline to identify speakers and assign names to transcript segments. This document explains the complete workflow.

## Architecture: Two Separate Systems

### 1. **Speaker Diarization & Attribution** (Who is speaking when?)
- **Purpose**: Determine WHICH speaker is talking in each time segment
- **Output**: Segments labeled with speaker IDs (e.g., `SPEAKER_0`, `SPEAKER_1`)
- **Location**: Stored in `segment.speaker` field

### 2. **People Extraction** (Who is being discussed?)
- **Purpose**: Extract names of people being DISCUSSED in the content
- **Output**: Database of people mentioned (Warren Buffett, Keynes, etc.)
- **Location**: Stored in HCE `people` table via unified miner

**CRITICAL**: These are completely separate! The speakers themselves are NOT extracted as "people" entries.

## Speaker Identification Pipeline

### Stage 1: Audio Diarization
**Tool**: [pyannote.audio](https://github.com/pyannote/pyannote-audio) v3.1

**Process**:
1. Analyzes audio waveforms to detect different voices
2. Segments audio by speaker changes
3. Assigns generic IDs: `SPEAKER_0`, `SPEAKER_1`, etc.
4. Uses deep learning models for voice activity detection and speaker embedding

**Key Files**:
- `src/knowledge_system/processors/diarization.py` - Main diarization processor
- `src/knowledge_system/processors/audio_processor.py` - Orchestrates diarization

**Sensitivity Settings**:
The system supports "conservative" diarization (fewer false speaker splits):
- `min_cluster_size=20`
- `threshold=0.75`
- `min_duration_on=1.0`

**Device Support**:
- CUDA (GPU) - Fastest
- MPS (Apple Silicon) - Fast with fallback handling
- CPU - Slowest but always works

### Stage 2: Voice Fingerprinting (Over-Segmentation Fix)
**Tool**: Custom implementation with ECAPA-TDNN and Wav2Vec2

**Purpose**: Fix false speaker splits from conservative diarization

**Process**:
1. Extracts voice embeddings using state-of-the-art models:
   - **ECAPA-TDNN** (speechbrain): Speaker verification model
   - **Wav2Vec2** (transformers): Speech representation model
2. Compares speakers pairwise using cosine similarity
3. Merges speakers with >0.7 similarity score
4. Stores voice fingerprints in database for future reference

**Key Features**:
- MFCC (Mel-frequency cepstral coefficients) features
- Spectral features (centroid, rolloff, zero crossing rate)
- Deep learning embeddings (512-dimensional vectors)
- 97% accuracy on 16kHz mono WAV files

**Key Files**:
- `src/knowledge_system/voice/voice_fingerprinting.py` - Voice feature extraction
- `src/knowledge_system/processors/speaker_processor.py` - Integration with diarization

### Stage 3: Speaker Name Suggestion
**Tool**: LLM-based analysis (OpenAI, Anthropic, or local MVP LLM)

**Process**:
1. Analyzes video metadata (title, description, channel name)
2. Examines first 5 speech segments per speaker
3. Looks for self-introductions using regex patterns:
   - `"I'm [Name]"`, `"My name is [Name]"`
   - `"Hi, I'm [Name]"`, `"Hello, this is [Name]"`
   - `"Thanks, [Name]"` (for guest introductions)
4. Matches names phonetically (e.g., "Stacy Rasgon" in title vs. "Stacey Raskin" in speech)
5. Assigns confidence scores (0-1)

**Critical Rules Enforced**:
- ✅ Each speaker gets a UNIQUE name (no duplicates)
- ✅ Metadata names beat transcription variants
- ✅ Phonetic matching preferred
- ✅ No empty names allowed

**Key Files**:
- `src/knowledge_system/utils/llm_speaker_suggester.py` - LLM-based name detection
- `src/knowledge_system/processors/speaker_processor.py` - Regex patterns for self-introductions

**Regex Patterns**:
```python
"self_introduction": r"\b(?:I'm|my name is|this is|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
"greeting": r"\b(?:hi|hello|hey),?\s+(?:I'm|this is)\s+([A-Z][a-z]+)"
"role_introduction": r"\b(?:as the|I'm the|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
"direct_address": r"\b(?:thanks?|thank you),?\s+([A-Z][a-z]+)"
```

### Stage 4: User Confirmation (GUI Mode)
**Tool**: Custom Qt dialog

**Process**:
1. Shows AI-suggested names with confidence scores
2. Displays sample speech segments for verification
3. User can:
   - Accept AI suggestions
   - Edit names manually
   - Override with custom names
4. Assignments saved to database for future use

**Key Files**:
- `src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py` - GUI dialog
- `src/knowledge_system/database/speaker_models.py` - Database persistence

### Stage 5: Automatic Assignment (Non-GUI Mode)
**Priority Order**:

1. **Manual Override** (highest priority)
   - User-provided mappings
   - From previous sessions in database

2. **Content-Based Detection**
   - LLM analysis of transcript + metadata
   - Regex pattern matching

3. **Fallback**
   - Generic names: "Speaker 1", "Speaker 2"
   - Preserves original speaker IDs

**Key Files**:
- `src/knowledge_system/utils/speaker_attribution.py` - Attribution priority logic
- `src/knowledge_system/processors/audio_processor.py` - Orchestration

### Stage 6: Database Persistence
**Storage**:

1. **Speaker Assignments** (`speaker_assignments` table)
   - Maps speaker IDs to assigned names
   - Tracks confidence scores and sources
   - Persists across sessions

2. **Voice Fingerprints** (`speaker_voices` table)
   - Stores voice embeddings (ECAPA-TDNN, Wav2Vec2, MFCC)
   - Enables voice-based speaker recognition
   - Can match speakers across different recordings

3. **Processing Sessions** (JSON metadata)
   - Complete processing history
   - AI suggestions vs. user corrections
   - Used for system learning/improvement

**Key Files**:
- `src/knowledge_system/database/speaker_models.py` - SQLAlchemy models
- `src/knowledge_system/processors/speaker_processor.py` - Database integration

## Segment Attribution Flow

```
Audio File
    ↓
[Diarization] → Generic speaker IDs (SPEAKER_0, SPEAKER_1)
    ↓
[Voice Fingerprinting] → Merge over-segmented speakers
    ↓
[Text Assignment] → Match transcript to speaker segments
    ↓
[LLM Analysis] → Suggest real names from metadata + transcript
    ↓
[User Confirmation] → Accept/Edit/Override names (GUI only)
    ↓
[Database Storage] → Save assignments + voice fingerprints
    ↓
Final Transcript → Segments with real speaker names
```

## Integration with HCE Pipeline

**Important**: Speaker attribution happens BEFORE HCE mining.

The HCE unified miner receives segments already labeled with speaker names:

```json
{
  "segment_id": "seg_001",
  "speaker": "Jeff Snider",  // Real name assigned by pipeline
  "t0": "00:00:15",
  "t1": "00:00:32",
  "text": "The Eurodollar market is crucial to understanding..."
}
```

The miner extracts:
- **Claims** made by Jeff Snider
- **Jargon** he uses
- **People** he discusses (Warren Buffett, Ben Bernanke, etc.)
- **Mental models** he explains

The speaker name (`Jeff Snider`) is metadata, NOT a "people" extraction.

## Why Speakers Aren't Extracted as "People"

From the unified miner prompt:

```
<bad_example>
  <input>"Thanks for tuning in, I'm Sarah and today we'll discuss inflation."</input>
  <explanation>DON'T extract "Sarah" - procedural self-identification by the speaker. 
  Only extract when the person is the subject of discussion.</explanation>
</bad_example>
```

**Reasoning**:
1. Speaker identity is already captured in `segment.speaker` field
2. "People" extraction is for analyzing WHO is being discussed
3. Self-introductions are procedural, not substantive content
4. Prevents duplication and database clutter

**Counter-example** (WOULD extract):
```
"Warren Buffett has long advocated for index fund investing..."
```
Here, Buffett is being DISCUSSED, not speaking, so he gets extracted.

## Tools Summary

| Stage | Tool | Purpose |
|-------|------|---------|
| Diarization | pyannote.audio v3.1 | Separate voices in audio |
| Voice Fingerprinting | ECAPA-TDNN + Wav2Vec2 | Merge over-segmented speakers |
| Name Detection (LLM) | OpenAI/Anthropic/MVP | Suggest names from metadata + transcript |
| Name Detection (Regex) | Python regex | Find self-introductions in text |
| User Interface | Qt Dialog | Manual name confirmation/editing |
| Persistence | SQLite + SQLAlchemy | Store assignments + fingerprints |
| Attribution Priority | Custom logic | Choose best name source |

## Database Schema

### `speaker_assignments` Table
```sql
CREATE TABLE speaker_assignments (
  id INTEGER PRIMARY KEY,
  speaker_id TEXT NOT NULL,
  assigned_name TEXT NOT NULL,
  confidence_score REAL,
  source_file TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### `speaker_voices` Table
```sql
CREATE TABLE speaker_voices (
  id INTEGER PRIMARY KEY,
  speaker_id TEXT NOT NULL,
  assigned_name TEXT,
  voice_fingerprint TEXT,  -- JSON with embeddings
  audio_samples TEXT,       -- JSON with sample paths
  created_at TIMESTAMP
);
```

### `segments` Table (HCE)
```sql
CREATE TABLE segments (
  episode_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  speaker TEXT,             -- Real name assigned by pipeline
  t0 TEXT,
  t1 TEXT,
  text TEXT,
  topic_guess TEXT,
  PRIMARY KEY (episode_id, segment_id)
);
```

## Configuration

### Settings Location
`src/knowledge_system/config/settings.py`

### Key Settings
```python
speaker_identification:
  diarization_sensitivity: "conservative"  # or "balanced", "aggressive"
  voice_fingerprinting_enabled: true
  min_confidence_threshold: 0.6
  auto_assign_high_confidence: true
```

## Future Enhancements

1. **Cross-Recording Speaker Recognition**
   - Match voice fingerprints across different episodes
   - Build persistent speaker profiles

2. **Active Learning**
   - Learn from user corrections
   - Improve LLM suggestions over time

3. **Multi-Language Support**
   - Extend regex patterns for non-English names
   - Support international name formats

4. **Real-Time Diarization**
   - Process audio streams in real-time
   - Live speaker identification

## References

- [pyannote.audio Documentation](https://github.com/pyannote/pyannote-audio)
- [ECAPA-TDNN Paper](https://arxiv.org/abs/2005.07143)
- [Wav2Vec2 Paper](https://arxiv.org/abs/2006.11477)
- Memory ID: 8391810 (Voice fingerprinting system details)
