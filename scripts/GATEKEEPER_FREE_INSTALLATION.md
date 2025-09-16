# Skip the Podcast Desktop - Gatekeeper-Free Installation

## The Problem
Your DMG triggers Gatekeeper because it was downloaded through a browser, which adds a quarantine flag.

## The Solution
Use one of these installers that download directly, bypassing quarantine:

### Option 1: Bash Installer (Recommended)
```bash
curl -sSL https://your-website.com/install_skip_the_podcast.sh | bash
```

Or download and run:
```bash
curl -O https://your-website.com/install_skip_the_podcast.sh
chmod +x install_skip_the_podcast.sh
./install_skip_the_podcast.sh
```

### Option 2: Python Installer
```bash
curl -O https://your-website.com/install_skip_the_podcast.py
python3 install_skip_the_podcast.py
```

### Option 3: Direct Terminal Commands
```bash
# Download DMG without quarantine
curl -L -o skip.dmg "https://github.com/skipthepodcast/desktop/releases/latest/download/Skip_the_Podcast_Desktop.dmg"

# Mount it
hdiutil attach skip.dmg

# Copy to Applications
cp -R "/Volumes/Skip the Podcast Desktop/Skip the Podcast Desktop.app" /Applications/

# Unmount and clean up
hdiutil detach "/Volumes/Skip the Podcast Desktop"
rm skip.dmg

# Launch
open -a "Skip the Podcast Desktop"
```

## Why This Works

1. **No Quarantine**: Files downloaded via `curl` or `urllib` don't get quarantine flags
2. **No Gatekeeper**: Without quarantine, Gatekeeper doesn't check the app
3. **Clean Install**: App appears in Applications and just works

## For Your Website

Add this to your download page:

```html
<h3>Having trouble with security warnings?</h3>
<p>Use our direct installer:</p>
<pre><code>curl -sSL https://your-site.com/install | bash</code></pre>
```

## Testing

1. Upload these installer scripts to your server
2. Test with: `curl -sSL https://your-server/install_skip_the_podcast.sh | bash`
3. App installs and launches with NO Gatekeeper warnings!
