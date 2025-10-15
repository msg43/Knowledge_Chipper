# Skipthepodcast.com (Skip the Podcast Desktop)

> Transform audio, video, and documents into structured knowledge with AI-powered analysis

**Version 3.4.0** | **macOS Application** | **Offline-First Design**

## 🆕 What's New in Version 3.4.0 - System 2 Architecture

### System 2: Production-Grade Reliability
- **🗄️ Database-Backed Job Orchestration**: All operations create persistent job records with SQLite WAL mode
- **🔄 Checkpoint/Resume Capability**: Failed jobs resume from their last successful checkpoint automatically
- **💾 Perfect State Persistence**: No more lost work due to crashes or interruptions
- **📊 Complete Audit Trail**: Track every LLM call, token usage, and processing metric in database

### Hardware-Aware Resource Management
- **🖥️ Automatic Hardware Detection**: Adapts to your system tier:
  - Consumer (M1/M2 base): 2 concurrent LLM requests
  - Prosumer (M1/M2 Pro/Max): 4 concurrent LLM requests
  - Enterprise (M1/M2 Ultra): 8 concurrent LLM requests
- **🧠 Dynamic Memory Monitoring**: Throttles at 70% memory usage to prevent crashes
- **⚡ Exponential Backoff**: Intelligent rate limit handling for all providers
- **📈 Real-Time Performance Metrics**: JSON-structured logs with correlation IDs

### Enhanced Observability
- **🏷️ Structured Error Codes**: HIGH/MEDIUM/LOW severity taxonomy per TECHNICAL_SPECIFICATIONS.md
- **📋 Job State Tracking**: Monitor jobs through queued→running→succeeded/failed lifecycle
- **🔍 LLM Request/Response Tables**: Full database tracking with costs and metrics
- **📊 System2Logger**: Structured JSON logging with job_run_id correlation

### GUI Simplified to 7 Tabs
- **1️⃣ Introduction**: Getting started guide
- **2️⃣ Transcribe**: With "Process automatically through entire pipeline" checkbox
- **3️⃣ Summarize**: LLM-powered summarization
- **4️⃣ Review**: SQLite-backed claim editor with tier coloring (A/B/C)
- **5️⃣ Upload**: Cloud storage management
- **6️⃣ Monitor**: Directory watching (renamed from Watcher)
- **7️⃣ Settings**: Configuration and API keys

### Smart Speaker Correction System
- **🔄 HCE Database Sync**: Automatically detects when speaker names are corrected
- **⚡ Background Reprocessing**: Updates all claims and evidence with correct speaker context
- **💰 Cost Transparency**: Shows estimated time and API costs before reprocessing
- **🎯 Manual Control**: "Update HCE Database" button in Speaker Attribution tab
- **📊 Real-Time Progress**: Beautiful dialog with live updates during reprocessing

### JSON Schema Validation
- **📋 Versioned Schemas**: All LLM I/O validated against `/schemas/*.v1.json`
- **🔧 Automatic Repair**: Schema validator fixes common issues
- **✅ Type Safety**: Guaranteed structure for miner and flagship outputs

## 🆕 What's New in Version 3.3.0

### Revolutionary Unified HCE Pipeline
- **🔄 Four-Pass Architecture**: Short Summary → Miner → Flagship Evaluator → Long Summary + Categories
- **📝 Intelligent Summaries**: Pre-mining context and post-evaluation comprehensive analysis
- **📊 Enhanced Scoring**: Importance, novelty, confidence on 1-10 scale
- **🎯 Single-Pass Extraction**: Claims, people, concepts, jargon in one operation
- **📋 Claim Type Classification**: Factual, causal, normative, forecast, definitional
- **🏷️ WikiData Categories**: Automatic topic categorization with confidence scores

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
- **Unified HCE Pipeline**: Advanced four-pass system (Short Summary → Miner → Flagship Evaluator → Long Summary + Categories)
- **Intelligent Summaries**: Pre-mining overview and post-evaluation comprehensive analysis
- **Enhanced JSON Compliance**: Qwen models for reliable structured output
- **Entity Recognition**: People, concepts, jargon, mental models in single pass
- **Intelligent Claim Ranking**: LLM-powered importance, novelty, and confidence scoring
- **WikiData Categories**: Automatic topic categorization for content organization
- **Semantic Deduplication**: Eliminate redundant content

