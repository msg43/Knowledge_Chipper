# Skipthepodcast.com (Skip the Podcast Desktop)

> Transform audio, video, and documents into structured knowledge with AI-powered analysis

**Version 3.3.0** | **macOS Application** | **Offline-First Design**

## 🆕 What's New in Version 3.3.0

### Revolutionary Unified HCE Pipeline
- **🔄 Two-Pass Architecture**: Streamlined Miner → Flagship Evaluator system
- **📊 Enhanced Scoring**: Importance, novelty, confidence on 1-10 scale
- **🎯 Single-Pass Extraction**: Claims, people, concepts, jargon in one operation
- **📋 Claim Type Classification**: Factual, causal, normative, forecast, definitional

### Qwen Model Integration
- **🚀 Superior JSON Compliance**: Industry-leading structured output reliability
- **🖥️ Hardware-Optimized Selection**: Automatic model recommendations by Mac specs
- **⚡ Consistent Performance**: All tiers use Qwen models for reliability
- **🔧 Multi-shot Prompting**: Examples and anti-examples for consistent results

### Technical Improvements
- **📈 Simplified Architecture**: Removed complex routing and reranking systems
- **🎛️ Updated GUI**: Streamlined controls for Miner and Flagship model selection
- **🔍 Schema Validation**: Guaranteed JSON output with comprehensive error handling
- **📚 Enhanced Documentation**: Updated troubleshooting and configuration guides

### Intelligent Download Pacing
- **🤖 Smart Rate Limiting**: Automatically spaces YouTube downloads to avoid bot detection
- **📊 Real-Time Monitoring**: Tracks processing pipeline status and adjusts download timing
- **⚡ Pipeline Optimization**: Keeps downloads ahead of summarization without overwhelming servers
- **🔧 Large Scale Support**: Designed for processing 1000+ videos efficiently

---

## Why Skipthepodcast.com Exists

In our information-rich world, valuable insights are buried in hours of podcasts, video lectures, research papers, and meeting recordings. Skipthepodcast.com was created to solve a fundamental problem: **extracting actionable intelligence from unstructured media content**.

Traditional transcription tools give you text. Skipthepodcast.com gives you **structured knowledge**:
- **Claims** with importance, novelty, and confidence scores (1-10 scale)
- **Speaker identification** with 97% voice fingerprinting accuracy  
- **Entity extraction** (people, concepts, technical terms) in single pass
- **Claim type classification** (factual, causal, normative, forecast, definitional)
- **Evidence citations** linking claims to exact sources

Perfect for researchers, students, professionals, and anyone who needs to process large volumes of content efficiently.

## What Skipthepodcast.com Accomplishes

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
- **Unified HCE Pipeline**: Streamlined two-pass system (Miner → Flagship Evaluator)
- **Enhanced JSON Compliance**: Qwen models for reliable structured output
- **Entity Recognition**: People, concepts, jargon, mental models in single pass
- **Intelligent Claim Ranking**: LLM-powered importance, novelty, and confidence scoring
- **Semantic Deduplication**: Eliminate redundant content

**📊 Knowledge Organization**
- SQLite-first database with optional cloud sync
- Obsidian integration with auto-tagging
- Searchable claim database across all content
- Knowledge maps (MOCs) linking related content
- Multiple export formats (Markdown, YAML, JSON, CSV)

### 🚀 Key Differentiators

1. **Unified HCE Pipeline**: Revolutionary two-pass system for superior claim extraction
2. **Qwen Model Integration**: Industry-leading JSON compliance and structured output
3. **97% Voice Accuracy**: Enterprise-grade speaker verification models
4. **Hardware-Optimized Models**: Automatic model selection based on Mac specifications
5. **Apple Silicon Acceleration**: Optimized for M2/M3 with MPS support
6. **Zero Configuration**: Works immediately after installation

## How to Use Skipthepodcast.com

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
   - Choose analysis type (Unified HCE is default)
   - Review extracted claims with importance, novelty, and confidence scores (1-10 scale)

4. **Explore Results**
   - "Claim Search" tab: Filter and explore extracted knowledge
   - "Speaker Attribution" tab: Review and correct speaker identification
   - All results stored in SQLite database for fast searching

