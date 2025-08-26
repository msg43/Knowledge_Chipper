# Knowledge Chipper Codebase Overview

## Executive Summary

Knowledge Chipper is a sophisticated knowledge management system for macOS that transforms videos, audio files, and documents into structured, searchable knowledge. It's designed for researchers, students, and professionals who need to extract evidence-based insights from media content.

\1 3.1.1
**Language**: Python 3.13+  
**Primary Platform**: macOS (optimized for Apple Silicon)  
**License**: MIT

## What Knowledge Chipper Does

### Core Workflow
1. **Input**: YouTube videos, local audio/video files, PDFs, markdown documents
2. **Process**: Transcribe → Extract structured claims → Map relationships → Identify contradictions → Create knowledge maps
3. **Output**: Organized markdown files with claims, evidence, entities, and relationships

### Key Capabilities
- **Transcription**: Using Whisper AI with speaker diarization
- **Claim Extraction**: A/B/C confidence tiers with evidence citations
- **Entity Recognition**: People, concepts, jargon with descriptions
- **Relationship Mapping**: Connections between claims and entities
- **Contradiction Detection**: Identifies conflicting claims across documents
- **Knowledge Organization**: Auto-generated tags and wikilinks for Obsidian

## Architecture Overview

### Technology Stack
- **Core Framework**: Python 3.13+ with asyncio
- **GUI**: PyQt6 desktop application
- **CLI**: Click-based command line interface
- **Database**: SQLite with FTS5 full-text search
- **AI/ML**: 
  - OpenAI Whisper (via whisper.cpp)
  - OpenAI GPT/Anthropic Claude/Ollama for analysis
  - PyTorch for ML operations (optional)
- **Video Processing**: yt-dlp, FFmpeg
- **Document Processing**: PyPDF2, pdfplumber

### Project Structure
```
Knowledge_Chipper/
├── src/knowledge_system/       # Main package
│   ├── cli.py                 # Command line interface
│   ├── commands/              # CLI command implementations
│   ├── config.py              # Configuration management
│   ├── database/              # SQLite models and migrations
│   ├── gui/                   # PyQt6 desktop interface
│   ├── processors/            # Input processors (audio, PDF, YouTube)
│   │   └── hce/              # Hybrid Claim Extractor system
│   ├── services/              # Core services
│   ├── superchunk/           # Long-form content processing
│   └── utils/                # Utilities and helpers
├── config/                    # Configuration files and templates
├── data/                     # Test data and cache
├── docs/                     # Documentation
└── tests/                    # Test suite
```

## Major Features & Recent Updates

### 1. HCE (Hybrid Claim Extractor) System
The revolutionary upgrade that replaced basic summaries with structured claim analysis:
- **A/B/C Confidence Tiers**: Claims categorized by certainty level
- **Evidence Citations**: Every claim backed by extracted quotes
- **Contradiction Detection**: Automatically identifies conflicting claims
- **Relationship Mapping**: Maps connections between claims and entities
- **Interactive Validation**: GUI dialog to review and correct AI-assigned tiers

### 2. Long-Form Context Engine (SuperChunk)
Advanced system for processing very long inputs (multi-hour transcripts):
- **Adaptive Segmentation**: Content-aware chunking
- **Retrieval-First Synthesis**: Works from targeted slices, not entire documents
- **Token Budget Management**: Respects model context windows
- **Evidence Tracking**: Quotes include character spans and paragraph indices
- **Verification Pass**: Checks top claims and surfaces contradictions

### 3. Smart Model-Aware Chunking
Intelligent document processing that maximizes model capacity:
- **95% Model Utilization**: Uses actual model context windows
- **Dynamic Thresholds**: Adapts to each model's capabilities
- **User-Controlled Output**: Max tokens setting controls both chunking and response length
- **Future-Proof**: Automatically adapts to new models

### 4. Enhanced GUI Features
- **Claim Search Tab**: Dedicated interface to explore extracted claims
- **Process Management Tab**: Full pipeline processing with progress tracking
- **File Watcher Tab**: Automated processing of new files
- **Hardware Detection**: Optimizes for Apple Silicon variants
- **Real-Time Progress**: Dynamic ETAs and performance monitoring

### 5. YouTube Processing Enhancements
- **Speaker Diarization**: Identifies different speakers in videos
- **Batch Processing**: Handles playlists and CSV files of URLs
- **Smart Caching**: 80-90% faster re-runs by skipping processed videos
- **Crash Recovery**: Automatically resumes from checkpoint after interruption
- **WebShare Proxy Integration**: Reliable access to YouTube content

## Database Schema

SQLite database with comprehensive schema:

### Core Tables
- `videos`: Video metadata and processing status
- `transcripts`: Multiple transcript versions per video
- `summaries`: LLM-generated summaries with cost tracking
- `claims`: Structured claims with confidence tiers
- `evidence_spans`: Timestamped quotes linked to claims
- `relations`: Typed relationships between claims
- `people`, `concepts`, `jargon`: Entity tables

