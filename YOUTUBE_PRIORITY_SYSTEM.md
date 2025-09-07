# YouTube Metadata Extraction Priority System

## 🎯 **Current Configuration**

The YouTube metadata processor now uses a **priority-based extraction system** that prioritizes **PacketStream** while conserving **Bright Data** code for future use.

## 🥇 **Priority Order**

### 1. **PacketStream Proxy + yt-dlp** (PRIMARY)
- **Status**: ✅ **ACTIVE** - Always tried first
- **Method**: Residential proxy with yt-dlp
- **Benefits**: 
  - Avoids bot detection
  - Scales to hundreds of URLs
  - Cost-effective per-GB pricing
- **Configuration**: Set via GUI Settings tab
- **Fallback**: If fails, tries next method

### 2. **Direct yt-dlp** (FALLBACK)
- **Status**: ⚠️ **CONDITIONAL** - Only for ≤2 videos
- **Method**: Direct yt-dlp without proxy
- **Reason**: Small batches unlikely to trigger bot detection
- **Limitation**: Disabled for >2 videos to prevent IP blocking
- **Fallback**: If fails, extraction fails completely

### 3. **Bright Data API** (CONSERVED)
- **Status**: 🚫 **DISABLED** - Code preserved but not invoked
- **Method**: Bright Data YouTube API Scraper
- **Reason**: Currently not in use per user preference
- **Code Status**: Fully preserved and functional
- **Re-activation**: Uncomment lines in `_extract_metadata_unified()`

## 🔧 **Implementation Details**

### File: `src/knowledge_system/processors/youtube_metadata.py`

```python
def _extract_metadata_unified(self, url: str, total_urls: int = 1) -> YouTubeMetadata | None:
    """
    Extract metadata with priority system:
    1. PacketStream (primary)
    2. Direct yt-dlp (fallback for ≤2 videos)  
    3. Bright Data (conserved but disabled)
    """
    
    # Method 1: PacketStream (ALWAYS TRIED)
    try:
        metadata = self._extract_metadata_packetstream(url)
        if metadata:
            return metadata
    except Exception as e:
        # Log and continue to fallback
    
    # Method 2: Direct yt-dlp (ONLY FOR ≤2 VIDEOS)
    if total_urls <= 2:
        try:
            metadata = self._extract_metadata_direct_ytdlp(url)
            if metadata:
                return metadata
        except Exception as e:
            # Log and continue
    
    # Method 3: Bright Data (DISABLED)
    # Code preserved but commented out
    # Uncomment to re-enable:
    # try:
    #     metadata = self._extract_metadata_bright_data(url)
    #     if metadata:
    #         return metadata
    # except Exception as e:
    #     pass
    
    return None  # All methods failed
```

## 📊 **Behavior by Batch Size**

| Batch Size | PacketStream | Direct yt-dlp | Bright Data | Reason |
|------------|--------------|---------------|-------------|---------|
| **1 video** | ✅ Tried first | ✅ Fallback | 🚫 Disabled | Safe for direct |
| **2 videos** | ✅ Tried first | ✅ Fallback | 🚫 Disabled | Safe for direct |
| **3+ videos** | ✅ Tried first | 🚫 Skipped | 🚫 Disabled | Bot detection risk |

## 🛡️ **Bot Detection Strategy**

- **1-2 videos**: Low risk, direct yt-dlp acceptable as fallback
- **3+ videos**: High risk, only proxied requests (PacketStream)
- **No Bright Data calls**: Avoids API costs and complexity

## ⚙️ **Configuration**

### PacketStream Setup
1. Go to **Settings → API Keys** tab
2. Enter **PacketStream Username**
3. Enter **PacketStream Auth Key**
4. Credentials saved to `config/credentials.yaml` (gitignored)

### Re-enabling Bright Data (if needed)
1. Open `src/knowledge_system/processors/youtube_metadata.py`
2. Find `_extract_metadata_unified()` method
3. Uncomment the Bright Data section (lines ~428-436)
4. Ensure Bright Data API key is configured

## 🎯 **User Benefits**

✅ **PacketStream Priority**: Reliable, scalable, cost-effective  
✅ **Smart Fallbacks**: Direct access for small batches  
✅ **Code Preservation**: Bright Data ready for future use  
✅ **Bot Avoidance**: Intelligent batch size detection  
✅ **Zero Data Loss**: Bright Data code fully preserved  

## 🔄 **Migration Path**

If you want to switch back to Bright Data:
1. Uncomment Bright Data code in `_extract_metadata_unified()`
2. Ensure Bright Data API key is configured
3. Optionally move it higher in priority order
4. Test with a few URLs first

The system is designed for **easy reconfiguration** while maintaining **reliability** and **cost control**.