### Desktop Interface Overview

The application provides a tabbed interface for different workflows:

**🎬 Content Input**
- **YouTube Extraction**: Process videos and playlists with intelligent pacing
- **Local Transcription**: Handle local audio/video files
- **Document Processing**: Analyze PDFs and text documents

**🧠 Analysis & Organization**  
- **Summarization**: Extract structured claims and entities (Unified HCE system)
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

### Unified HCE (Hybrid Claim Extractor) System

The revolutionary two-pass intelligence engine that replaces traditional summarization:

**🔄 Two-Pass Architecture:**
1. **Unified Miner**: Single pass extraction of claims, people, concepts, and jargon with claim type classification
2. **Flagship Evaluator**: Comprehensive LLM-powered ranking and validation of all extracted entities

**📊 Advanced Scoring System:**
- **Importance** (1-10): Core relevance and significance
- **Novelty** (1-10): Uniqueness and freshness of information  
- **Confidence** (1-10): Reliability and evidence quality
- **Claim Types**: Factual, causal, normative, forecast, definitional

**🎯 Key Features:**
- **JSON Schema Validation**: Guaranteed structured output with Qwen models
- **Multi-shot Prompting**: Examples and anti-examples for consistent results
- **Evidence Citations**: Every claim linked to exact source quotes
- **Entity Recognition**: Comprehensive extraction in single pass
- **Interactive Validation**: Review and correct AI-assigned scores

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
5. **Unified Mining** → Single-pass extraction of all entities with Qwen models
6. **Flagship Evaluation** → Comprehensive LLM ranking and validation
7. **Storage** → SQLite database with relationships
8. **Export** → Multiple formats for integration

### Hardware-Optimized Model Selection

Automatic model recommendations based on your Mac specifications:

- **🔥 M2/M3 Ultra (64GB+ RAM)**: `qwen2.5:14b-instruct` (8.2GB) - Maximum capability
- **🔥 M2/M3 Max (32GB+ RAM)**: `qwen2.5:14b-instruct` (8.2GB) - High performance  
- **🔥 M2/M3 Pro (16GB+ RAM)**: `qwen2.5:7b-instruct` (4GB) - Balanced efficiency
- **🔥 Base Systems**: `qwen2.5:3b-instruct` (2GB) - Optimized for limited resources

**Key Benefits:**
- **Consistent JSON Compliance**: All Qwen models excel at structured output
- **Automatic Detection**: Hardware specs detected during installation
- **Optimal Performance**: Right-sized models for your system capabilities
- **Future-Proof**: Easy model upgrades as hardware improves

### Performance & Optimization

- **Smart Chunking**: Model-aware content segmentation
- **Unified Pipeline**: Streamlined two-pass processing for efficiency
- **Cache Management**: Intelligent caching for speed
- **Hardware Acceleration**: Optimized for Apple Silicon MPS
- **Offline Operation**: No internet required for core functionality

## Configuration & Customization

The system uses a layered configuration approach:

1. **Default Settings**: System defaults (read-only)
2. **User Configuration**: Your personal overrides
3. **Environment Variables**: Runtime overrides

Key configuration areas:
- **LLM Providers**: OpenAI, Anthropic, local Qwen models
- **HCE Pipeline**: Miner and Flagship model selection
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

### Intelligent Updates & Caching

Skip the Podcast Desktop features an intelligent component caching system that makes updates fast and efficient:

**🚀 Smart Update System:**
- **Daily patches**: Only download changed app code (~940KB)
- **Large components**: Python, AI models, FFmpeg cached until version changes
- **Automatic detection**: System knows what needs updating
- **Bandwidth efficient**: 99.7% reduction in update downloads

**💡 Recommendation:**
Enable **"Check for updates on startup"** in the app settings to get the latest features and improvements automatically. The intelligent caching system ensures updates are lightning-fast, typically downloading only the small app code changes rather than re-downloading large components.

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

**Ready to transform your content into structured knowledge?** Download Skipthepodcast.com and start extracting insights from your audio, video, and document libraries today.

For technical documentation, troubleshooting, and advanced configuration, see the `/docs` directory and `CHANGELOG.md` for detailed feature history.
