# FFmpeg Version Requirement

## Current Requirement: Any modern FFmpeg version

This project works with **any modern FFmpeg version** (4.x, 5.x, 6.x, 7.x, or 8.x).

### FFmpeg Usage

The project uses FFmpeg for:
- Audio format conversion (WEBM/M4A → WAV)
- Audio normalization
- Metadata extraction

All these features work identically across FFmpeg versions 4-8.

## Installation

### macOS (Homebrew)

```bash
# Install the latest FFmpeg
brew install ffmpeg

# Verify installation
ffmpeg -version
```

If you already have an older FFmpeg version:

```bash
# Upgrade to latest
brew upgrade ffmpeg
```

## For GUI Users

The GUI installer automatically downloads and installs FFmpeg to a user-space location. No manual FFmpeg installation is required.

## Troubleshooting

### Error: FFmpeg not found

Install FFmpeg using your system's package manager:

**macOS**: `brew install ffmpeg`  
**Ubuntu/Debian**: `sudo apt install ffmpeg`  
**Windows**: Download from https://ffmpeg.org/download.html

### Error: "AudioDecoder is not defined" (Historical)

This error was related to the now-removed torchcodec dependency. If you see this error in logs, it can be safely ignored as the system uses torchaudio for audio loading.

## Related Documentation

- `FFMPEG_VERSION_ANALYSIS.md` - Detailed analysis of FFmpeg usage
- `TORCHCODEC_FFMPEG_ROOT_CAUSE_AND_SOLUTION.md` - Technical deep dive
- `AUDIODECODER_FIX.md` - Original issue investigation

