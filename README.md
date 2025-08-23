# Knowledge_Chipper

**Version:** 3.0.3 | **Build Date:** 2025-08-22 

A revolutionary knowledge management system for macOS that transforms videos, audio files, and documents into structured claim analysis and organized knowledge. Perfect for researchers, students, and professionals who need evidence-based insights from media content.

**What it does:** Transcribes videos → Extracts structured claims with confidence tiers → Maps relationships and contradictions → Creates knowledge maps → Organizes everything automatically.

**🔍 HCE Features:** Advanced claim extraction with A/B/C confidence tiers + real-time contradiction detection + semantic deduplication + entity recognition (people/concepts) + relationship mapping + evidence citations + Obsidian integration with auto-tagging + comprehensive search and filtering.

## 🎉 What's New (Latest Updates)

### 🔍 **HCE (Hybrid Claim Extractor) System - Revolutionary Upgrade**
- **Structured Claim Analysis**: Extract claims with A/B/C confidence tiers instead of basic summaries
- **🎯 Claim Tier Validation**: Interactive popup dialog to review and correct AI-assigned A/B/C tiers
- **🔍 Claim Search & Exploration**: Dedicated search interface to explore extracted claims across all content
- **Real-Time Analytics**: Live display of claim counts, contradictions, relations, and top findings
- **Smart Filtering**: Filter by confidence tier, claim type, or limit results for focused analysis  
- **Contradiction Detection**: Automatically identify conflicting claims within and across documents
- **Relationship Mapping**: Map connections between claims, entities, and concepts
- **Entity Recognition**: Automatic extraction of people, concepts, and jargon with descriptions
- **Evidence Citations**: Every claim backed by extracted evidence with confidence scores
- **Obsidian Integration**: Auto-generated tags and wikilinks for seamless knowledge management
- **Professional Output**: Beautiful markdown with executive summaries, categorized claims, and evidence
- **Performance Optimized**: Semantic deduplication, embedding cache, and database optimization
- **Gold Standard Dataset**: Build human-validated training data to improve AI accuracy over time

### 🧠 Context-Driven Long‑Form Analysis (New Synthesis Engine)
- **Purpose**: Deliver faithful, scalable analysis for very long inputs (multi‑hour transcripts, large PDFs) without dumping entire texts into a single prompt.
- **How it works (high level)**:
  - **Adaptive segmentation** guided by content signals keeps attention dense where it matters.
  - **Retrieval‑first synthesis**: works from targeted slices, not the whole transcript at once.
  - **Structured extraction**: schema‑validated outputs for entities, concepts, relationships, and claims.
  - **Evidence tracking**: quotes include character spans and paragraph indices; configurable quote caps.
  - **Linking & deduplication**: conservative cross‑references across chunks/files (allows “none” when uncertain).
  - **Verification pass**: checks top claims and surfaces contradictions before finalizing results.
  - **Preflight token budgeting**: respects real model windows and prompt/output budgets.
  - **Refine loop**: if quality gates fail, re‑reads only targeted regions, not the whole corpus.
  - **Artifacts for reproducibility**: final outputs plus optional scorecards, decision logs, link graphs, token traces, and lightweight ledgers.
- **Why we added this**: To maximize accuracy, transparency, and cost efficiency on long content while keeping normal GUI/CLI flows simple. Advanced behavior stays mostly invisible by default; power users can review artifacts when needed.

### 🚀 Smart Model-Aware Chunking (Major Performance Upgrade)
- **3.4x More Capacity**: Replaced hardcoded 8,000 token limit with intelligent model-aware thresholds
- **95% Model Utilization**: Now uses 95% of each model's actual context window instead of 25%
- **User-Controlled Output**: Your "Max tokens" setting controls both chunking decisions AND response length
- **Real-World Impact**: Most large transcripts (100K+ chars) now process as single units instead of being unnecessarily chunked

### 📊 Enhanced Real-Time Progress Tracking
- **Accurate Time Estimates**: Dynamic ETAs for individual files and entire batches
- **Granular Progress**: Real-time percentage completion with detailed status updates
- **Performance Monitoring**: Token processing rates and throughput tracking
- **Heartbeat System**: Prevents "frozen" appearance during long AI model calls

### 🔧 Improved User Experience
- **Clear Progress Messages**: Shows actual token counts and chunking thresholds
- **Better Error Reporting**: More detailed failure information with suggested solutions
- **Custom Prompt Preservation**: Fixed issues where chunked summaries ignored custom templates
- **Comprehensive Completion Reports**: Detailed statistics and timing information

### 📈 Performance Optimizations
- **Intelligent Token Budgeting**: Accounts for prompt overhead and response size requirements
- **Model Context Detection**: Automatically detects and uses each model's full capabilities
- **Future-Proof Design**: Automatically adapts to new models (Qwen2.5-1M gets 950K+ thresholds!)

### 🆕 Smart Knowledge Extraction
- **Header-to-YAML Auto-Extraction**: Document summaries automatically extract structured data to YAML frontmatter
- **Intelligent Field Generation**: Converts bullet points under headers (Mental Models, Jargon, People) to numbered YAML fields
- **MOC Classification**: Automatically adds `Is_MOC` field based on analysis type for better organization
- **Zero Configuration**: Works automatically with Document Summary analysis type

