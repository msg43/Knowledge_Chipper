# Changelog

All notable changes to the Knowledge System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Improved Audio Transcription tab layout
- Better hardware recommendation text formatting
- Enhanced progress tracking for all operations

### Fixed
- Audio transcription silent failures
- YouTube extraction error handling
- GUI layout issues in transcription tab
- Process control and cancellation reliability

## [1.0.0] - 2024-07-21

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
