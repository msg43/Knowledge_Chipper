# Lazy Loading Diarization System

## Overview

The Knowledge Chipper system now uses lazy loading for speaker diarization features, reducing the initial installation size by **80%** (~377MB savings). Diarization dependencies are only installed when explicitly requested, making the system more lightweight and faster to deploy.

## Problem Solved

### Before: Heavy Initial Installation
- **torch**: 324MB
- **transformers**: 51MB  
- **pyannote.audio**: 1.9MB
- **Total**: ~377MB for diarization features

### After: Lightweight Core Installation
- **Core system**: ~50MB
- **Diarization**: Optional, installed only when needed
- **Total savings**: 80% reduction in initial install size

## Installation Options

### 1. Core Installation (Recommended)
```bash
# Lightweight installation without diarization
pip install -e .

# Or with GUI
pip install -e ".[gui]"
```

### 2. Full Installation with Diarization
```bash
# Complete installation with all features
pip install -e ".[full]"

# Or install diarization separately
pip install -e ".[diarization]"
```

### 3. Manual Diarization Installation
```bash
# Install diarization dependencies manually
pip install torch transformers pyannote.audio
```

## How Lazy Loading Works

### 1. Dependency Checking
```python
from knowledge_system.processors.diarization import is_diarization_available

if is_diarization_available():
    print("Diarization is available")
else:
    print("Diarization dependencies not installed")
```

### 2. Automatic Fallback
When diarization is requested but not available:
- System continues without diarization
- Clear error messages with installation instructions
- No crashes or broken functionality

### 3. On-Demand Loading
```python
# Dependencies are only loaded when actually used
processor = SpeakerDiarizationProcessor()
# No heavy imports until this point

result = processor.process(audio_file)
# Dependencies loaded here if available
```

## Benefits

### 🚀 **Installation Speed**
- **80% faster** initial installation
- **Reduced bandwidth** usage
- **Smaller download** size

### 💾 **Storage Efficiency**
- **377MB saved** in core installation
- **Optional features** only when needed
- **Better resource** utilization

### 🔧 **Development Experience**
- **Faster CI/CD** pipelines
- **Reduced test** environment size
- **Easier deployment** to containers

### 🎯 **User Experience**
- **Faster setup** for basic users
- **Clear installation** instructions
- **Graceful degradation** when features unavailable

## Usage Examples

### Basic Transcription (No Diarization)
```python
from knowledge_system.processors.audio_processor import AudioProcessor

# Works without diarization dependencies
processor = AudioProcessor(enable_diarization=False)
result = processor.process("audio.mp3")
```

### Transcription with Diarization
```python
from knowledge_system.processors.audio_processor import AudioProcessor

# Requires diarization dependencies
processor = AudioProcessor(enable_diarization=True)
result = processor.process("audio.mp3")
```

### Checking Diarization Availability
```python
from knowledge_system.processors.diarization import is_diarization_available

if is_diarization_available():
    print("✅ Diarization available")
else:
    print("❌ Diarization not available")
    print("Install with: pip install -e '.[diarization]'")
```

## GUI Integration

### Automatic Detection
The GUI automatically detects diarization availability:
- **Available**: Diarization checkbox is enabled
- **Not available**: Diarization checkbox is disabled with helpful message
- **Clear instructions**: Installation guidance provided

### User-Friendly Messages
```python
# When diarization is requested but not available
"Speaker diarization requires additional dependencies.

Install with: pip install -e '.[diarization]'

Or install manually:
  pip install torch transformers pyannote.audio

Note: This will add ~377MB to your installation size."
```

## Configuration

### Settings File
```yaml
# config/settings.yaml
transcription:
  diarization: false  # Default to false for lightweight install
  # Other settings...
```

### Environment Variables
```bash
# Enable diarization if available
export KNOWLEDGE_SYSTEM_DIARIZATION=true
```

## Error Handling

### Graceful Degradation
```python
# When diarization fails
try:
    result = processor.process(audio_file)
    if result.success:
        print("Transcription with diarization successful")
    else:
        print("Transcription successful, diarization failed")
except ImportError:
    print("Diarization not available, continuing without it")
```

### Clear Error Messages
- **Missing dependencies**: Clear installation instructions
- **Configuration issues**: Helpful troubleshooting steps
- **Runtime errors**: Detailed error information

## Performance Impact

### Installation Time
- **Core installation**: ~2-3 minutes
- **With diarization**: ~8-10 minutes
- **Bandwidth savings**: ~377MB download

### Runtime Performance
- **No impact** on core functionality
- **Diarization**: Only loaded when used
- **Memory usage**: Reduced for basic operations

## Migration Guide

### For Existing Users
1. **No breaking changes**: Existing code continues to work
2. **Optional upgrade**: Install diarization only if needed
3. **Clear instructions**: Migration guidance provided

### For New Users
1. **Start lightweight**: Install core system first
2. **Add features**: Install diarization when needed
3. **Clear documentation**: Step-by-step guides available

## Troubleshooting

### Common Issues

#### 1. Diarization Not Available
```bash
Error: Diarization dependencies not available
```
**Solution**: Install diarization dependencies
```bash
pip install -e ".[diarization]"
```

#### 2. Import Errors
```bash
ImportError: No module named 'torch'
```
**Solution**: Install PyTorch
```bash
pip install torch
```

#### 3. HuggingFace Token Issues
```bash
Error: HuggingFace token required
```
**Solution**: Configure HuggingFace token in settings

### Debug Mode
```python
import logging
logging.getLogger('knowledge_system.processors.diarization').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Improvements
1. **More granular dependencies**: Separate torch/transformers/pyannote
2. **Model caching**: Cache downloaded models
3. **Progress tracking**: Installation progress for large dependencies
4. **Auto-installation**: Automatic dependency installation on demand

### Potential Additions
1. **Alternative diarization**: Lightweight diarization options
2. **Cloud diarization**: Remote diarization services
3. **Model optimization**: Smaller, faster diarization models
4. **Batch processing**: Efficient batch diarization

## Conclusion

The lazy loading diarization system provides:

- ✅ **80% size reduction** in initial installation
- ✅ **Faster deployment** and setup
- ✅ **Better user experience** with clear instructions
- ✅ **Graceful degradation** when features unavailable
- ✅ **No breaking changes** to existing functionality

The system now offers a lightweight core installation with optional heavy features, making it more accessible to users who don't need speaker diarization while maintaining full functionality for those who do. 