### Advanced Features
- **Full-Text Search**: FTS5 tables for fast semantic search
- **WAL Mode**: Concurrent read access
- **Foreign Key Constraints**: Data integrity
- **Covering Indexes**: Optimized query performance

## Configuration System

### Key Configuration Files
- `config/settings.yaml`: Main application settings
- `config/credentials.yaml`: API keys and authentication
- `config/prompts/`: Analysis prompt templates
- `config/dropdown_options.txt`: Dynamic analysis types

### Supported AI Providers
- **OpenAI**: GPT-4, GPT-4o models
- **Anthropic**: Claude 3 family
- **Ollama**: Local models
- **Custom Endpoints**: Via model URI system

## Command Line Interface

### Core Commands
```bash
# Transcribe audio/video
knowledge-system transcribe --input "video.mp4"

# Generate summary/claims
knowledge-system summarize "transcript.md"

# Create knowledge map
knowledge-system moc *.md

# Full pipeline processing
knowledge-system process ./videos/ --recursive

# Watch folder for new files
knowledge-system watch ./input/ --patterns "*.mp4,*.pdf"
```

## GUI Application

### Main Tabs
1. **YouTube Extraction**: Process videos and playlists
2. **Audio Transcription**: Local file processing
3. **Summarization**: AI-powered analysis with claim extraction
4. **Process Management**: Full pipeline orchestration
5. **Claim Search**: Explore and validate extracted claims
6. **File Watcher**: Automated folder monitoring
7. **API Keys/Settings**: Configuration and performance tuning

## Performance Optimizations

### Hardware Awareness
- Detects Apple Silicon variants (M1/M2/M3)
- Configurable performance profiles
- GPU acceleration via Metal Performance Shaders
- Dynamic batch sizing based on available memory

### Processing Efficiency
- Parallel file processing
- Smart caching to avoid reprocessing
- Streaming for large files
- Progress tracking with time estimates

## Current Development Focus

### Active Development Areas
1. **HCE Enhancement**: Improving claim extraction accuracy
2. **Performance Optimization**: Faster processing for large batches
3. **User Experience**: Simplified workflows and better error handling
4. **Integration**: Better Obsidian integration and export options

### Recent Changes (from git status)
- Modified configuration examples
- Updates to command processors (process, summarize, transcribe)
- Enhanced transcription service
- New test suite and documentation

## Key Design Decisions

### Philosophy
- **User-First**: Designed for knowledge workers and researchers
- **Performance**: Optimized for desktop use with powerful hardware
- **Flexibility**: Supports multiple AI providers and models
- **Reliability**: Comprehensive error handling and recovery
- **Extensibility**: Plugin-based architecture for processors

### Trade-offs
- Prioritizes accuracy over speed for transcription
- Desktop-focused (not optimized for mobile/battery)
- Requires significant disk space for caching
- Memory-intensive for large batch operations

## Testing & Quality

### Test Coverage
- Unit tests with pytest
- Integration tests for full pipelines
- GUI testing with pytest-qt
- Performance benchmarks

### Quality Assurance
- Automatic quality detection for transcriptions
- Claim tier validation system
- Comprehensive error reporting
- User feedback integration

## Future Roadmap

### Near-Term Goals
- Multi-language support
- Real-time processing capabilities
- Enhanced visualization tools
- API for third-party integration

### Long-Term Vision
- Knowledge graph generation
- Collaborative claim validation
- Domain-specific models
- Active learning integration

## Getting Started

### Installation
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
bash scripts/setup.sh  # or quick_setup.sh
```

### First Run
```bash
# GUI application
python -m knowledge_system.gui

# CLI for automation
knowledge-system --help
```

## Important Notes for Development

### Code Style
- Black formatter with 88-character lines
- Type hints throughout (mypy strict mode)
- Comprehensive docstrings
- Clear error messages

### Contributing Guidelines
- Feature branches for new development
- Tests required for new functionality
- Documentation updates with code changes
- Performance impact consideration

### Key Files to Understand
1. `src/knowledge_system/cli.py` - Entry point for CLI
2. `src/knowledge_system/processors/hce/` - Claim extraction system
3. `src/knowledge_system/gui/main_window_pyqt6.py` - GUI entry point
4. `src/knowledge_system/database/models.py` - Data models
5. `src/knowledge_system/config.py` - Configuration management

## Support & Resources

- **GitHub**: https://github.com/msg43/Knowledge_Chipper
- **Documentation**: See `/docs/public/` directory
- **Issue Tracker**: GitHub Issues
- **Community Models**: See COMMUNITY_MODELS.md

---

This document provides a comprehensive overview of the Knowledge Chipper codebase as of January 2025. The system is actively maintained and continues to evolve based on user feedback and research needs.
