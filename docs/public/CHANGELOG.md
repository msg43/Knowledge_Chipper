# Changelog

All notable changes to the Knowledge System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.1.2] - 2025-08-31

### Added
- **Enhanced Speaker Attribution System**: Complete migration from sidecar files to database-driven approach
- **Intelligent Learning Service**: AI learns from user corrections to improve future speaker suggestions
- **Pattern Recognition**: Detects speakers based on content analysis, channel patterns, and voice characteristics
- **Auto-Assignment Queue**: Shows recordings needing review with pre-filled AI suggestions
- **Enhanced Database Schema**: New tables and columns for comprehensive speaker data storage
- **Sample Segment Storage**: Database stores first 5 speaking segments for quick speaker identification

### Changed
- **Database-Only Storage**: Eliminated `.speaker_assignments.json` sidecar files completely
- **Queue Building**: Now uses database queries instead of file scanning for 3-5x performance improvement
- **Speaker Attribution Tab**: Streamlined UI with enhanced learning-based suggestions
- **Assignment Workflow**: Simplified process with automatic pattern learning and suggestions

### Removed
- **Video-Specific Mappings**: Removed hardcoded video mappings in favor of learned patterns
- **Auto-Assign Speakers Button**: Functionality now integrated into queue building process
- **Export Attributed Button**: Feature consolidated into existing export functionality
- **Sidecar File Dependencies**: Complete elimination of file-based speaker assignment storage

### Fixed
- **Performance Issues**: Database queries much faster than file system scanning
- **Data Consistency**: Database storage prevents assignment loss and corruption
- **Memory Usage**: Optimized speaker data handling and storage
- **Learning Accuracy**: Enhanced pattern recognition improves suggestion quality over time

### Technical
- **Database Migration**: Automatic schema upgrade with new speaker-related tables
- **Enhanced Models**: Updated Pydantic and SQLAlchemy models with learning metadata
- **API Improvements**: Enhanced speaker processor methods with learning integration
- **Index Optimization**: Added database indexes for improved query performance

## [1.0.0] - 2025-08-18

### Added
- Intelligent quality detection with automatic retry
- Duration-based transcription validation
- Configurable retry attempts (0-3)
- Performance vs quality mode selection
- Real-time model download progress
- WebShare 402 payment error detection
- HuggingFace token input for speaker diarization
- Enhanced hardware recommendations layout

### Changed
- Removed "style" option from summarization (prompt-controlled)
- Improved Local Transcription tab layout
- Better hardware recommendation text formatting
- Enhanced progress tracking for all operations

### Fixed
- Audio transcription silent failures
- YouTube extraction error handling
- GUI layout issues in local transcription tab
- Process control and cancellation reliability

## [0.0.9] - 2024-07-21

### Added
- Initial release of Knowledge System
- PyQt6 desktop GUI application
- Audio transcription with Whisper.cpp
- YouTube video/playlist extraction
- Document summarization with AI
- Maps of Content (MOC) generation
- Speaker diarization support
- WebShare proxy integration
- Comprehensive test suite
- Cross-platform support (macOS optimized)
- Hardware-aware performance optimization
- Process control with pause/resume/cancel
- Intelligent text chunking for large documents
- File watcher for automated processing
- CLI interface for scripting
- Multiple AI provider support (OpenAI, Anthropic)
- Batch processing capabilities
- Progress tracking and reporting
- Error handling and recovery
- Extensive documentation

### Security
- API key protection
- Secure credential storage
- Input validation and sanitization 
