# YouTube API Setup Guide

## Why This Is Needed

YouTube has significantly tightened their bot detection, making it nearly impossible to scrape transcripts without triggering "Sign in to confirm you're not a bot" errors. The official YouTube Data API v3 is the most reliable solution.

## Step 1: Get a YouTube API Key

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create a new project** or select an existing one
3. **Enable the YouTube Data API v3**:
   - Go to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. **Create credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the API key

## Step 2: Add Your API Key

Choose one of these methods:

### Method A: Environment Variable (Recommended)
```bash
export YOUTUBE_API_KEY="your_api_key_here"
```

### Method B: Config File
Create `config/youtube_api_key.txt`:
```
your_api_key_here
```

### Method C: Settings File
Add to `config/settings.yaml`:
```yaml
youtube_api_key: "your_api_key_here"
```

## Step 3: Test the API

Run this command to test:
```bash
python -c "from src.knowledge_system.utils.youtube_api import get_youtube_transcript_api; result = get_youtube_transcript_api('https://youtu.be/dQw4w9WgXcQ'); print('Success!' if result else 'No transcript available')"
```

## API Quota

- **Free tier**: 10,000 requests per day
- **Cost**: $5 per 1,000 additional requests
- **Typical usage**: ~1 request per video transcript

## Benefits

✅ **No bot detection issues**  
✅ **Reliable and stable**  
✅ **Official Google support**  
✅ **Works with all videos**  
✅ **No browser authentication needed**  

## Fallback Options

If you prefer not to use the API, you can still try:

1. **Manual cookie export** from your browser
2. **Use a VPN** to avoid IP-based blocking
3. **Wait for yt-dlp updates** that might bypass new protections

The API approach is recommended for production use. 