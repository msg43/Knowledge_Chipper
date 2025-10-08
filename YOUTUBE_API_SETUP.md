# YouTube API Setup Guide

## Overview
The Knowledge Chipper system includes YouTube transcription functionality that requires YouTube API credentials to function. When these credentials are not configured, the system correctly skips YouTube-related tests and shows appropriate warning messages.

## Expected Behavior
When YouTube API credentials are not configured, you will see messages like:
```
⚠️  youtube_transcribe_Youtube_Playlists_1_no_diarization - Skipped (YouTube API access not available)
⚠️  youtube_transcribe_Youtube_Playlists_1_with_diarization - Skipped (YouTube API access not available)
```

This is **expected behavior** and not a bug.

## YouTube API Setup (Optional)

If you want to enable YouTube transcription functionality, follow these steps:

### 1. Create YouTube API Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3

### 2. Create API Credentials
1. Go to "Credentials" in the Google Cloud Console
2. Click "Create Credentials" → "API Key"
3. Copy the generated API key

### 3. Configure Knowledge Chipper
Add your YouTube API key to the Knowledge Chipper configuration:

**Option 1: Environment Variable**
```bash
export YOUTUBE_API_KEY="your_api_key_here"
```

**Option 2: Configuration File**
Add to your Knowledge Chipper config file:
```yaml
youtube:
  api_key: "your_api_key_here"
```

### 4. Test YouTube Functionality
After configuration, YouTube transcription tests should run successfully instead of being skipped.

## YouTube API Quotas
- YouTube Data API v3 has daily quotas
- Transcription requests count against your quota
- Monitor usage in the Google Cloud Console

## Troubleshooting
- **"API access not available"**: YouTube API key not configured
- **"Quota exceeded"**: Daily API limit reached
- **"Video not found"**: Invalid YouTube URL or private video

## Files Modified
- `tests/comprehensive_test_suite.py`: Fixed YouTube URL extraction from CSV files with headers
- YouTube URL extraction now handles both simple CSV files and CSV files with headers

## Test Results
With proper YouTube API configuration:
- ✅ YouTube transcription tests will run
- ✅ Playlist processing will work
- ✅ Video metadata extraction will function

Without YouTube API configuration:
- ⚠️ Tests are skipped (expected behavior)
- ⚠️ YouTube functionality is disabled
- ✅ System continues to work for other features