**📊 Knowledge Organization**
- SQLite-first database with optional cloud sync
- Obsidian integration with auto-tagging
- Searchable claim database across all content
- Knowledge maps (MOCs) linking related content
- Multiple export formats (Markdown, YAML, JSON, CSV)

### 🚀 Key Differentiators

1. **Unified HCE Pipeline**: Revolutionary four-pass system with intelligent summaries and category detection
2. **Qwen Model Integration**: Industry-leading JSON compliance and structured output
3. **Intelligent Summaries**: Pre-mining context and post-evaluation comprehensive analysis
4. **WikiData Categories**: Automatic topic categorization for content discovery
5. **97% Voice Accuracy**: Enterprise-grade speaker verification models
6. **Hardware-Optimized Models**: Automatic model selection based on Mac specifications
7. **Apple Silicon Acceleration**: Optimized for M2/M3 with MPS support
8. **Zero Configuration**: Works immediately after installation

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
- **HCE Database Sync**: Automatically update analysis when speaker names change
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

The revolutionary four-pass intelligence engine that replaces traditional summarization:

**🔄 Four-Pass Architecture:**
1. **Short Summary (Pre-Mining)**: Generate 1-2 paragraph contextual overview before extraction begins
2. **Unified Miner**: Single pass extraction of claims, people, concepts, and jargon with claim type classification
3. **Flagship Evaluator**: Comprehensive LLM-powered ranking using short summary for context
4. **Long Summary + Categories**: Generate 3-5 paragraph comprehensive analysis and identify WikiData topic categories

**📊 Advanced Scoring System:**
- **Importance** (1-10): Core relevance and significance
- **Novelty** (1-10): Uniqueness and freshness of information  
- **Confidence** (1-10): Reliability and evidence quality
- **Claim Types**: Factual, causal, normative, forecast, definitional

**🎯 Key Features:**
- **Intelligent Summaries**: Pre-mining context improves evaluation; post-evaluation creates coherent narrative
- **WikiData Categories**: Automatic topic categorization with confidence scores (3-8 categories per episode)
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
- **Smart HCE Sync**: Automatically update analysis database when speaker names are corrected

### Intelligent Processing Pipeline

1. **Content Ingestion** → Universal format support
2. **Transcription** → Whisper with speaker diarization  
3. **Voice Fingerprinting** → 97% accurate speaker identification
4. **LLM Validation** → AI-powered speaker name suggestion
5. **Short Summary** → Pre-mining contextual overview (1-2 paragraphs)
6. **Unified Mining** → Single-pass extraction of all entities with Qwen models
7. **Flagship Evaluation** → Comprehensive LLM ranking using context from short summary
8. **Long Summary** → Post-evaluation comprehensive analysis (3-5 paragraphs)
9. **Category Detection** → WikiData topic identification with confidence scores
10. **Storage** → SQLite database with relationships
11. **Export** → Multiple formats for integration

### Speaker Correction & HCE Sync

When you correct speaker assignments after analysis, the system intelligently updates everything:

**Automatic Workflow:**
1. **Correct Names** → Update speaker assignments in the Speaker Attribution tab
2. **Detect Changes** → System checks if HCE analysis exists for this content
3. **Confirm Update** → Beautiful dialog shows what will be reprocessed with cost/time estimates
4. **Background Processing** → Reprocess claims, evidence, and entities with correct speaker context
5. **Complete Sync** → Database fully updated with corrected speaker attributions

