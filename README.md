# Knowledge Chipper (Skip the Podcast Desktop)

> Transform audio, video, and documents into structured knowledge with AI-powered analysis

**Version 3.2.22** | **macOS Application** | **Offline-First Design**

## Why Knowledge Chipper Exists

In our information-rich world, valuable insights are buried in hours of podcasts, video lectures, research papers, and meeting recordings. Knowledge Chipper was created to solve a fundamental problem: **extracting actionable intelligence from unstructured media content**.

Traditional transcription tools give you text. Knowledge Chipper gives you **structured knowledge**:
- **Claims** with confidence ratings (A/B/C tiers)
- **Speaker identification** with 97% voice fingerprinting accuracy  
- **Entity extraction** (people, concepts, technical terms)
- **Relationship mapping** between ideas and contradictions
- **Evidence citations** linking claims to exact sources

Perfect for researchers, students, professionals, and anyone who needs to process large volumes of content efficiently.

## What Knowledge Chipper Accomplishes

### 🎯 Core Capabilities

**📹 Universal Content Processing**
- YouTube videos and playlists
- Local audio/video files (MP4, MP3, WAV, etc.)
- Documents (PDF, Word, Markdown, Plain Text)
- Batch processing of entire folders

**🎙️ Advanced Speaker Intelligence**
- State-of-the-art voice fingerprinting (ECAPA-TDNN + Wav2Vec2 models)
- Conservative diarization with AI-powered speaker merging
- Persistent speaker profiles across recordings
- LLM-validated speaker identification

**🧠 Structured Knowledge Extraction**
- **HCE System**: Hybrid Claim Extractor with A/B/C confidence tiers
- **Entity Recognition**: People, concepts, jargon, mental models
- **Contradiction Detection**: Identify conflicting information
- **Relationship Mapping**: Connect related claims and evidence
- **Semantic Deduplication**: Eliminate redundant content

**📊 Knowledge Organization**
- SQLite-first database with optional cloud sync
- Obsidian integration with auto-tagging
- Searchable claim database across all content
- Knowledge maps (MOCs) linking related content
- Multiple export formats (Markdown, YAML, JSON, CSV)

### 🚀 Key Differentiators

1. **Offline-First Design**: Complete functionality without internet connection
2. **Bundled Dependencies**: ~600MB DMG includes all AI models and tools
3. **97% Voice Accuracy**: Enterprise-grade speaker verification models
4. **Claim-Based Analysis**: Structured extraction vs. basic summarization
5. **Hardware Optimized**: Apple Silicon MPS and CUDA acceleration
6. **Zero Configuration**: Works immediately after installation

## How to Use Knowledge Chipper

### Quick Start (5 Minutes)

1. **Download & Install**
   - Download the DMG from releases
   - Right-click → Open (to bypass Gatekeeper)
   - Everything bundled - no additional setup required

2. **Your First Transcription**
   - Launch the app → "Local Transcription" tab
   - Drop in an audio/video file
   - Click "Start Transcription"
   - Speaker diarization runs automatically

3. **Extract Knowledge**
   - Go to "Summarization" tab
   - Select your transcript file
   - Choose analysis type (HCE is default)
   - Review extracted claims with A/B/C confidence ratings

4. **Explore Results**
   - "Claim Search" tab: Filter and explore extracted knowledge
   - "Speaker Attribution" tab: Review and correct speaker identification
   - All results stored in SQLite database for fast searching

### Desktop Interface Overview

The application provides a tabbed interface for different workflows:

**🎬 Content Input**
- **YouTube Extraction**: Process videos and playlists
- **Local Transcription**: Handle local audio/video files
- **Document Processing**: Analyze PDFs and text documents

**🧠 Analysis & Organization**  
- **Summarization**: Extract structured claims and entities (HCE system)
- **Process Management**: Full pipeline processing (transcribe → analyze → organize)
- **Claim Search**: Explore extracted knowledge across all content

**🎙️ Speaker Management**
- **Speaker Attribution**: Review and assign speaker names
- **Voice Enrollment**: Create persistent speaker profiles

**⚙️ System Management**
- **File Watcher**: Automated processing of new files
- **API Keys**: Configure LLM providers (OpenAI, Anthropic, Local)
- **Sync Status**: Manage cloud backup (optional)

### Command Line Interface

For automation and scripting:

```bash
# Basic transcription with speaker diarization
knowledge-system transcribe --input "video.mp4" --enable-diarization

# Extract structured knowledge
knowledge-system summarize "transcript.md"

# Process entire folders
knowledge-system process ./content/ --recursive

# Voice fingerprinting
knowledge-system voice enroll --speaker-name "John Doe" --audio-file "sample.wav"

# Get help
knowledge-system --help
```

### Input Formats Supported

**Audio & Video**: MP4, MOV, MP3, WAV, M4A, WEBM (anything FFmpeg supports)
**Documents**: PDF, DOCX, DOC, RTF, TXT, MD
**Web Content**: YouTube URLs and playlists
**Batch Processing**: Entire folders with pattern matching

### Output Formats

