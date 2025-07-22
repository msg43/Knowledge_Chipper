# YouTube OAuth2 Authentication Setup

This guide explains how to set up OAuth2 authentication for full access to YouTube captions in your Knowledge System app.

## Why OAuth2?

OAuth2 provides **full access** to YouTube captions, while API keys have limitations:

- **API Key**: Can only fetch video information, **cannot access captions**
- **OAuth2**: Full access to captions, video info, and other YouTube features

## Prerequisites

1. Google Cloud Console account
2. A Google Cloud project with YouTube Data API v3 enabled

## Step-by-Step Setup

### 1. Create OAuth2 Credentials in Google Cloud Console

1. **Go to Google Cloud Console**: https://console.cloud.google.com/apis/credentials
2. **Create or select a project**
3. **Enable YouTube Data API v3**:
   - Go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. **Create OAuth2 credentials**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client IDs"
   - Choose "Desktop application" as the application type
   - Give it a name (e.g., "Knowledge System YouTube Access")
   - Click "Create"
5. **Download the credentials**:
   - Click the download button next to your new OAuth client
   - Save the file as `client_secret.json` in your project directory

### 2. Configure OAuth2 in the App

#### Option A: Using the GUI (Recommended)

1. **Launch the app**: `python -m knowledge_system.gui`
2. **Go to Settings tab**
3. **Find "YouTube OAuth2 Authentication" section**
4. **Enable OAuth2**: Check the "Enable OAuth2" checkbox
5. **Select client secret file**: Click "Browse" and select your `client_secret.json`
6. **Save settings**: Click "Save Settings"
7. **Authenticate**: Click "🔐 Authenticate"
   - Your browser will open for Google sign-in
   - Sign in with your Google account
   - Grant permissions to the app
   - Return to the app (authentication complete)
8. **Test**: Click "🧪 Test" to verify authentication works

#### Option B: Using the Utilities Tab

1. **Go to Utilities tab**
2. **Click "🔐 Quick OAuth2 Setup"**
3. **Follow the setup instructions**
4. **Complete setup in Settings tab**

### 3. Verify Setup

1. **Check status**: In Settings tab, OAuth2 status should show "✅ Authenticated"
2. **Test with a video**: Try processing a YouTube video with captions
3. **Check logs**: Look for "OAuth2" messages in the app logs

## Using OAuth2

Once set up, OAuth2 will be used automatically when:

1. **OAuth2 is enabled** in settings
2. **Processing YouTube videos** that have captions
3. **API-first mode** is enabled (default)

The app will try OAuth2 first, then fall back to yt-dlp if needed.

## Authentication Flow

```
YouTube Video URL
       ↓
1. OAuth2 enabled? → Try OAuth2 authentication
       ↓
2. Get video captions via YouTube API
       ↓
3. Success? → Return transcript
       ↓
4. Failed? → Fall back to yt-dlp method
```

## Troubleshooting

### "Authentication failed"
- **Check client_secret.json**: Ensure file is valid and not corrupted
- **Check permissions**: Make sure you granted all requested permissions
- **Re-authenticate**: Click "🗑️ Revoke" then "🔐 Authenticate" again

### "No captions available"
- **Check video**: Not all videos have captions
- **Check language**: Try different language settings
- **Manual vs Auto**: Some videos only have auto-generated captions

### "Client secrets file not found"
- **Check file path**: Ensure `client_secret.json` is in the correct location
- **Re-download**: Download the file again from Google Cloud Console
- **Check permissions**: Ensure the app can read the file

### "API access failed"
- **Check API quota**: You may have exceeded API limits
- **Check project**: Ensure YouTube Data API v3 is enabled
- **Check credentials**: Verify OAuth client is properly configured

## Advanced Configuration

### Manual Configuration

You can also configure OAuth2 manually by editing `config/settings.yaml`:

```yaml
api_keys:
  youtube_oauth2_enabled: true
  youtube_client_secret_file: "config/client_secret.json"
```

### Credential Storage

OAuth2 credentials are stored in:
- **File**: `config/youtube_oauth2_credentials.json`
- **Contains**: Access token, refresh token, expiry information
- **Security**: Keep this file secure and don't share it

### Revoking Access

To revoke OAuth2 access:

1. **In the app**: Settings tab → "🗑️ Revoke" button
2. **In Google**: https://myaccount.google.com/permissions
   - Find your app and revoke access

## Comparison: OAuth2 vs API Key vs yt-dlp

| Method | Video Info | Captions | Rate Limits | Setup Complexity |
|--------|------------|----------|-------------|------------------|
| **OAuth2** | ✅ Yes | ✅ Yes | High quota | Medium |
| **API Key** | ✅ Yes | ❌ No | Medium quota | Low |
| **yt-dlp** | ✅ Yes | ✅ Yes | Bot detection | None |

## Best Practices

1. **Use OAuth2 for bulk processing**: Higher rate limits than yt-dlp
2. **Keep credentials secure**: Don't share or commit credential files
3. **Monitor quotas**: Check Google Cloud Console for API usage
4. **Have fallbacks**: Keep yt-dlp as backup method
5. **Test regularly**: Verify authentication hasn't expired

## API Quotas

YouTube Data API v3 has the following quotas:
- **Default quota**: 10,000 units per day
- **Caption download**: ~200 units per video
- **Video info**: ~1 unit per video

**Request quota increase** if you need higher limits.

## Support

If you encounter issues:

1. **Check logs**: Look for detailed error messages
2. **Test with simple video**: Try a known working YouTube video
3. **Verify setup**: Use the "🧪 Test" button in Settings
4. **Re-authenticate**: Sometimes credentials need refreshing

---

**Note**: OAuth2 provides the most reliable access to YouTube captions and is recommended for regular use. 