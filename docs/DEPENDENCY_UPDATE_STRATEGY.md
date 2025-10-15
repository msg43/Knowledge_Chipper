# Dependency Update Strategy for yt-dlp

## The Problem

yt-dlp requires frequent updates to work with YouTube's changing API, BUT updates could introduce breaking changes. This creates a dilemma:
- **Too conservative**: System breaks when YouTube changes
- **Too aggressive**: Untested updates break your application

## Industry Best Practice: Staged Deployment

### 1. Development Environment (Aggressive Updates)
**Use**: `yt-dlp>=2025.9.26` (allow any newer version)

```bash
# Developer workflow
make update-ytdlp  # Update to latest
# Test manually
# Run automated tests
```

**Purpose**: Catch issues early, stay current with latest fixes

### 2. Production/Distribution (Conservative Pinning)
**Use**: `yt-dlp==2025.9.26` (exact version, tested and verified)

**Purpose**: Users only get versions you've tested and validated

### 3. Update Workflow

```
┌─────────────┐
│  Latest     │  Developer updates & tests
│  yt-dlp     │  (weekly or when YouTube breaks)
│  Released   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Developer  │  1. Run: make update-ytdlp
│  Testing    │  2. Test YouTube downloads
│             │  3. Run test suite
└──────┬──────┘
       │
       ▼ (passes)
┌─────────────┐
│  Update     │  Update pyproject.toml with
│  Pin        │  exact tested version
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Release    │  Build .dmg with pinned version
│  to Users   │  Users get tested version
└─────────────┘
```

## Implementation Options

### Option 1: Dual Requirements Files (Recommended)

**requirements-dev.txt** (for development):
```python
yt-dlp>=2025.9.26  # Allow updates for testing
```

**requirements.txt** (for production/users):
```python
yt-dlp==2025.9.26  # Exact version, tested
```

**pyproject.toml** (for package distribution):
```python
"yt-dlp==2025.9.26",  # Pin exact version for DMG
```

### Option 2: Environment Variables

```python
# In your dependency resolver
if os.getenv("ENVIRONMENT") == "development":
    install("yt-dlp>=2025.9.26")  # Latest
else:
    install("yt-dlp==2025.9.26")  # Pinned
```

### Option 3: Version Lock File (Like package-lock.json)

Use `pip freeze` to lock all versions:
```bash
pip freeze > requirements.lock
```

Developers can update, but production uses the lock file.

## Recommended Workflow for Your Project

### Weekly Update Cycle

**Monday Morning (Developer)**:
```bash
# 1. Update to latest
make update-ytdlp

# 2. Test with your test videos
knowledge-system youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 3. Run automated tests
make test-integration

# 4. Test batch processing
make test-youtube-batch

# 5. If all passes, update the pin
```

**Update the Pin**:
```python
# In pyproject.toml (single source of truth)
"yt-dlp==2025.9.26",  # Update to new tested version
```

**Commit and Release**:
```bash
git add pyproject.toml
git commit -m "Update yt-dlp to 2025.9.26 (tested)"
# Build and release
```

### Emergency "YouTube Broke" Workflow

When YouTube changes break downloads:

```bash
# 1. Update immediately
make update-ytdlp

# 2. Quick smoke test (5 minutes)
knowledge-system youtube [test-video]

# 3. If works, emergency patch release
# Update pin, build, release

# 4. Full testing can happen post-release
# (better to ship working-but-untested than broken-but-stable)
```

## Automated Testing Strategy

### Pre-Release Testing (CI/CD)

```yaml
# .github/workflows/test-ytdlp.yml
name: Test yt-dlp Updates

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:

jobs:
  test-ytdlp-update:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install with latest yt-dlp
        run: |
          pip install yt-dlp --upgrade
          pip install -e .
      
      - name: Test YouTube downloads
        run: |
          pytest tests/test_youtube_integration.py
      
      - name: Create PR if tests pass
        if: success()
        run: |
          # Auto-create PR to update pinned version
          YTDLP_VERSION=$(pip show yt-dlp | grep Version | awk '{print $2}')
          # Update pyproject.toml
          # Create PR with new version
```

### User-Side Safety Net

For the distributed app, consider a fallback mechanism:

```python
# In youtube_download.py
def download_youtube_video(url: str):
    try:
        # Try with bundled yt-dlp
        return _download_with_ytdlp(url)
    except YoutubeDLError as e:
        if "signature" in str(e) or "extraction" in str(e):
            # Likely YouTube API changed
            logger.warning("yt-dlp may be outdated, checking for updates...")
            
            if user_confirms_update():
                update_ytdlp()
                return _download_with_ytdlp(url)
            else:
                raise UpdateRequiredError(
                    "YouTube download failed. Please update the application."
                )
        raise
```

## Monitoring and Alerting

### 1. Track yt-dlp Releases
Monitor: https://github.com/yt-dlp/yt-dlp/releases

Set up GitHub notifications for new releases.

### 2. Error Tracking
Log YouTube download failures separately:
```python
if youtube_download_failed:
    logger.error(
        "YouTube download failed",
        extra={
            "ytdlp_version": ytdlp.__version__,
            "error_type": error.__class__.__name__,
            "url": url,
        }
    )
```

### 3. User Feedback Channel
Have users report YouTube issues quickly (they'll notice first).

## Version Pinning Strategies by Risk Tolerance

### Conservative (Lowest Risk)
```python
"yt-dlp==2025.9.26"  # Exact version only
```
- **Pro**: Predictable, tested
- **Con**: Manual updates required, breaks when YouTube changes

### Moderate (Balanced)
```python
"yt-dlp>=2025.9.26,<2026.0.0"  # Allow minor updates
```
- **Pro**: Gets bug fixes automatically
- **Con**: Some risk of breakage

### Aggressive (Highest Current)
```python
"yt-dlp>=2025.9.26"  # Any newer version
```
- **Pro**: Always current
- **Con**: Untested versions in production

## Recommendation for Knowledge Chipper

Use **Conservative Pinning with Weekly Testing**:

1. **Development**: Use `>=` to test latest
2. **Production DMG**: Pin exact tested version
3. **Update Rhythm**: Weekly testing + emergency patches
4. **Safety Net**: Clear error messages telling users to update app

This balances:
- User stability (pinned versions)
- Developer awareness (testing latest)
- Quick response (emergency patch workflow)

## Example: requirements-dev.txt vs requirements.txt

Create separate files:

**requirements-dev.txt**:
```python
# Development dependencies - allow updates
yt-dlp>=2025.9.26  # Test with latest

# Include base requirements
-r requirements.txt
```

**requirements.txt**:
```python
# Production dependencies - pinned versions
yt-dlp==2025.9.26  # Tested and verified
# ... other deps
```

**Developer workflow**:
```bash
pip install -r requirements-dev.txt  # Gets latest yt-dlp for testing
```

**Build workflow**:
```bash
pip install -r requirements.txt  # Uses pinned version
```

## Final Recommendation

For a desktop application distributed as DMG:

1. ✅ **Pin exact versions** in releases
2. ✅ **Test updates weekly** in development
3. ✅ **Emergency patch** when YouTube breaks
4. ❌ **Never auto-update** in user's installation
5. ✅ **Monitor yt-dlp releases** for critical updates
6. ✅ **Have clear update instructions** for users

This is how major desktop apps (VS Code, Slack, etc.) handle critical dependencies.
