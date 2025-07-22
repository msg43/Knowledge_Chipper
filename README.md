# Knowledge System

A comprehensive knowledge management system for macOS that transforms videos, audio files, and documents into organized, searchable knowledge. Perfect for researchers, students, and professionals who work with lots of media content.

**What it does:** Transcribes videos → Generates summaries with intelligent chunking → Creates knowledge maps → Organizes everything automatically.

**✨ Key Features:** Intelligent text chunking (fully automatic) + automatic quality detection with smart retry + advanced process control with pause/resume/cancellation + comprehensive desktop and CLI interfaces.

## Table of Contents

- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [First Run](#first-run)
- [📱 Getting Started Tutorial](#-getting-started-tutorial)
  - [Your First Transcription](#your-first-transcription)
  - [Your First Summary](#your-first-summary)
  - [Understanding Your Output](#understanding-your-output)
- [🖥️ User Interface Guide](#️-user-interface-guide)
  - [Desktop GUI (Recommended)](#desktop-gui-recommended)
  - [Command Line Interface](#command-line-interface)
  - [Command Line Basics](#command-line-basics)
- [⭐ Core Features](#-core-features)
  - [What Can It Process?](#what-can-it-process)
  - [Main Operations](#main-operations)
  - [Output Types](#output-types)
  - [Intelligent Text Chunking](#-intelligent-text-chunking)
  - [Intelligent Quality Detection & Automatic Retry](#-intelligent-quality-detection--automatic-retry)
- [🎯 Common Use Cases](#-common-use-cases)
  - [YouTube Video Processing](#youtube-video-processing)
  - [Local File Processing](#local-file-processing)
  - [Batch Processing](#batch-processing)
  - [Automated Monitoring](#automated-monitoring)
- [⚙️ Configuration & Settings](#️-configuration--settings)
  - [Essential Settings](#essential-settings)
  - [API Keys Setup](#api-keys-setup)
  - [Hardware-Aware Performance Options](#hardware-aware-performance-options)
  - [Quality Detection & Retry Settings](#quality-detection--retry-settings)
  - [Customization Options](#customization-options)
- [🔧 Troubleshooting](#-troubleshooting)
  - [Common Issues](#common-issues)
  - [Performance Tips](#performance-tips)
  - [Getting Help](#getting-help)
- [🚀 Advanced Features](#-advanced-features)
  - [Custom Templates](#custom-templates)
  - [Progress Reporting](#progress-reporting)
  - [Process Control & Cancellation](#️-process-control--cancellation)
- [💻 Command Line Reference](#-command-line-reference)
  - [Basic Commands](#basic-commands)
  - [Advanced Commands](#advanced-commands)
  - [Batch Operations](#batch-operations)
- [🛠️ Development](#️-development)
  - [Project Structure](#project-structure)
  - [Running Tests](#running-tests)
  - [Contributing](#contributing)
- [📚 Technical Details](#-technical-details)
  - [Supported File Types](#supported-file-types)
  - [Performance Considerations](#performance-considerations)
  - [System Architecture](#system-architecture)
  - [Intelligent Chunking System](#intelligent-chunking-system)
  - [Process Control System](#process-control-system)
- [📄 License & Credits](#-license--credits)

## 🚀 Quick Start

### Prerequisites

- **macOS Sonoma or later** (optimized for Apple Silicon)
- **Python 3.9+** (check with `python3 --version`)
- **Git** (for installation)
- **16GB+ RAM recommended** for large files

### Installation

1. **Clone and enter the project:**
```bash
git clone <repository-url>
cd App5
```

2. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install everything:**
```bash
pip install -r requirements.txt
pip install -e .
```

4. **Set up configuration:**
```bash
cp config/settings.example.yaml config/settings.yaml
```

### First Run

**Launch the desktop app:**
```bash
python -m knowledge_system.gui
```

🎉 **Success!** You should see the Knowledge System desktop application. If you get an error, see [Troubleshooting](#-troubleshooting).

## 📱 Getting Started Tutorial

### Your First Transcription

Let's transcribe a YouTube video to get you started:

1. **Open the desktop app** (see [First Run](#first-run) above)
2. **Go to the "YouTube Extraction" tab**
3. **Paste a YouTube URL** (try: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
4. **Click "Start Processing"**
5. **Wait for completion** - you'll see progress updates

**What happens:** The system downloads the video, extracts audio, transcribes it using AI, and saves a markdown file with the transcript.

### Your First Summary

Now let's create a summary of your transcript:

1. **Go to the "Summarization" tab**
2. **Click "Browse"** and select your transcript file (`.md` file from step above)
3. **Choose a summary style** (try "General" for your first run)
4. **Click "Start Summarization"**
5. **Wait for completion**

**What happens:** The system uses AI to analyze your transcript and create a structured summary with key points.

### Understanding Your Output

After processing, you'll find files in your output directory:

```
Your_Output_Folder/
├── dQw4w9WgXcQ_transcript.md      # Full transcript
├── dQw4w9WgXcQ_summary.md         # AI-generated summary
├── Thumbnails/                     # Video thumbnails
│   └── dQw4w9WgXcQ_thumbnail.jpg
└── Reports/                        # Processing reports
    └── transcription_2024-01-15_14-30-45.md
```

**🎯 Pro Tip:** Open the `.md` files in any text editor or markdown viewer to see your results!

## 🖥️ User Interface Guide

### Desktop GUI (Recommended)

The desktop app has tabs for different operations:

- **🎬 YouTube Extraction**: Process YouTube videos and playlists
- **🎵 Audio Transcription**: Process local audio/video files
- **📝 Summarization**: Create summaries from transcripts
- **🗺️ Maps of Content**: Generate knowledge maps
- **👁️ File Watcher**: Automatically process new files
- **⚙️ Settings**: Configure API keys, hardware performance options, and preferences

**Navigation:** Click tabs to switch between operations. All settings are saved automatically.

### Command Line Interface

For automation and scripting, the system provides a comprehensive CLI that works alongside the GUI:

### Command Line Basics

For automation and scripting:

```bash
# Quick transcription
knowledge-system transcribe --input "video.mp4"

# Quick summary
knowledge-system summarize "transcript.md"

# Get help
knowledge-system --help
```

## ⭐ Core Features

### What Can It Process?

**📹 Video & Audio:**
- YouTube videos and playlists
- Local files: MP4, MP3, WAV, WEBM, etc.
- Any audio/video format supported by FFmpeg

**📄 Documents:**
- PDF files
- Markdown files
- Plain text files

### Main Operations

1. **🎯 Transcription**: Convert speech to text using AI
2. **📝 Summarization**: Generate structured summaries
3. **🗺️ Maps of Content**: Create knowledge organization systems
4. **👁️ Monitoring**: Watch folders for automatic processing

### Maps of Content (MOC) - Deep Dive

**What it does:** Transforms your collection of markdown files into a structured, cross-referenced knowledge base with zero manual effort.

#### **📋 Step-by-Step Process**

**Phase 1: Setup**
- Add markdown files (`.md` or `.txt`) via GUI or command line
- Configure depth (1-5), theme, and optional custom templates
- Choose whether to extract beliefs and claims

**Phase 2: Content Analysis** 
For each file, the system runs **5 parallel extraction processes**:

1. **👥 People Extraction**
   - Finds names: "John Smith", "Dr. Jane Doe", "Alice P. Johnson"
   - Filters false positives (generic terms)
   - Tracks mention frequency and file locations

2. **🏷️ Tag Extraction**
   - Hashtags: `#ai`, `#technology`
   - Wiki links: `[[concept]]`
   - Bold terms: `**important**`
   - Counts usage across files

3. **🧠 Mental Models Extraction**
   - Frameworks: "Pareto principle", "Systems thinking model"
   - Definitions: `**Framework** - explanation`
   - Theoretical concepts with context

4. **📖 Jargon/Terminology Extraction**
   - Acronyms: API, ML, AI
   - Definitions: `**API** - Application Programming Interface`
   - Technical terms with explanations

5. **💭 Beliefs Extraction** (optional)
   - Claims: "I believe...", "Research shows..."
   - Evidence pairs: `**Claim** - supporting evidence`
   - Confidence scoring (0.0-1.0)

**Phase 3: Knowledge Organization**
- Removes duplicates across files
- Sorts by relevance and frequency
- Creates cross-references and relationships
- Applies organizational themes (topical/chronological/hierarchical)

**Phase 4: File Generation**
Creates **6 interconnected files**:

- **`MOC.md`** - Main overview (uses your custom template if provided)
- **`People.md`** - Directory with mention counts: "John Smith (mentioned 3 times)"
- **`Tags.md`** - Topic taxonomy: "#ai (used in 5 files)"
- **`Mental Models.md`** - Framework definitions and applications
- **`Jargon.md`** - Terminology glossary with context
- **`beliefs.yaml`** - Structured belief data with confidence scores

#### **🎯 What Gets Analyzed**

**Example Input Content:**
```markdown
John Smith discusses the Pareto principle in #productivity contexts.
**API** - Application Programming Interface for system integration.
I believe that 80/20 thinking transforms how we prioritize work.
```

**Extracted Results:**
- **People**: John Smith (1 mention)
- **Mental Models**: Pareto principle
- **Tags**: #productivity  
- **Jargon**: API - Application Programming Interface
- **Beliefs**: "80/20 thinking transforms prioritization" (confidence: 0.8)

#### **📊 Custom Templates**

Control your MOC output format with custom templates:

```markdown
# Knowledge Map - {theme} Organization
Generated: {generated_at} | Files: {source_files_count}

## Key People ({people_count} found)
{people_list}

## Important Topics ({tags_count} found)  
{tags_list}

## Core Concepts ({mental_models_count} found)
{mental_models_list}
```

**Available Placeholders:**
- `{generated_at}`, `{theme}`, `{depth}`, `{source_files_count}`
- `{people_count}`, `{tags_count}`, `{mental_models_count}`, `{jargon_count}`, `{beliefs_count}`
- `{people_list}`, `{tags_list}`, `{mental_models_list}`, `{jargon_list}`, `{beliefs_list}`, `{source_files_list}`

#### **💡 Key Benefits**

- **Zero Manual Work**: No tagging or categorization needed
- **Multiple Perspectives**: 6 different views of the same knowledge
- **Cross-Referenced**: Everything links to everything else
- **Scalable**: Works with 1 file or 1000+ files
- **Customizable**: Templates control output format
- **Standards-Compliant**: Generates proper Markdown and YAML

#### **🚀 Usage Examples**

**GUI:** Maps of Content tab
1. Add markdown files or folders
2. Set depth and title
3. Optional: Add custom template
4. Click "Start MOC Generation"

**CLI:**
```bash
# Basic MOC generation
knowledge-system moc *.md

# With custom template and theme
knowledge-system moc documents/ --template my_template.txt --theme hierarchical --depth 4

# Skip belief extraction
knowledge-system moc files/*.md --no-include-beliefs
```

**Perfect for:** Research notes, meeting transcripts, knowledge bases, documentation collections, academic papers, interview transcripts.

### Output Types

- **Transcripts**: Full text with timestamps
- **Summaries**: Key points and insights with intelligent chunking
- **Knowledge Maps**: People, tags, concepts, and relationships
- **Reports**: Detailed processing logs

### 🧠 Intelligent Text Chunking

**Automatic Processing for Documents of Any Size**

The system automatically handles documents that exceed AI model context windows through intelligent chunking that works completely behind the scenes:

**🔧 Fully Automatic Operation:**
- **Zero Configuration**: No settings needed - just works automatically
- **Smart Detection**: Automatically detects when chunking is needed based on document size and model limits
- **Intelligent Boundaries**: Automatically chooses optimal split points (paragraphs → sentences → words)
- **Context Preservation**: Automatically calculates optimal overlap to maintain meaning across chunks
- **Seamless Results**: Automatically reassembles chunks into coherent final summaries

**🧮 Automatic Calculations (Behind the Scenes):**
- ✅ **Optimal chunk size** based on model context window
- ✅ **Safety margins** (15% buffer for prompt variations)
- ✅ **Overlap tokens** (10% of chunk size, min 100, max 500)
- ✅ **Minimum chunk size** (20% of max, ensuring quality)

**📊 Universal Model Support:**
- **GPT-4 Turbo/4o**: 128,000 tokens - automatically detected
- **Claude 3**: 200,000 tokens - automatically detected
- **GPT-4**: 8,192 tokens - automatically detected  
- **Local models**: Context windows automatically detected per model

**🎯 Key Benefits:**
- **Just Works**: Process transcripts of any length without thinking about it
- **Always Optimal**: System chooses best strategy for each document and model combination
- **Invisible Complexity**: Advanced chunking happens transparently
- **Consistent Quality**: Maintains summary quality regardless of document size
- **Future-Proof**: Automatically adapts to new models and context windows

### 🎯 Intelligent Quality Detection & Automatic Retry

**Automatic Quality Validation with Smart Recovery**

The system includes advanced quality detection that automatically identifies transcription issues and intelligently retries with better models when needed:

**🔍 Automatic Quality Analysis:**
- **Duration-Based Validation**: Analyzes words-per-minute ratio against audio length
- **Content Pattern Detection**: Identifies repetitive text ("you you you") and hallucinations
- **Silence Handling**: Detects when models get "stuck" on silent segments
- **Model-Specific Validation**: Adjusts quality thresholds based on model capabilities

**🔄 Smart Retry Logic:**
- **Model Progression**: Automatically upgrades tiny→base→small→medium→large when quality fails
- **Preserves User Choice**: Always starts with user's selected model
- **Intelligent Fallback**: Only retries when quality validation detects genuine issues
- **Single Retry Default**: Balances quality improvement with processing time

**⚡ Performance vs Quality Controls:**

**Three Operating Modes:**

1. **🚀 Performance Mode** (Fastest)
   ```
   ☐ Enable automatic quality retry
   ```
   - **Speed**: Fastest possible processing
   - **Behavior**: Returns results with quality warnings
   - **Best for**: Quick drafts, testing, speed-critical workflows

2. **🎯 Balanced Mode** (Default)
   ```
   ☑️ Enable automatic quality retry
   Max Retry Attempts: 1
   ```
   - **Speed**: 2-3x slower if retry needed
   - **Behavior**: One automatic model upgrade when quality fails
   - **Best for**: Most users wanting reliable quality

3. **🏆 Maximum Quality Mode** (Highest Accuracy)
   ```
   ☑️ Enable automatic quality retry  
   Max Retry Attempts: 2-3
   ```
   - **Speed**: Slowest but highest accuracy
   - **Behavior**: Multiple model upgrades until success
   - **Best for**: Critical transcriptions, difficult audio

**🧮 Quality Metrics Analyzed:**
- **Words Per Minute**: Detects insufficient transcription (e.g., 18 WPM for 40-min audio)
- **Repetition Patterns**: Identifies stuck loops and hallucinations
- **Content Coherence**: Validates realistic speech patterns
- **Language Consistency**: Ensures proper language detection

**💡 Intelligent Warnings:**
When retries are disabled and quality issues are detected:
```
✅ Transcription completed with quality warning
⚠️  Low word density detected (18.5 WPM, expected >40 WPM)
🎯 Consider enabling quality retry or trying a larger model
```

**🎛️ User Control:**
- **GUI Controls**: Easy enable/disable in Audio Transcription tab
- **Configurable Attempts**: 0-3 retry attempts (0 = performance mode)
- **Real-time Feedback**: See retry progress and model upgrades
- **Persistent Settings**: Quality preferences saved automatically

**📊 Quality vs Performance Examples:**
```
User selects "tiny" model for speed:

Performance Mode (No Retry):
├── Try "tiny" model → Quality warning → Done (3 seconds)
└── Result: Fast but may need manual retry

Balanced Mode (1 Retry):
├── Try "tiny" model → Quality fails → Retry "base" → Success (9 seconds)  
└── Result: 3x slower but higher quality

Maximum Quality (2 Retries):
├── Try "tiny" → Fails → "base" → Fails → "small" → Success (15 seconds)
└── Result: 5x slower but maximum accuracy
```

**🎯 Key Benefits:**
- **Automatic Quality Assurance**: Catches transcription failures before you see them
- **User Control**: Choose your own speed vs quality tradeoff
- **Transparent Operation**: Clear feedback about retry decisions and quality issues
- **Intelligent Resource Usage**: Only retries when genuinely needed
- **Future-Proof**: Adapts quality thresholds as models improve

## 🎯 Common Use Cases

### YouTube Video Processing

**Perfect for:** Lectures, podcasts, tutorials, interviews

```bash
# Single video
knowledge-system transcribe --input "https://youtube.com/watch?v=VIDEO_ID"

# Entire playlist
knowledge-system transcribe --input "https://youtube.com/playlist?list=PLAYLIST_ID"
```

**GUI:** Use the "YouTube Extraction" tab for the easiest experience.

### Local File Processing

**Perfect for:** Recorded meetings, audio notes, video files

```bash
# Single file
knowledge-system transcribe --input "meeting.mp4"

# Multiple files
knowledge-system process ./recordings/ --recursive
```

**GUI:** Use the "Audio Transcription" tab and browse to your files.

### Batch Processing

**Perfect for:** Large collections of content

```bash
# Process everything in a folder
knowledge-system process ./videos/ --recursive --transcribe --summarize

# Process specific file types
knowledge-system process ./content/ --patterns "*.mp4" "*.pdf"
```

**GUI:** Use "File Watcher" tab to automatically process new files.

### Automated Monitoring

**Perfect for:** Ongoing content processing

**GUI:** Use "File Watcher" tab to set up automated processing that monitors folders and automatically processes new files as they appear.

## ⚙️ Configuration & Settings

### Essential Settings

**In the desktop app:**
1. Go to "Settings" tab
2. Set your **output directory** (where files are saved)
3. Add **API keys** for AI services (see below)

### API Keys Setup

For AI summarization, you need API keys:

**OpenAI (Recommended):**
1. Go to https://platform.openai.com/account/api-keys
2. Create a new key
3. Add it in Settings tab → "OpenAI API Key"

**Anthropic (Alternative):**
1. Go to https://console.anthropic.com/
2. Create a new key
3. Add it in Settings tab → "Anthropic API Key"

### Hardware-Aware Performance Options

The Knowledge System automatically detects your Apple Silicon hardware and optimizes performance accordingly:

**Performance Profiles:**
- **Auto**: Automatically selects optimal settings based on your hardware
- **Battery Saver**: Minimal resource usage for mobile devices
- **Balanced**: Good performance/efficiency balance (default for most systems)
- **High Performance**: Maximizes within thermal limits
- **Maximum Performance**: Pushes hardware to absolute limits (recommended for M3 Ultra systems)

**Hardware Detection:**
- Automatically detects M1/M2/M3 variants (including Pro, Max, Ultra)
- Identifies CPU cores, GPU cores, Neural Engine, and memory configuration
- Optimizes batch sizes, concurrency, and model selection
- Displays real-time performance characteristics

**Performance Optimizations:**
- **MPS Acceleration**: Leverages Apple Silicon GPU for faster processing
- **Smart Batch Sizing**: Adjusts batch sizes based on available memory
- **Concurrent Processing**: Optimizes parallel file processing
- **Model Selection**: Chooses appropriate Whisper model for your hardware

**For High-End Systems (M3 Ultra + 128GB RAM):**
- Up to 16 concurrent file processing (vs 4 default)
- 64-item batch sizes (vs 16 default)
- Large-v3 Whisper model for maximum accuracy
- Optimized for large-scale content processing

**Manual Overrides Available:**
- Override Whisper model selection
- Force specific device usage (CPU/MPS/CUDA)
- Custom batch sizes and concurrency limits
- Expert-level hardware acceleration controls

### Quality Detection & Retry Settings

**Configure Quality vs Performance Tradeoff**

The Audio Transcription tab includes advanced quality controls that let you balance processing speed against transcription accuracy:

**🎛️ Quality Retry Controls:**
- **Enable Automatic Quality Retry**: ☑️/☐ toggle for automatic retry on quality failures
- **Max Retry Attempts**: 0-3 attempts (0 = performance mode, 1 = balanced, 2-3 = maximum quality)
- **Smart UI**: Retry attempts automatically disabled when quality retry is turned off
- **Persistent Settings**: Quality preferences saved and restored automatically

**🔧 Configuration Examples:**

**Speed-First Setup (Content Creators):**
```
☐ Enable automatic quality retry
Max Retry Attempts: 0 (disabled)
Model: tiny (for speed)
```
- **Result**: 3-second processing for 30-second video
- **Use case**: Quick draft transcripts, rough content review

**Balanced Setup (Most Users):**
```
☑️ Enable automatic quality retry  
Max Retry Attempts: 1
Model: base (recommended)
```
- **Result**: Automatic upgrade to "small" if quality fails
- **Use case**: Reliable transcripts for meetings, lectures

**Quality-First Setup (Research/Academic):**
```
☑️ Enable automatic quality retry
Max Retry Attempts: 2-3  
Model: small or medium
```
- **Result**: Multiple model upgrades until highest quality achieved
- **Use case**: Critical transcriptions, difficult audio, academic research

**📊 Quality Validation Metrics:**
- **Words Per Minute Analysis**: Automatically detects suspiciously low transcription rates
- **Repetition Detection**: Identifies "you you you" and similar failure patterns
- **Duration Correlation**: Validates transcription length against audio duration
- **Silence Handling**: Catches models stuck on quiet segments

**💡 Smart Recommendations:**
The system provides automatic recommendations based on your hardware:
- **High-end systems**: Can afford quality mode with minimal impact
- **Moderate hardware**: Balanced mode recommended for best experience
- **Low-end systems**: Performance mode to avoid excessive processing times

**🎯 Real-World Impact:**
```bash
# 40-minute lecture transcription comparison:

Performance Mode:
├── "tiny" model only → 1,200 words (suspected failure)
├── Processing time: 2 minutes
└── Quality warning: 30 WPM (expected 120+ WPM)

Balanced Mode (1 retry):
├── "tiny" model fails → Auto-retry "base" → 4,800 words  
├── Processing time: 6 minutes
└── Success: 120 WPM (normal range)

Quality Mode (2 retries):
├── "tiny" fails → "base" fails → "small" succeeds → 5,200 words
├── Processing time: 12 minutes  
└── Highest accuracy: 130 WPM with speaker context
```

**🎛️ Access These Settings:**
1. Open the Knowledge System desktop app
2. Go to "Audio Transcription" tab  
3. Find "Quality vs Performance Controls" in the Settings section
4. Configure retry behavior and maximum attempts
5. Settings are saved automatically for future sessions

### CUDA & GPU Acceleration

The Knowledge System provides comprehensive GPU acceleration support across all platforms, with intelligent hardware detection and automatic optimization.

**Cross-Platform GPU Support:**
- **NVIDIA CUDA**: RTX 20/30/40 series, Tesla, Quadro cards
- **Apple Silicon**: M1/M2/M3 with Metal Performance Shaders (MPS)
- **AMD ROCm**: Radeon RX 6000/7000 series (experimental)
- **Intel GPU**: Arc and integrated graphics (experimental)

**Automatic Hardware Detection:**
- Detects GPU count, names, and VRAM capacity
- Identifies CUDA/driver versions and compute capabilities
- Recognizes Tensor Core support for RTX cards
- Provides intelligent device recommendations based on workload

**CUDA Performance Benefits:**
- **5-10x faster** transcription compared to CPU processing
- **Large model support** with sufficient VRAM (8GB+ recommended)
- **Batch processing optimization** for multiple files
- **Tensor Core acceleration** on RTX 20/30/40 series

**Performance Examples:**
```
CPU (16-core):           1x baseline performance
Apple Silicon MPS:       3-5x faster than CPU
NVIDIA RTX 4090:         8-12x faster than CPU
Multi-GPU CUDA:          15-20x faster than CPU
```

**Installation & Setup:**

For enhanced CUDA features, install optional dependencies:
```bash
# Install CUDA-enhanced version
pip install -e ".[cuda]"
```

**Automatic Device Selection:**
- **Auto mode**: Intelligently selects optimal device based on:
  - Available VRAM vs model requirements
  - Tensor Core capabilities
  - Current GPU utilization
  - Batch size and file count
- **Manual override**: Force specific devices (cuda:0, cuda:1, mps, cpu)

**CUDA-Specific Optimizations:**
- **VRAM-aware model selection**: Automatically chooses largest model that fits
- **Multi-GPU support**: Distributes workload across available GPUs
- **Memory management**: Prevents out-of-memory errors with intelligent batching
- **Tensor Core utilization**: Automatic mixed-precision for RTX cards

**Hardware Requirements:**
- **Minimum**: NVIDIA GPU with 4GB+ VRAM (GTX 1660 or better)
- **Recommended**: RTX 3070/4070 with 8GB+ VRAM
- **Optimal**: RTX 4090 with 24GB VRAM for large-scale processing

**Performance Profiles (CUDA-Enhanced):**
- **High Performance**: Uses large-v3 model with 2x batch sizes on high-VRAM GPUs
- **Maximum Performance**: Pushes CUDA GPUs to maximum throughput
- **Multi-GPU**: Automatically distributes across all available CUDA devices

**GUI Integration:**
The Settings tab displays detailed hardware information:
- GPU names and VRAM amounts
- CUDA/driver versions
- Tensor Core availability (🟢/🔴 indicators)
- Real-time device recommendations
- Performance preview with hardware-specific optimizations

### Customization Options

- **Transcription Models**: Choose quality vs. speed
- **Summary Styles**: Bullet points, academic, executive
- **Output Formats**: Markdown, plain text, SRT subtitles
- **Processing Options**: Auto-processing, file patterns

## 🔧 Troubleshooting

### Common Issues

**❌ "API key not found"**
- **Solution**: Add your API key in Settings tab
- **Details**: OpenAI or Anthropic API key required for summarization

**❌ "FFmpeg not found"**
- **Solution**: Install FFmpeg: `brew install ffmpeg`
- **Details**: Required for audio/video processing

**❌ "Permission denied"**
- **Solution**: Check file permissions and output directory access
- **Details**: Ensure you have write access to output folder

**❌ "Out of memory"**
- **Solution**: Use smaller transcription model or process fewer files at once
- **Details**: Large files need more RAM

**⚠️ "Transcription quality warning"**
- **Explanation**: Automatic quality detection found potential issues (low word density, repetitive text)
- **Solution**: Enable quality retry for automatic improvement, or manually try a larger model
- **Details**: Not an error - transcript was generated but may need improvement

**🔄 "Retrying transcription with improved model"**
- **Explanation**: Quality retry automatically upgrading from smaller to larger model
- **Normal behavior**: System detected quality issues and is attempting to improve results
- **Details**: Processing time will increase but quality should improve significantly

**❌ "All transcription attempts failed"**
- **Solution**: Check audio quality, try manual model selection, or disable quality validation temporarily
- **Details**: Multiple retry attempts failed - audio may be severely corrupted or inaudible

### Performance Tips

- **Use hardware detection** (Settings → "Detect Hardware") to optimize for your system
- **Select appropriate performance profile** (Auto, Balanced, High Performance, or Maximum Performance)
- **For high-end systems (M3 Ultra)**: Use Maximum Performance mode for best results
- **Override settings manually** if needed: batch sizes, concurrency, model selection
- **Monitor performance preview** in Settings tab to see current optimizations
- **Close other applications** when processing large files

**Quality vs Performance Optimization:**
- **For maximum speed**: Disable automatic quality retry and use "tiny" model
- **For balanced workflow**: Use default settings (quality retry enabled, 1 attempt)
- **For critical accuracy**: Enable 2-3 retry attempts and start with "base" or "small" model
- **Large batch processing**: Consider performance mode to avoid cumulative retry delays
- **Quality troubleshooting**: Temporarily disable quality retry to isolate audio vs validation issues

### Getting Help

1. **Check the logs** in the GUI console output
2. **Look at processing reports** (saved automatically)
3. **Try with a smaller test file** first
4. **Check your API key** configuration

## 🚀 Advanced Features

### Custom Templates

Customize how summaries and knowledge maps are generated:

```bash
# Use custom summary template
knowledge-system summarize document.txt --template custom_prompt.txt

# Use custom MOC template
knowledge-system moc *.md --template custom_moc_template.txt
```

### Progress Reporting

All operations generate detailed reports saved in your Reports folder with:
- Processing statistics
- Success/failure details
- Output file locations
- Performance metrics

### 🎛️ Process Control & Cancellation

**Full Control Over Long-Running Operations**

Advanced cancellation and process control for managing large workloads:

**🔄 Pause & Resume:**
- **Real-time Control**: Pause/resume any operation mid-process
- **Safe Checkpoints**: Operations pause at safe breakpoints
- **Memory Preservation**: Maintains progress state during pause
- **GUI Integration**: One-click pause/resume in desktop app

**⏹️ Graceful Cancellation:**
- **Smart Cancellation**: 10-second graceful shutdown before force stop
- **Progress Preservation**: Saves completed work before cancelling
- **User Confirmation**: Prevents accidental cancellation
- **Background Processing**: Option to continue cancelled operations in background

**🚨 Hang Detection & Recovery:**
- **Automatic Detection**: Monitors for stalled operations (60+ seconds)
- **Recovery Options**: Cancel, wait longer, or ignore hung operations
- **Timeout Configuration**: Customizable hang detection sensitivity
- **Force Recovery**: Emergency force-stop for completely stuck processes

**💡 Control Features:**
- **Cancel Buttons**: Visible in all progress widgets during processing
- **Thread-Safe Operations**: Safe cancellation without data corruption
- **Operation Types**: Transcription, summarization, extraction, MOC generation
- **Hang Levels**: Lenient (5min), Moderate (2min), Strict (30s), Aggressive (10s)

**🎯 Use Cases:**
- Stop runaway processing jobs
- Pause long operations during system maintenance
- Recover from stuck API calls or network issues
- Manage processing priority in multi-task environments

## 💻 Command Line Reference

### Basic Commands

```bash
# Transcribe a file
knowledge-system transcribe --input "file.mp4"

# Summarize a transcript
knowledge-system summarize "transcript.md"

# Generate knowledge map
knowledge-system moc transcript1.md transcript2.md

# Process everything
knowledge-system process ./videos/ --recursive
```

### Advanced Commands

```bash
# YouTube playlist with custom model
knowledge-system transcribe --input "playlist_url" --model large

# Batch processing with specific patterns
knowledge-system process ./content/ --patterns "*.mp4" "*.pdf" --recursive

# Custom templates for summaries and MOCs
knowledge-system summarize document.txt --template custom_prompt.txt
knowledge-system moc *.md --template custom_moc_template.txt

# Large documents (intelligent chunking happens automatically)
knowledge-system summarize large_transcript.md  # Chunking applied automatically when needed
```

### Batch Operations

```bash
# Process folder recursively with full pipeline
knowledge-system process ./videos/ --recursive --transcribe --summarize --moc

# Batch transcription from CSV file
knowledge-system transcribe --batch-urls urls.csv --output ./transcripts/

# Recursive summarization with custom patterns
knowledge-system summarize ./documents/ --recursive --patterns "*.pdf" "*.md" "*.txt"
```

## 🛠️ Development

### Project Structure

```
App5/
├── src/knowledge_system/           # Main package
│   ├── processors/                 # Input processors
│   ├── services/                   # Core services
│   ├── gui/                        # User interfaces
│   └── utils/                      # Utilities
├── tests/                          # Test suite
├── config/                         # Configuration
└── data/                           # Data storage
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=knowledge_system

# Run specific test
pytest tests/unit/test_config.py -v
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📚 Technical Details

### Supported File Types

**Audio/Video:** MP4, WEBM, MP3, WAV, M4A, FLAC, OGG, AVI, MOV, MKV
**Documents:** PDF, TXT, MD, MARKDOWN

### Performance Considerations

- **Automatic hardware detection** for M1/M2/M3 Apple Silicon variants
- **Performance profiles** (Auto, Balanced, High Performance, Maximum Performance)
- **Intelligent batch sizing** based on available memory and CPU cores
- **MPS acceleration** optimized for Apple Silicon GPU
- **Adaptive concurrency** scaling with hardware capabilities
- **Memory-optimized** processing for long audio files

### System Architecture

- **Modular processors** for different input types
- **Plugin-based services** for AI providers
- **Queue-based processing** for reliability
- **Progress tracking** throughout pipeline

### Intelligent Chunking System

**Fully Automatic Implementation:**

- **Token Estimation**: Uses tiktoken for accurate token counting across different models
- **Context Window Detection**: Automatically detects model context limits (8K-200K tokens)
- **Smart Boundary Detection**: Preserves semantic integrity using regex patterns for sentences/paragraphs
- **Automatic Overlap Management**: Intelligently calculates optimal token overlap (50-1000) to maintain context
- **Seamless Reassembly**: Intelligent merging of chunk summaries with transition handling

**Automatic Strategy Selection:**
```python
# System automatically chooses optimal strategy for each document:
Priority 1: Paragraph boundaries (preserves document structure)
Priority 2: Sentence boundaries (maintains semantic integrity)  
Priority 3: Word boundaries (fallback for dense text)

# Selection logic is completely automatic based on:
# - Document content structure
# - Model context window
# - Optimal chunk sizes
```

**Performance Optimizations:**
- **Parallel Processing**: Chunks processed concurrently when possible
- **Memory Management**: Streaming for large inputs to prevent memory overflow
- **Caching**: Reuses tokenization results for repeated operations
- **Safety Margins**: 10-20% buffer to account for prompt variation and output estimation

### Process Control System

**Cancellation Architecture:**

- **CancellationToken**: Thread-safe signaling system using threading.Event
- **Graceful Shutdown**: 10-second timeout with force-stop fallback
- **Progress Preservation**: Checkpoint-based state saving during cancellation
- **Worker Thread Management**: Safe termination without resource leaks

**Hang Detection:**
```python
# Timeout configurations by operation type
TRANSCRIPTION: 300 seconds (5 minutes)
SUMMARIZATION: 120 seconds (2 minutes) 
EXTRACTION: 180 seconds (3 minutes)
MOC_GENERATION: 240 seconds (4 minutes)
```

**Thread Safety:**
- **Lock-based synchronization** for progress updates
- **Atomic operations** for cancellation state changes
- **Queue-based communication** between UI and worker threads
- **Memory barriers** for cross-thread variable access

## 📄 License & Credits

**License:** MIT License - see [LICENSE](LICENSE) file

**Built with:**
- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube processing
- [PyQt6](https://pypi.org/project/PyQt6/) for desktop GUI
- [Click](https://click.palletsprojects.com/) for command-line interface

---

🚀 **Ready to get started?** Jump to [Quick Start](#-quick-start) and process your first file in minutes! 


## APPENDIX

### Why MPS Over CoreML for Large File Operations

The Knowledge System is designed to prioritize **Metal Performance Shaders (MPS)** over CoreML for transcription workloads, especially on high-end Apple Silicon systems. This architectural decision was made after careful analysis of performance characteristics across different hardware configurations and use cases.

#### **Hardware Utilization Comparison**

##### **Neural Engine Limitations (CoreML)**
- **Memory Constraint**: Limited to ~1GB dedicated ANE memory
- **Batch Processing**: Optimal for 1-4 files simultaneously
- **Sequential Processing**: More sequential than parallel processing
- **Memory Pressure**: Hits limits with 8-16+ files regardless of system RAM

##### **GPU Powerhouse (MPS)**
- **Unified Memory**: Scales with system RAM (8GB to 128GB+)
- **Parallel Processing**: True batch processing of 10-50+ files
- **Sustained Performance**: Desktop thermal design prevents throttling
- **Memory Bandwidth**: Higher throughput for large data transfers

#### **Performance Crossover Points**

The decision becomes more pronounced with high-end hardware:

**Standard M2 Pro (16GB RAM):**
- **CoreML optimal**: 1-3 files
- **MPS optimal**: 4+ files
- **Crossover point**: ~4 files

**M3 Ultra (128GB RAM):**
- **CoreML optimal**: 1-3 files (unchanged - ANE memory doesn't scale)
- **MPS optimal**: 5-50+ files
- **Crossover point**: ~3 files

#### **Specific Advantages for Large Operations**

##### **1. Memory Scalability**
```
CoreML (ANE):     1GB limit    (fixed regardless of system RAM)
MPS (GPU):        8-128GB      (scales with system configuration)
```

##### **2. Batch Processing Efficiency**
- **CoreML**: Processes files sequentially through 1GB memory bottleneck
- **MPS**: True parallel processing utilizing full system memory
- **Result**: 5-10x faster processing for large batches

##### **3. Long Audio File Handling**
- **CoreML**: Struggles with >1 hour audio files due to memory constraints
- **MPS**: Handles 10+ hour files efficiently with proper memory management
- **Transcription timeout**: Extended to 1 hour to accommodate large files

##### **4. Hardware Utilization**
**M3 Ultra Specifications:**
- **76 GPU cores** vs 32 ANE cores
- **800GB/s memory bandwidth** vs ANE's limited bandwidth
- **Sustained performance** vs ANE thermal limitations

#### **Real-World Performance Benefits**

##### **Large Batch Processing**
```bash
# Processing 20 video files (1 hour each)
CoreML approach:  ~8-12 hours  (sequential bottleneck)
MPS approach:     ~2-3 hours   (parallel processing)
```

##### **Memory Requirements**
```
Single 2-hour video file:
CoreML:  Requires chunking/streaming (complexity)
MPS:     Processes in single pass (simplicity)
```

##### **System Resource Utilization**
- **CoreML**: Underutilizes system capabilities on high-end hardware
- **MPS**: Scales performance with hardware investment
- **Future-proofing**: Performance improves with hardware upgrades

#### **Development Philosophy**

This system is designed for **knowledge workers and researchers** who:
- Process large volumes of content (lectures, meetings, podcasts)
- Want maximum performance from their hardware investment
- Need reliable batch processing capabilities
- Value processing speed over power efficiency

#### **When CoreML Might Be Better**

CoreML still has advantages for:
- **Single file processing** (< 30 minutes)
- **Mobile/battery-powered usage** (MacBook Air)
- **Power-efficient processing** (ANE uses less energy)
- **Specific model optimizations** (if available)

#### **Technical Implementation**

The system automatically detects Apple Silicon and configures MPS acceleration:

```python
# Simplified architecture decision
if platform.machine() == 'arm64':  # Apple Silicon
    if batch_size > 3 or file_duration > 60_minutes:
        use_mps_acceleration = True
    else:
        use_coreml_acceleration = True
```

#### **Future Considerations**

As Apple continues to improve both technologies:
- **CoreML**: May gain larger memory allocations in future chips
- **MPS**: Will continue scaling with GPU core counts and memory bandwidth
- **Hybrid approach**: Future versions might dynamically switch based on workload

**Bottom Line**: For the Knowledge System's primary use case (large-scale content processing), MPS provides superior performance, especially on high-end Apple Silicon systems with substantial RAM configurations.