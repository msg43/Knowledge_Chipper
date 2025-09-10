# YouTube Cookie Setup Guide

## Why Cookies Are Needed

YouTube has implemented aggressive bot detection that blocks automated downloads, even when using residential proxies. Using your browser's YouTube cookies allows the system to authenticate as "you" rather than as a bot.

## Quick Setup Options

### Option 1: Automatic Browser Cookie Import (Easiest)
The system will automatically try to import cookies from your browsers in this order:
1. Chrome
2. Safari  
3. Firefox
4. Brave
5. Edge
6. Opera

**Note**: On macOS, you may be prompted for your password to access browser cookies.

### Option 2: Manual Cookie File (Most Reliable)

1. **Install a browser extension**:
   - Chrome: "Get cookies.txt LOCALLY" 
   - Firefox: "cookies.txt"
   - Safari: "Cookies.txt"

2. **Log into YouTube** in your browser

3. **Export cookies**:
   - Click the extension icon while on youtube.com
   - Save/export the cookies

4. **Save the file** in one of these locations:
   - `~/.config/knowledge_system/cookies.txt` (recommended)
   - `~/.knowledge_system/cookies.txt`
   - `./cookies.txt` (in your project directory)
   - `./config/cookies.txt`

## How It Works

With cookies enabled, the system will:
1. First check for a manual `cookies.txt` file
2. If not found, try to import cookies from your browsers
3. Use the cookies to authenticate YouTube requests
4. Combine cookies with proxy rotation for best results

## Benefits

- **Bypasses bot detection**: YouTube sees you as a logged-in user
- **Works with parallel downloads**: Each session uses the same cookies but different IPs
- **Persistent**: Manual cookie files work until they expire (usually weeks/months)
- **Safe**: Only session cookies are used, not passwords

## Troubleshooting

### "Sign in to confirm you're not a bot" error
This means cookies aren't being used or have expired. Create a fresh `cookies.txt` file.

### "407 Proxy Authentication Required" error  
This is a proxy configuration issue, not related to cookies.

### Cookies expire
YouTube cookies typically last 1-2 months. When they expire, just export new ones.

## Security Notes

- Cookie files contain session tokens, not passwords
- Keep your `cookies.txt` file private
- Cookies expire automatically
- The system only uses cookies for youtube.com

## Testing Your Setup

After setting up cookies, try downloading a single video. You should see:
```
🍪 Using authentication strategy: ['cookiefile'] 
```
or
```
🍪 Using authentication strategy: ['cookiejar']
```

This confirms cookies are being used.