**Key Features:**
- **Non-Blocking**: Reprocessing runs in background with real-time progress
- **Smart Detection**: Only triggers when HCE data actually exists
- **Cost Transparency**: Shows estimated API costs before confirming
- **Complete Reprocessing**: All claims and evidence updated with correct speaker context
- **Manual Control**: Optional "Update HCE Database" button for on-demand updates

This ensures your knowledge base always reflects the correct speaker attributions, even if you fix mistakes after initial processing.

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

## System 2 Architecture

### Job Orchestration
The System 2 architecture introduces database-backed job management for reliability and observability:

**Job Types:**
- `download`: Media file acquisition
- `transcribe`: Audio/video to text conversion
- `mine`: Extract claims, entities, and concepts
- `flagship`: Evaluate and rank extractions
- `upload`: Cloud synchronization
- `pipeline`: End-to-end processing chain

**Key Features:**
- **Persistent State**: All jobs tracked in SQLite with WAL mode
- **Checkpoint/Resume**: Failed jobs resume from last checkpoint
- **Auto-Process Chains**: Automatic progression through pipeline stages
- **Metrics Tracking**: Token usage, latency, and cost per operation

### Resource Management
System 2 automatically adapts to your hardware:

| Hardware Tier | RAM | CPU Cores | Mining Workers | Eval Workers |
|--------------|-----|-----------|----------------|--------------|
| Consumer | <8GB | 2-4 | 2 | 1 |
| Prosumer | 16GB | 8 | 4 | 2 |
| Professional | 32GB | 12+ | 6 | 3 |
| Server | 64GB+ | 16+ | 10 | 5 |

**Memory Protection:**
- Dynamic throttling when memory usage exceeds 70%
- Critical mode at 90% prevents new job starts
- Graceful degradation maintains system stability

### Observability
Comprehensive logging and monitoring:

**Error Taxonomy:**
- `HIGH`: Immediate attention (database errors, schema failures)
- `MEDIUM`: Degraded function (API limits, partial failures)
- `LOW`: Minor issues (cache misses, optional features)

**Monitoring:**
- Job state transitions tracked in database
- LLM token usage and costs per operation
- Memory throttle events and performance metrics
- Structured logs with contextual information

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

## System 2 Architecture

Skipthepodcast.com v3.4.0 introduces System 2, a production-grade architecture designed for reliability and observability:

### Core Components

**1. Job Orchestration (`System2Orchestrator`)**
- Persistent job records with unique IDs
- Checkpoint save/restore for resumability
- Auto-process chaining between pipeline stages
- Failed job retry with exponential backoff

**2. LLM Adapter (`LLMAdapter`)**
- Centralized API management for all providers
- Hardware-aware concurrency limits
- Memory-based throttling (70% threshold)
- Cost tracking and estimation

**3. Database Layer**
- SQLite with WAL mode for concurrency
- New tables: `job`, `job_run`, `llm_request`, `llm_response`
- Optimistic locking with `updated_at` columns
- Complete audit trail of all operations

**4. Structured Logging (`System2Logger`)**
- JSON-formatted logs with correlation IDs
- Error taxonomy (HIGH/MEDIUM/LOW severity)
- Performance metrics on every operation
- Integration with log aggregation tools

**5. Schema Validation**
- Versioned JSON schemas in `/schemas/` directory
- Automatic repair of malformed LLM outputs
- Type safety for all pipeline data

### Benefits

- **Reliability**: Jobs resume automatically after failures
- **Observability**: Complete visibility into system behavior
- **Cost Control**: Track and limit LLM API usage
- **Performance**: Optimized for your specific hardware
- **Maintainability**: Consistent patterns across codebase

For detailed operations guide, see [OPERATIONS.md](OPERATIONS.md).

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
- See OPERATIONS.md for System 2 operational guidance
- Review Architecture Decision Records in `/docs/adr/`

---

**Ready to transform your content into structured knowledge?** Download Skipthepodcast.com and start extracting insights from your audio, video, and document libraries today.

For technical documentation, troubleshooting, and advanced configuration, see the `/docs` directory and `CHANGELOG.md` for detailed feature history.