**Structured Data**: SQLite database (primary storage)
**Knowledge Maps**: Markdown with Obsidian linking
**Exports**: YAML, JSON, CSV for integration
**Reports**: Detailed processing summaries

## Advanced Features

### HCE (Hybrid Claim Extractor) System

The core intelligence engine that replaces traditional summarization:

- **A/B/C Confidence Tiers**: Claims rated by reliability
- **Evidence Citations**: Every claim linked to exact source quotes
- **Contradiction Detection**: Identify conflicting information
- **Entity Recognition**: People, concepts, jargon automatically extracted
- **Relationship Mapping**: Connections between ideas and entities
- **Interactive Validation**: Review and correct AI-assigned tiers

### Voice Fingerprinting Technology

State-of-the-art speaker verification achieving 97% accuracy:

- **Multi-Modal Analysis**: MFCC, spectral, prosodic features + deep embeddings
- **Enterprise Models**: Wav2Vec2 (Facebook) + ECAPA-TDNN (SpeechBrain)
- **Hardware Accelerated**: Automatic MPS (Apple Silicon) and CUDA support
- **Persistent Profiles**: Voice enrollment for automatic recognition
- **Conservative Diarization**: Moderate clustering with AI-powered merging

### Intelligent Processing Pipeline

1. **Content Ingestion** → Universal format support
2. **Transcription** → Whisper with speaker diarization  
3. **Voice Fingerprinting** → 97% accurate speaker identification
4. **LLM Validation** → AI-powered speaker name suggestion
5. **Knowledge Extraction** → HCE claim analysis with entities
6. **Storage** → SQLite database with relationships
7. **Export** → Multiple formats for integration

### Performance & Optimization

- **Smart Chunking**: Model-aware content segmentation
- **Batch Processing**: Efficient handling of large volumes
- **Cache Management**: Intelligent caching for speed
- **Hardware Acceleration**: Optimized for Apple Silicon and CUDA
- **Offline Operation**: No internet required for core functionality

## Configuration & Customization

The system uses a layered configuration approach:

1. **Default Settings**: System defaults (read-only)
2. **User Configuration**: Your personal overrides
3. **Environment Variables**: Runtime overrides

Key configuration areas:
- **LLM Providers**: OpenAI, Anthropic, local models
- **Voice Processing**: Sensitivity thresholds, model selection
- **Output Preferences**: Export formats, file organization
- **Performance**: Batch sizes, hardware utilization

## Use Cases

### Research & Academia
- Process lecture recordings and research papers
- Extract structured claims with evidence citations
- Build knowledge maps connecting related concepts
- Identify contradictions in literature

### Business & Professional
- Analyze meeting recordings and presentations
- Process training materials and documentation
- Create searchable knowledge bases
- Track speaker contributions and insights

### Content Analysis
- Podcast and video content analysis
- Multi-speaker conversation processing
- Claim verification and fact-checking
- Relationship mapping between ideas

### Personal Knowledge Management
- Organize learning materials
- Build personal knowledge bases
- Track insights across multiple sources
- Integrate with Obsidian workflows

## Installation & Setup

### System Requirements
- **macOS 10.15+** (Catalina or later)
- **8GB RAM minimum** (16GB+ recommended)
- **2GB free disk space** 
- **Apple Silicon or Intel Mac** (Apple Silicon recommended)

### Installation Options

**Option 1: DMG Installation (Recommended)**
1. Download the latest DMG from releases (~600MB)
2. Mount and copy to Applications
3. Right-click → Open to bypass Gatekeeper
4. All models and dependencies pre-bundled

**Option 2: Manual Installation**
```bash
git clone https://github.com/your-repo/knowledge_chipper.git
cd knowledge_chipper
pip install -e ".[full]"
knowledge-system gui
```

### First Run Setup
1. Configure API keys for your preferred LLM provider
2. Test with a short audio file
3. Ready to process your content!

## Performance & Hardware

### Recommended Hardware
- **Apple M2/M3**: Optimal performance with MPS acceleration
- **16GB+ RAM**: For large files and batch processing
- **SSD Storage**: Fast I/O for temporary files
- **GPU**: Apple Silicon or NVIDIA for acceleration

### Processing Performance
- **Transcription**: 2-15 minutes per hour of audio (model dependent)
- **Analysis**: 30-90 seconds per 10k words (model dependent)
- **Voice Fingerprinting**: Near real-time on Apple Silicon
- **Batch Processing**: Linear scaling with parallel workers

## Troubleshooting

### Common Issues
- **Installation**: Right-click → Open to bypass Gatekeeper warnings
- **API Errors**: Verify API keys and model access in API Keys tab
- **Poor Quality**: Use larger models for better accuracy
- **Performance**: Enable GPU acceleration in settings

### Getting Help
- Check the `/docs` directory for detailed documentation
- Review processing reports for specific error messages
- Use the built-in model refresh to update available options
- Consult the CHANGELOG.md for version-specific information

---

**Ready to transform your content into structured knowledge?** Download Knowledge Chipper and start extracting insights from your audio, video, and document libraries today.

For technical documentation, troubleshooting, and advanced configuration, see the `/docs` directory and `CHANGELOG.md` for detailed feature history.