### 🤖 Dynamic Model Management & Smart Validation
- **Live Model Updates**: Fetches latest models from OpenAI API and Ollama.com/library when you hit refresh (🔄)
- **Smart Session Validation**: Automatically validates model access on first use - no test buttons needed
- **Clear Error Messages**: Specific, actionable feedback like "Model requires GPT-4 access" or "Run 'ollama pull llama3.2'"
- **Intelligent Fallbacks**: Automatically suggests alternatives for deprecated models
- **Zero Manual Configuration**: Model lists update automatically, validation happens transparently

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
  - [Summarization - Deep Dive](#summarization---deep-dive)
  - [Claim Search & Exploration](#-claim-search--exploration)
  - [Process Management - Full Pipeline Processing](#-process-management---full-pipeline-processing)
  - [File Watcher - Automated Processing](#️-file-watcher---automated-processing)
  - [Document Summary Header-to-YAML Extraction](#-document-summary-special-feature-header-to-yaml-extraction)
  - [Output Types](#output-types)
  - [Intelligent Text Chunking](#-intelligent-text-chunking)
  - [Intelligent Quality Detection & Automatic Retry](#-intelligent-quality-detection--automatic-retry)
- [🎯 Common Use Cases](#-common-use-cases)
  - [YouTube Video Processing](#youtube-video-processing)
  - [Local File Processing](#local-file-processing)
  - [Batch Processing](#batch-processing)
  - [Automated Monitoring](#automated-monitoring)
  - [Claim Analysis & Research](#claim-analysis--research)
  - [Full Pipeline Processing](#full-pipeline-processing)
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
  - [Long‑Form Context Engine](#long-form-context-engine)
  - [Advanced Artifacts (Optional, Experts)](#advanced-artifacts-optional-experts)
  - [Intelligent Chunking System](#intelligent-chunking-system)
  - [Process Control System](#process-control-system)
- [📄 License & Credits](#-license--credits)

## 🚀 Quick Start

### Prerequisites

- **macOS Sonoma or later** (optimized for Apple Silicon)
- **Python 3.13+** (check with `python3 --version`)
- **FFmpeg** (for audio/video processing - install with `brew install ffmpeg`)
- **Git** (for installation)
- **16GB+ RAM recommended** for large files

### Automated Installation (Recommended)

**Interactive setup with full options:**
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
bash scripts/setup.sh
```

**Quick setup (no prompts):**
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
bash scripts/quick_setup.sh
```

### Manual Installation

**Core installation (lightweight, no diarization):**
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
python3 -m venv venv
source venv/bin/activate
pip install -e ".[gui]"  # With GUI
# or
pip install -e .          # CLI only
```

**Full installation with diarization:**
```bash
pip install -e ".[full]"  # Everything including diarization
# or
pip install -e ".[diarization]"  # Just diarization dependencies
```

**Install diarization later:**
```bash
# If you want to add diarization after core installation
pip install -e ".[diarization]"
```

**What the scripts do:**
- ✅ Checks Python 3.9+ and installs Homebrew if needed
- ✅ Installs FFmpeg and other system dependencies  
- ✅ Creates virtual environment and installs all Python packages
- ✅ Sets up configuration files from templates
- ✅ Creates data directories in ~/Documents/KnowledgeSystem
- ✅ Optionally downloads Whisper models and Ollama (interactive version)
- ✅ Tests the installation and provides next steps
- ✅ Can launch the GUI immediately when complete

**Setup time:** 2-5 minutes (vs 15+ minutes manual)

### Manual Installation (Alternative)

If you prefer manual control or the automated script doesn't work:

1. **Clone and enter the project:**
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
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
2. **Go to the "Extraction" tab**
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

- **🎬 YouTube Extraction**: Process YouTube videos and playlists with speaker diarization support
- **🎵 Audio Transcription**: Process local audio/video files with quality retry and GPU acceleration
- **📝 Summarization**: Create summaries from transcripts with claim tier validation
- **📊 Process Management**: Full pipeline processing with transcription, summarization, and MOC generation
- **🔍 Claim Search**: Explore and search extracted claims across all processed content
- **👁️ File Watcher**: Automatically process new files as they're added to watched folders
- **⚙️ API Keys**: Configure API keys, hardware performance options, and preferences

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

1. **🎯 Transcription**: Convert speech to text using AI with speaker diarization
2. **📝 Summarization**: Generate structured summaries with HCE claim extraction
3. **📊 Process Management**: Full pipeline processing with transcription, summarization, and MOC generation
4. **🔍 Claim Search**: Explore and analyze extracted claims across all content
5. **👁️ Monitoring**: Watch folders for automatic processing

### Summarization - Deep Dive

**What it does:** Transforms your documents using AI-powered analysis with multiple specialized approaches: comprehensive summaries, structured knowledge maps, entity extraction, and relationship analysis.

#### **📋 Step-by-Step Process**

**Phase 1: Setup**
- Add markdown files (`.md` or `.txt`) via GUI or command line
- Configure depth (1-5), theme, and optional custom templates
- Choose whether to extract beliefs and claims

**Phase 2: Summarization** 
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

**GUI:** Summarization tab
1. Add documents or folders
2. Choose Analysis Type from dropdown (Document Summary, Knowledge Map, Entity Extraction, or Relationship Analysis)
3. Template auto-populates based on selection (customize if desired)
4. Configure provider and model (use 🔄 to refresh available models)
5. Click "Start Analysis"

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

### 🔍 Claim Search & Exploration

**Comprehensive Search Interface for Extracted Claims**

The Claim Search tab provides a powerful interface to explore, filter, and analyze all claims extracted from your processed content:

**🎯 Search Capabilities:**
- **Text Search**: Find claims containing specific keywords or phrases
- **Tier Filtering**: Filter by confidence tier (A, B, C, or All)
- **Content Type**: Filter by claim type (factual, causal, normative, forecast, definition)
- **Source Filtering**: Search within specific videos or documents
- **Advanced Queries**: Combine multiple filters for precise results

**📊 Rich Display Format:**
- **Claim Details**: Full claim text with confidence scores and evidence
- **Source Context**: Video title, URL, and processing metadata
- **Tier Indicators**: Visual A/B/C tier badges with color coding
- **Evidence Preview**: Supporting evidence spans with timestamps
- **Quick Actions**: Direct links to source content and validation options

**🔧 Interactive Features:**
- **Real-time Search**: Results update as you type
- **Sortable Results**: Sort by relevance, confidence, date, or tier
- **Export Options**: Export search results to CSV or JSON
- **Batch Operations**: Select multiple claims for bulk actions
- **Validation Integration**: Direct access to tier validation from search results

**Sample Search Interface:**
```
Search: "artificial intelligence" | Tier: All | Type: Forecast

Results: 47 claims found

┌─────────────────────────────────────────────────────────┐
│ [A] AI will transform healthcare within 5 years        │
│ Source: "Future of Medicine" (youtube.com/watch?v=...)  │
│ Evidence: "Recent breakthroughs in diagnostic AI..."    │
│ Confidence: 0.89 • Type: Forecast                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ [B] Machine learning requires large datasets           │
│ Source: "ML Fundamentals" (youtube.com/watch?v=...)    │
│ Evidence: "Training effective models typically..."      │
│ Confidence: 0.72 • Type: Factual                       │
└─────────────────────────────────────────────────────────┘
```

**🎯 Perfect For:**
- **Research Analysis**: Find all claims related to specific topics
- **Fact Checking**: Verify claims across multiple sources
- **Content Curation**: Identify high-confidence claims for reports
- **Knowledge Discovery**: Explore connections between different claims
- **Quality Assurance**: Review and validate claim accuracy

### 📊 Process Management - Full Pipeline Processing

**Comprehensive Workflow Management for Multiple Files**

The Process Management tab provides a unified interface for running complete processing pipelines on multiple files simultaneously:

**🔄 Full Pipeline Capabilities:**
- **Transcription**: Convert audio/video files to text with speaker diarization
- **Summarization**: Generate AI-powered summaries with HCE claim extraction
- **MOC Generation**: Create knowledge maps from processed content
- **Batch Processing**: Handle multiple files with progress tracking
- **Settings Inheritance**: Automatically uses settings from other tabs

**⚙️ Configuration Options:**
- **Input Selection**: Add individual files or entire folders
- **Processing Steps**: Enable/disable transcription, summarization, and MOC generation
- **Output Management**: Configurable output directory and file organization
- **Progress Monitoring**: Real-time progress tracking with detailed status updates
- **Error Handling**: Comprehensive error reporting and recovery options

**🎯 Workflow Benefits:**
- **One-Click Processing**: Complete pipeline from raw files to knowledge maps
- **Consistent Settings**: Uses your configured models and preferences from other tabs
- **Parallel Processing**: Efficient handling of multiple files simultaneously
- **Progress Transparency**: Clear visibility into each processing stage
- **Flexible Output**: Choose which processing steps to include

### 👁️ File Watcher - Automated Processing

**Intelligent Folder Monitoring for Continuous Processing**

The File Watcher tab enables automated processing of new files as they're added to monitored directories:

**🔍 Monitoring Features:**
- **Real-time Detection**: Instantly detects new files added to watched folders
- **Pattern Matching**: Configurable file patterns (*.mp4, *.pdf, etc.)
- **Recursive Watching**: Monitor subdirectories automatically
- **Debounce Control**: Prevents duplicate processing during file operations
- **Multiple Patterns**: Support for multiple file types simultaneously

**⚡ Processing Options:**
- **Auto-Processing**: Automatically process detected files
- **Dry Run Mode**: Preview what would be processed without actual processing
- **Custom Delays**: Configurable debounce delays for stable file detection
- **Selective Processing**: Choose which file types to process automatically
- **Manual Override**: Option to manually trigger processing for detected files

**🎛️ Configuration:**
- **Watch Directory**: Select any folder to monitor
- **File Patterns**: Comma-separated patterns (e.g., "*.mp4,*.mp3,*.pdf")
- **Processing Pipeline**: Uses settings from other tabs for consistency
- **Status Monitoring**: Real-time display of watched files and processing status
- **Start/Stop Control**: Easy enable/disable of monitoring

**Sample Configuration:**
```
Watch Directory: ~/Documents/Research/
File Patterns: *.mp4,*.mp3,*.pdf,*.txt
Recursive: ✓ (monitor subdirectories)
Auto-Process: ✓ (process files automatically)
Debounce Delay: 5 seconds
```

**🎯 Perfect For:**
- **Research Workflows**: Automatically process new research materials
- **Content Creation**: Monitor download folders for new videos/audio
- **Document Management**: Process new documents as they're added
- **Batch Operations**: Set up overnight processing of large collections
- **Team Collaboration**: Monitor shared folders for new content

#### **📋 Document Summary Special Feature: Header-to-YAML Extraction**

**Smart Automatic YAML Field Generation from Summary Content**

When using "Document Summary" analysis type, the system automatically extracts structured information and adds it to YAML frontmatter:

**🎯 How It Works:**
1. System analyzes the generated summary content
2. Looks for specific header sections (configurable in `config/Headers_to_YAML.txt`)
3. Extracts bullet points under those headers
4. Automatically creates numbered YAML fields

**📝 Default Header Detection:**
```
Mental Models; Jargon; People
```

**🔄 Automatic Processing Example:**

**Summary Content Generated:**
```markdown
### Mental Models
- Systems thinking approach to complex problems
- First principles reasoning for better decisions
- Opportunity cost evaluation framework

### Jargon
- API: Application Programming Interface
- MVP: Minimum Viable Product

### People
- Elon Musk: CEO of Tesla and SpaceX
```

**YAML Frontmatter Automatically Added:**
```yaml
---
title: "Summary of podcast_episode"
source_file: "episode.md"
model: "gpt-4o-mini-2024-07-18"
Is_MOC: false
Mental_Models_01: "Systems thinking approach to complex problems"
Mental_Models_02: "First principles reasoning for better decisions"
Mental_Models_03: "Opportunity cost evaluation framework"
Jargon_01: "API: Application Programming Interface"
Jargon_02: "MVP: Minimum Viable Product"
People_01: "Elon Musk: CEO of Tesla and SpaceX"
generated: "2025-01-02T16:30:00Z"
---
```

**⚙️ Configuration:**
- **Header List**: Edit `config/Headers_to_YAML.txt` to customize which headers trigger extraction
- **Analysis Type Detection**: Only works with "Document Summary" analysis type
- **Is_MOC Field**: Automatically adds `Is_MOC: false` for Document Summary, `Is_MOC: true` for MOC types

**🔧 Field Name Consistency:**
- **Exact Header Matching**: H3 headers from your prompt become YAML fields exactly (spaces → underscores)
  - `### Mental Models` → `Mental_Models_01`, `Mental_Models_02`, etc.
  - `### People` → `People_01`, `People_02`, etc.
  - `### Jargon` → `Jargon_01`, `Jargon_02`, etc.
- **Title Consistency**: Both file titles and YAML titles display without dashes (e.g., "my document" instead of "my-document")

**💡 Benefits:**
- **Zero Manual Work**: Automatic structured data extraction
- **Obsidian Compatible**: Perfect YAML frontmatter for knowledge management
- **Searchable**: Query by specific mental models, people, or jargon
- **Scalable**: Works across hundreds of summary files
- **Customizable**: Configure which headers to extract

**🎯 Perfect For:** Building searchable knowledge bases, research databases, podcast analysis, interview insights, and academic paper organization.

### Output Types

- **Transcripts**: Full text with timestamps
- **Summaries**: Key points and insights with intelligent chunking
- **Knowledge Maps**: People, tags, concepts, and relationships
- **Reports**: Detailed processing logs

### 🧠 Intelligent Text Chunking

**Smart Model-Aware Processing for Documents of Any Size**

The system automatically handles documents that exceed AI model context windows through intelligent chunking with **model-aware thresholds** that maximize your hardware capabilities:

**🚀 Smart Model-Aware Chunking (NEW):**
- **Model-Specific Thresholds**: Automatically uses 95% of each model's actual capacity
- **User-Controlled Response Size**: Your "Max tokens" setting controls both chunking decisions AND summary length
- **Dynamic Token Budgeting**: Calculates available space accounting for prompt overhead and expected response size
- **Massive Efficiency Gains**: 3.4x more input capacity vs previous hardcoded limits

**📊 Real-World Performance Improvements:**
```
Example: qwen2.5:32b-instruct with 2000 max_tokens

OLD System (Hardcoded):
- Chunking threshold: 8,000 tokens (24.4% model utilization)
- Your 100K char files: FORCED chunking into 4 pieces

NEW System (Smart):
- Chunking threshold: 29,075 tokens (88.7% model utilization)  
- Your 100K char files: SINGLE UNIT processing ✅
- Result: 3-4x faster, perfect prompt adherence
```

**🔧 Fully Automatic Operation:**
- **Zero Configuration**: No settings needed - intelligently adapts to your model and preferences
- **Smart Detection**: Uses actual model context windows instead of conservative hardcoded limits
- **Intelligent Boundaries**: Automatically chooses optimal split points (paragraphs → sentences → words)
- **Context Preservation**: Automatically calculates optimal overlap to maintain meaning across chunks
- **Seamless Results**: Automatically reassembles chunks into coherent final summaries

**🧮 Advanced Automatic Calculations:**
- ✅ **Model context window detection** (8K to 1M+ tokens depending on model)
- ✅ **Prompt overhead estimation** (accounts for your custom templates)
- ✅ **User response size reservation** (uses your "Max tokens" setting)
- ✅ **5% safety margin** (95% utilization with protection against edge cases)
- ✅ **Optimal chunk size and overlap** based on available capacity

**📊 Universal Model Support with Real Limits:**
- **qwen2.5:32b-instruct**: 29,075 token threshold (88.7% of 32K capacity)
- **GPT-4o**: 119,548 token threshold (93.4% of 128K capacity)
- **Claude 3.5 Sonnet**: 180,000 token threshold (90% of 200K capacity)
- **GPT-4**: 6,075 token threshold (87.5% of 8K capacity)
- **Future models**: Automatically adapts to new context windows

**🎯 Key Benefits:**
- **Maximum Efficiency**: Uses 95% of model capacity instead of artificial 25% limits
- **User Control**: Your "Max tokens" controls both processing decisions and output length
- **Perfect Quality**: Single-unit processing preserves custom prompt adherence
- **Future-Proof**: Automatically scales with new models (Qwen2.5-1M gets 950K+ thresholds!)
- **Transparent**: Clear progress messages show actual token counts and thresholds

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

### 📊 Enhanced Real-Time Progress Tracking

**Comprehensive Progress Monitoring with Time Estimates**

The system now provides detailed, real-time progress tracking for all operations with intelligent time estimation and granular status updates:

**🕐 Time Estimation & ETAs:**
- **Individual File Progress**: Real-time percentage completion for current file
- **Overall Batch Progress**: Combined progress across all selected files
- **Estimated Time Remaining**: Dynamic ETA calculation for both current file and entire batch
- **Processing Speed Tracking**: Tokens per second and completion rates
- **Elapsed Time Display**: Shows time taken for completed files

**📈 Granular Status Updates:**
- **File-Level Progress**: "Processing Marc-Faber-transcript.md (67% complete, 2m 15s remaining)"
- **Batch-Level Progress**: "Overall: 2/5 files complete (40%), ~8 minutes remaining"
- **Operation-Specific**: Different progress types for transcription, summarization, chunking
- **Quality Indicators**: Shows retry attempts and model upgrades in real-time

**🎛️ Smart Progress Display:**
```
Enhanced Summarization Progress Example:

✅ Processing Marc-Faber-on-Gold.md...
📖 Reading input text... (10%)
🧠 Smart chunking threshold: 29,075 tokens (88.7% model utilization)
🔧 Text is large (25,000 > 29,075 tokens), processing as single unit ✅
🚀 Processing with AI model... (45% complete, 1m 30s remaining)
💾 Summary generation complete! (100%)
⏱️  File completed in 2m 45s

📊 Overall Progress: 3/5 files complete (60%)
🕐 Batch time remaining: ~4m 30s
```

**🚀 Performance Monitoring:**
- **Token Processing Rates**: Real-time tokens/second for LLM operations
- **Throughput Tracking**: Files per hour completion rates
- **Efficiency Metrics**: Time saved by smart chunking decisions
- **Resource Utilization**: Model capacity usage and optimization suggestions

**🎯 User Experience Improvements:**
- **Throttled Updates**: Progress updates every 10% or 30 seconds to reduce noise
- **Heartbeat Monitoring**: Prevents "frozen" appearance during long LLM calls
- **Clear Error Reporting**: Detailed failure information with suggested solutions
- **Success Summaries**: Comprehensive completion reports with timing and statistics

**💡 Benefits:**
- **No More Guessing**: Always know how much work remains
- **Planning Capability**: Accurate time estimates for scheduling other work
- **Process Transparency**: Clear visibility into what the system is doing
- **Early Problem Detection**: Spot issues before they become failures
- **Performance Optimization**: Identify bottlenecks and optimization opportunities

## 🎯 Common Use Cases

### YouTube Video Processing with Advanced Batch Management

**Perfect for:** Lectures, podcasts, tutorials, interviews, large channel archives

```bash
# Single video
knowledge-system transcribe --input "https://youtube.com/watch?v=VIDEO_ID"

# Entire playlist
knowledge-system transcribe --input "https://youtube.com/playlist?list=PLAYLIST_ID"

# Process CSV file with multiple URLs (great for retry)
knowledge-system transcribe --batch-urls urls.csv

# Retry failed extractions from auto-generated CSV
knowledge-system transcribe --batch-urls logs/youtube_extraction_failures.csv
```

**GUI:** Use the "Extraction" tab for the easiest experience.

#### 🚀 **NEW: Intelligent Batch Processing with Resource Management**

For processing large numbers of videos (100s-1000s), the system now includes enterprise-grade resource management:

**🔄 Conveyor Belt Mode (Default)**
- Downloads videos in small batches (50-100 at a time)
- Processes each batch with parallel diarization 
- Automatically cleans up audio files after successful processing
- Memory-efficient for long-running operations
- **Best for:** Normal internet, limited disk space

**📥 Download-All Mode (New Option)**
- Downloads ALL audio files first, then processes offline
- Can disconnect internet after download phase
- Retains audio files until all processing completes
- **Best for:** Slow internet, large disk space, overnight processing

**🧠 Smart Resource Monitoring**
- **Memory Pressure Handling**: Automatically reduces concurrency when memory usage hits 85%
- **Emergency Protection**: Stops processing at 98% memory to prevent crashes
- **Dynamic Adjustment**: Concurrency adapts based on system performance
- **Disk Space Validation**: Checks available space before starting large batches

**🛡️ Crash Recovery**
- Audio files are retained until successful transcription
- Failed downloads can be retried without re-downloading successful ones
- Automatic failure logging with CSV files for easy retry

#### 🎙️ **Enhanced Speaker Diarization**

YouTube videos now support advanced speaker identification:

```bash
# Enable diarization for speaker-aware transcripts
knowledge-system transcribe --input "https://youtube.com/watch?v=VIDEO_ID" --enable-diarization
```

**Features:**
- **Speaker Labels**: Output includes (SPEAKER_00), (SPEAKER_01), etc.
- **Webshare Proxy Integration**: Uses your configured proxy for reliable audio downloads
- **Intelligent Processing**: Automatically switches between regular transcripts and diarization
- **Fallback Handling**: Gracefully falls back to regular transcripts if diarization fails

**Sample Output with Diarization:**
```markdown
## Interview Analysis

**(SPEAKER_00):** Welcome to the show. Today we're discussing...

**(SPEAKER_01):** Thanks for having me. I'm excited to talk about...

**(SPEAKER_00):** Let's start with the basics. Can you explain...
```

#### 🎯 **Claim Tier Validation System**

**Interactive Quality Assurance for HCE Claims**

After HCE processing extracts claims with A/B/C confidence tiers, users can validate and correct the AI's tier assignments through an intuitive card-based interface:

**🔍 Validation Workflow:**
1. **Process content** with HCE claim extraction enabled
2. **Click "Validate Claim Tiers"** button after processing completes
3. **Review each claim** in a beautiful card-based popup dialog
4. **Confirm or modify** tier assignments (A → B, B → C, etc.)
5. **Build gold standard dataset** for improving AI accuracy over time

**✨ Key Features:**
- **Card-Based Interface**: Each claim displayed as an individual card with evidence
- **Quick Workflow**: Click tier → Click confirm → Move to next claim
- **Visual Feedback**: Cards change color based on validation state
- **Progress Tracking**: Real-time progress with "X of Y claims validated"
- **Batch Operations**: "Confirm All Remaining" for efficiency
- **Analytics Dashboard**: Track AI accuracy rates and improvement over time

**📊 Validation Analytics:**
- **Overall Accuracy**: System-wide AI accuracy rates
- **Tier-Specific Performance**: Separate accuracy for A, B, C tiers
- **Correction Patterns**: Common A→B, B→C corrections identified
- **Model Performance**: Track accuracy across different AI models
- **Training Data**: Build human-validated dataset for model improvement

**Sample Validation Interface:**
```
┌─────────────────────────────────────────────────────────┐
│ Claim: AI will significantly impact job markets         │
│ Type: Forecast • Evidence: 2 spans • Confidence: 0.85  │
│                                                         │
│ Tier: ○ A  ● B  ○ C    [✓ Confirm] [Skip]             │
│                                                         │
│ Evidence: "Studies show 40% of jobs could be automated │
│ within the next decade according to McKinsey..."       │
└─────────────────────────────────────────────────────────┘
Progress: 3 of 12 claims validated (1 modified)
```

**🎯 Perfect For:**
- **Researchers**: Building reliable claim databases
- **Content Creators**: Ensuring claim accuracy in analysis
- **Academics**: Creating validated datasets for research
- **Organizations**: Quality assurance for knowledge management

#### ⚡ **Performance & Reliability**

- **80-90% Faster Re-runs**: Automatically skips already processed videos
- **WebShare Proxy Required**: Ensures reliable access to YouTube content  
- **Automatic Retry Logic**: Failed extractions are logged and can be easily retried
- **Parallel Processing**: Multiple videos processed simultaneously with resource monitoring

**Performance Note:** Re-running YouTube extractions is now 80-90% faster! The system automatically skips videos that have already been processed by checking video IDs before making any API calls.

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

### Claim Analysis & Research

**Perfect for:** Research analysis, fact-checking, knowledge discovery

```bash
# Process research materials with HCE claim extraction
knowledge-system summarize research_papers/ --analysis-type "HCE Analysis"

# Search extracted claims
# Use GUI: Claim Search tab to explore and filter claims
```

**GUI Workflow:**
1. **Process content** with HCE enabled in Summarization tab
2. **Validate claim tiers** using the popup validation dialog
3. **Search and explore** claims in the Claim Search tab
4. **Export results** for further analysis or reporting

### Full Pipeline Processing

**Perfect for:** Complete end-to-end workflows

**GUI:** Use "Process Management" tab for one-click processing:
1. **Add files or folders** to process
2. **Configure pipeline** (transcription + summarization + MOC)
3. **Start processing** and monitor progress
4. **Review results** with integrated validation tools

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
4. Models automatically populate from your account when you click refresh (🔄)

**Anthropic (Alternative):**
1. Go to https://console.anthropic.com/
2. Create a new key
3. Add it in Settings tab → "Anthropic API Key"
4. Latest Claude models are pre-configured and updated regularly

**Ollama (Local):**
- Models automatically detected from your local Ollama installation
- Click refresh (🔄) to update the list from ollama.com/library
- System validates models are actually installed before use

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
- **Output Formats**: Markdown, plain text, SRT subtitles
- **Processing Options**: Auto-processing, file patterns

#### **🎨 Custom Analysis Types & Prompts**

**✨ FULLY DYNAMIC SYSTEM**: The analysis types and prompt templates are completely customizable through simple configuration files - no code changes required!

### **How the Dynamic System Works**

**🔄 Automatic Template Detection:**
1. **Analysis Types**: Defined in `config/dropdown_options.txt` (comma-separated)
2. **Template Files**: System automatically looks for `config/prompts/{analysis_type}.txt`
3. **Smart Conversion**: Analysis type names are converted to filenames automatically
4. **No Hardcoding**: Add any analysis type without touching code

**📁 File Naming Convention:**
```
Analysis Type → Template File
"Document Summary" → config/prompts/document summary.txt
"Custom Research" → config/prompts/custom research.txt  
"Meeting Notes (Beta)" → config/prompts/meeting notes beta.txt
```

**Conversion Rules:**
- Spaces: Preserved as spaces (not underscores)
- Parentheses: Removed completely  
- Case: Converted to lowercase
- Example: `"My Analysis (Beta)"` → `my analysis beta.txt`

### **Adding New Analysis Types**

**Step 1: Add to Dropdown Options**
```bash
# Edit config/dropdown_options.txt
Document Summary,Create MOC,Create MOC of MOCs,Research Analysis,Meeting Minutes,Interview Insights
```

**Step 2: Create Template File**
```bash
# Create config/prompts/research analysis.txt
Analyze the following research content and extract:

## Key Findings
- Extract the main research findings
- Note methodology used

## Data Sources  
- Identify all data sources mentioned
- Assess credibility and reliability

## Conclusions
- Summarize author conclusions
- Note limitations mentioned

{TEXT}
```

**Step 3: That's It!**
- New option appears immediately in GUI dropdown
- Template auto-loads when selected
- Users can still customize template path if needed

### **Configuration Files**

**Dropdown Options** (`config/dropdown_options.txt`):
```
Document Summary,Knowledge Map (MOC Style),Entity Extraction,Relationship Analysis,Meeting Minutes,Research Paper Analysis,Interview Insights,Code Review,Financial Analysis
```

**Template Requirements:**
- Must include `{TEXT}` placeholder for content insertion
- Can include `{MAX_TOKENS}` for token limit
- Standard markdown formatting supported
- Can include custom instructions and sections

### **Real-World Examples**

**Academic Research Setup:**
```bash
# config/dropdown_options.txt
Document Summary,Literature Review,Research Paper Analysis,Methodology Extraction,Data Analysis

# Then create:
# config/prompts/literature review.txt
# config/prompts/research paper analysis.txt  
# config/prompts/methodology extraction.txt
# config/prompts/data analysis.txt
```

**Business Meeting Setup:**
```bash
# config/dropdown_options.txt  
Document Summary,Meeting Minutes,Action Items,Decision Log,Strategic Planning

# Then create corresponding .txt files in config/prompts/
```

**Content Creator Setup:**
```bash
# config/dropdown_options.txt
Document Summary,Video Script Analysis,Content Ideas,Audience Insights,Performance Review
```

### **Benefits of Dynamic System**

**✅ Zero Code Changes**: Add unlimited analysis types via text files
**✅ Instant Updates**: Changes appear immediately in GUI
**✅ User Customizable**: End users can add their own analysis types
**✅ Template Flexibility**: Each analysis type uses its own specialized prompt
**✅ Professional Workflows**: Customize for specific industries or use cases
**✅ Team Consistency**: Share config files to standardize analysis across teams

### **Advanced Customization**

**Custom Template Variables:**
```markdown
# config/prompts/financial analysis.txt
Analyze the following financial content focusing on:

## Revenue Analysis
- Extract revenue figures and growth rates
- Note seasonal patterns

## Risk Assessment  
- Identify financial risks mentioned
- Assess management discussion of risks

Maximum response length: {MAX_TOKENS} tokens

Content to analyze:
{TEXT}
```

**Template Best Practices:**
- Use clear section headers for consistent output structure
- Include specific instructions for desired analysis depth
- Consider your intended output format (YAML fields, bullet points, etc.)
- Test templates with sample content before deploying

**💡 Pro Tip**: The system automatically generates YAML metadata from section headers when using "Document Summary" analysis type, so structure your templates accordingly!

## 🔧 Troubleshooting

### Common Issues

**❌ "API key not found"**
- **Solution**: Add your API key in Settings tab
- **Details**: OpenAI or Anthropic API key required for summarization

**❌ "Model validation failed"**
- **Solution**: The system automatically checks model access when you start processing
- **Common causes and fixes**:
  - "No access to model": Check your API subscription (e.g., GPT-4 requires specific access)
  - "Model not installed": For Ollama, run `ollama pull <model-name>`
  - "Invalid API key": Verify your API key is correct and active
  - "Rate limit exceeded": Wait a few minutes and try again
- **Details**: First use of each model validates it can actually respond

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

**⚠️ "Template File Missing"**
- **Explanation**: Selected analysis type doesn't have a corresponding prompt template file
- **Solution**: Create the missing template file at the specified path, or edit `config/dropdown_options.txt` to remove unused options
- **Details**: System expects prompt files to match dropdown options exactly (lowercase with spaces preserved)

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

### Handling Failed Extractions

**YouTube Extraction Failures:**
- **Check failure log**: `logs/youtube_extraction_failures.log` for detailed error messages
- **Retry failed URLs**: Load `logs/youtube_extraction_failures.csv` directly into Extraction tab
- **Common failures**: 
  - 🔐 Proxy authentication → Check WebShare credentials
  - 💰 Payment required → Add funds to WebShare account
  - ❌ Video unavailable → Video is private/deleted/region-locked

**Summary Generation Issues:**
- **Check modification times**: System only processes changed files by default
- **Force regeneration**: Use `--force` flag or "Force regenerate all" checkbox
- **View skip reasons**: Check console output for why files were skipped

### Getting Help

1. **Check the logs** in the GUI console output
2. **Look at processing reports** (saved automatically)
3. **Try with a smaller test file** first
4. **Check your API key** configuration
5. **Review failure logs** in `logs/` directory for specific errors

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

# Large documents (smart model-aware chunking)
knowledge-system summarize large_transcript.md  # Intelligent chunking uses 95% of model capacity
# Example: 100K char files process as single unit on qwen2.5:32b (vs forced chunking before)
```

### Model Management

```bash
# List available models for a provider
knowledge-system models list openai
knowledge-system models list anthropic
knowledge-system models list local

# Refresh model lists from official sources
knowledge-system models refresh        # Refresh all providers
knowledge-system models refresh openai # Refresh specific provider

# Models are automatically validated when first used
# No manual testing needed - happens transparently
```

### Batch Operations

```bash
# Process folder recursively with full pipeline
knowledge-system process ./videos/ --recursive --transcribe --summarize --moc

# Batch transcription from CSV file
knowledge-system transcribe --batch-urls urls.csv --output ./transcripts/

# Recursive summarization with custom patterns
knowledge-system summarize ./documents/ --recursive --patterns "*.pdf" "*.md" "*.txt"

# Force re-summarization of all files (ignore modification times)
knowledge-system summarize ./documents/ --force

# Normal run skips unchanged files for massive time/cost savings
knowledge-system summarize ./documents/  # Only processes modified files
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

### 🚀 Performance Optimization Features (NEW)

#### Smart Caching & Skip Logic

The system now includes intelligent caching to avoid reprocessing unchanged content:

**YouTube Transcript Extraction:**
- **Video ID Index**: Automatically builds an index of processed videos
- **Smart Skip**: Checks video IDs before fetching - skips if already processed
- **Performance Impact**: 80-90% faster for re-runs (no API calls for existing videos)
- **Override**: Use "Overwrite existing" checkbox to force re-extraction

**Summary Generation:**
- **Modification Time Tracking**: Only re-summarizes files changed since last summary
- **Content Hash Verification**: Optional hash checking for content changes
- **Cost Savings**: Skips API calls for unchanged files
- **Force Regenerate**: Use `--force` flag in CLI or checkbox in GUI to regenerate all

#### Failure Tracking & Recovery

**YouTube Extraction Failures:**
- **Detailed Logging**: All failed extractions logged to `logs/youtube_extraction_failures.log`
- **CSV Export**: Failed URLs automatically saved to `logs/youtube_extraction_failures.csv`
- **Easy Retry**: Load the CSV file directly into Extraction tab to retry failed videos
- **Error Categories**: Proxy auth issues, payment required, video unavailable, etc.

**Performance Statistics:**
- Shows exact time saved by skipping unchanged content
- Estimates API tokens and costs saved
- Reports number of files skipped via smart caching

#### Crash Recovery & Resume Capabilities

**Robust Recovery for Large YouTube Processing Operations**

The system includes comprehensive crash recovery mechanisms specifically designed for large YouTube transcription batches with diarization:

**🔄 Automatic Crash Recovery:**
- **Video ID Index**: Maintains persistent index of successfully processed videos
- **Resume from Checkpoint**: Automatically skips completed videos when restarting after a crash
- **Diarization-Aware**: Recovery works regardless of whether diarization was enabled
- **Progress Preservation**: Checkpoint system saves task states throughout processing

**📊 Recovery Mechanisms:**
- **Index Building**: Scans existing transcript files for video IDs in YAML frontmatter
- **Smart Skip Logic**: Checks video IDs before processing - skips if already completed
- **File-Based Recovery**: Works by examining actual output files, not just memory state
- **Graceful Restart**: Simply re-run the same batch - completed videos are automatically skipped

**🎯 Real-World Scenario:**
```
Initial batch: 100 YouTube videos with diarization
App crashes after: 45 videos successfully completed
On restart: System automatically skips the 45 completed videos
Continues from: Video #46 (automatically detected)
Time saved: 80-90% (no re-downloading or re-processing)
```

**⚡ Performance Benefits:**
- **80-90% Time Savings**: Re-runs are dramatically faster due to intelligent skipping
- **No Re-processing**: Completed transcriptions (with diarization) are preserved
- **Checkpoint-Based**: Progress tracking with automatic resume capability
- **Override Available**: Use "Overwrite existing" option to force re-processing if needed

**🔧 How It Works:**
1. **During Processing**: System tracks completed video IDs and saves to persistent checkpoint files
2. **After Crash**: On restart, system builds index of existing transcripts from output directory
3. **Smart Resume**: Compares new batch against existing files and skips matches
4. **Seamless Continue**: Picks up exactly where it left off without user intervention

**💡 Perfect For:**
- Large YouTube playlist processing (100+ videos)
- Long-running transcription jobs with diarization
- Batch processing operations that might be interrupted
- Research projects requiring reliable, resumable workflows

### System Architecture

- **Modular processors** for different input types
- **Plugin-based services** for AI providers
- **Queue-based processing** for reliability
- **Progress tracking** throughout pipeline

### Long‑Form Context Engine

Built for accuracy and scale on very long inputs while staying cost‑aware and reproducible:

- **Segmentation & Signals**: adaptive windows based on content signals (precision/narrative balance) with sticky transitions and overlaps.
- **Targeted Retrieval**: synthesizes from retrieved slices instead of prompting with entire transcripts.
- **Schema‑Validated Extractors**: produces consistent JSON for entities, concepts, relationships, and claims with exact counts.
- **Evidence Fidelity**: quotes carry character spans and paragraph indices; configurable maximum quoted words.
- **Linker & Deduplication**: conservative cross‑linking; allows explicit “none” when links are uncertain.
- **Verification & Gates**: verifies top claims, tracks novelty/rarity coverage, and surfaces contradictions before finalizing.
- **Token Budget Discipline**: pre‑checks prompt/input/output budgets against real model windows.
- **Refine Cycle**: if a gate fails, generates a focused refine plan and re‑reads only the relevant regions.
- **Artifacts & Observability**: optional scorecards, decision logs, token traces, link graphs, and a compact ledger to make results explainable.

### Advanced Artifacts (Optional, Experts)

Most users can ignore this section. These artifacts are for advanced users who want transparency, auditing, or to integrate outputs into research or pipelines. They are saved alongside your outputs (for example, within `Reports/` or the processing folder).

<details>
<summary>Show advanced artifacts</summary>

- **final.md**: The readable, human‑friendly write‑up produced after analysis. This is the document most people will read.
- **scorecard.json**: A small report with quality metrics (e.g., coverage of rare items, verification outcomes). Useful to sanity‑check that the result meets expected quality.
- **decision_log.json**: A step‑by‑step record of major decisions (how content was segmented, why certain slices were retrieved, when verification was triggered). Helps explain “why the system did what it did.”
- **llm_calls.jsonl**: A newline‑delimited log of model calls (sanitized prompts/outputs with timing and token counts). Handy for debugging or cost analysis.
- **token_trace.csv**: Spreadsheet‑friendly view of token usage across steps. Use any spreadsheet app to spot outliers or bottlenecks.
- **link_graph.dot**: A graph representation of relationships between entities/concepts. Open with a Graphviz viewer or any DOT‑file visualizer to see how ideas connect.
- **global_context.json**: Condensed context built from retrieved slices that informed the final synthesis. Useful to understand what evidence the system considered.
- **chunking_decisions.json**: Records where and why the text was split, including overlaps and presets. Helpful when validating segmentation on long inputs.
- **verification_log.json**: Shows which top claims were checked and the outcomes. Useful for trust and auditing.
- **refine_plan.json**: If quality gates fail, this file describes targeted follow‑ups (what to re‑read or double‑check) instead of reprocessing everything.
- **ledger.sqlite / artifacts.sqlite**: Lightweight databases for indexing artifacts and traces, enabling faster inspection with external tools.

Tip: If you don’t need these, you can ignore them—your normal summaries, transcripts, and reports work the same as always.

</details>

### Intelligent Chunking System

**Smart Model-Aware Implementation:**

- **Model-Specific Thresholds**: Uses actual context windows (32K for Qwen, 128K for GPT-4o, 200K for Claude)
- **Dynamic Token Budgeting**: Calculates available space: `context_window - prompt_tokens - max_output_tokens - 5% safety`
- **User-Controlled Response Size**: Max tokens setting controls both chunking decision AND actual response length
- **95% Utilization**: Maximizes model capacity instead of conservative 25% hardcoded limits

**Advanced Decision Logic:**
```python
# Smart chunking decision (NEW):
def should_chunk(text, model, prompt_template, max_tokens):
    context_window = get_model_context_window(model)  # Real model capacity
    prompt_overhead = estimate_prompt_tokens(prompt_template)
    safety_margin = context_window * 0.05  # 5% buffer
    
    available_for_text = context_window - prompt_overhead - max_tokens - safety_margin
    estimated_tokens = estimate_tokens(text)
    
    return estimated_tokens > available_for_text  # Smart decision

# Example results:
# qwen2.5:32b + 2000 max_tokens = 29,075 token threshold (vs old 8,000)
# GPT-4o + 2000 max_tokens = 119,548 token threshold (vs old 8,000)
```

**Intelligent Boundary Detection:**
- **Token Estimation**: Uses tiktoken for accurate token counting across different models
- **Smart Boundary Detection**: Preserves semantic integrity using regex patterns for sentences/paragraphs
- **Automatic Overlap Management**: Intelligently calculates optimal token overlap (50-1000) to maintain context
- **Seamless Reassembly**: Intelligent merging of chunk summaries with transition handling

**Performance Optimizations:**
- **Massive Efficiency Gains**: 3.4x more input capacity reduces unnecessary chunking by 75%
- **Single-Unit Processing**: Most large files now process without chunking (faster, better quality)
- **Parallel Processing**: Chunks processed concurrently when chunking is actually needed
- **Memory Management**: Streaming for large inputs to prevent memory overflow
- **Prompt Preservation**: Custom templates correctly applied across chunks and reassembly

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

## Cache Management

The Knowledge System includes smart Python cache management to prevent import issues and ensure clean startup:

### Automatic Cache Clearing
The system automatically detects when cache clearing is needed based on:
- Code changes in the project
- Dependency changes (requirements.txt)
- Recent import errors in logs
- Python version changes

When you start the GUI, it will automatically clear cache if needed:
```bash
python -m knowledge_system gui
# Output: 🧹 Cache cleared: recent import errors detected
```

### Manual Cache Management
You can also manage cache manually using CLI commands:

```bash
# Check if cache clearing is recommended
python -m knowledge_system cache status

# Clear cache immediately
python -m knowledge_system cache clear

# Create a flag to force cache clearing on next startup
python -m knowledge_system cache flag
```

### When Cache Clearing Helps
- Import errors (like "module not found" or "missing method")
- Stale module state after code updates
- Dependencies not working correctly after updates
- Application behaving unexpectedly after changes

The cache clearing is smart and only runs when needed, so it won't slow down normal application startup.
