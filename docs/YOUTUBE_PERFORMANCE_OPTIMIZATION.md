# YouTube Processing Performance Optimization

## Problem: Slow YouTube URL Processing

If you're experiencing slow YouTube URL processing (e.g., 30 seconds for 3 videos), this is likely due to hardcoded delays that were implemented to avoid rate limiting. These delays are unnecessary when using rotating proxies.

## Solution: Configure YouTube Processing Delays

The Knowledge System now supports configurable delays for YouTube processing. You can disable these delays when using rotating proxies to dramatically speed up processing.

### Quick Fix: Disable Delays with Proxies

1. Copy the provided configuration file:
   ```bash
   cp config/disable_youtube_delays.yaml config/settings.yaml
   ```

2. Make sure your proxy credentials are set:
   ```bash
   export WEBSHARE_USERNAME="your_username"
   export WEBSHARE_PASSWORD="your_password"
   ```

3. Run your YouTube processing - it should be much faster!

### Manual Configuration

Add this to your `config/settings.yaml`:

```yaml
youtube_processing:
  # Automatically disable delays when rotating proxies are available
  disable_delays_with_proxy: true
  
  # Or manually set all delays to 0
  metadata_delay_min: 0.0
  metadata_delay_max: 0.0
  transcript_delay_min: 0.0
  transcript_delay_max: 0.0
  api_batch_delay_min: 0.0
  api_batch_delay_max: 0.0
  
  # Don't use delays even when proxies are configured
  use_proxy_delays: false
```

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `disable_delays_with_proxy` | Automatically disable delays when WebShare proxies are configured | `false` |
| `use_proxy_delays` | Whether to use delays when proxies are configured | `true` |
| `metadata_delay_min/max` | Delay range for metadata requests (seconds) | `0.5-2.0` |
| `transcript_delay_min/max` | Delay range for transcript requests (seconds) | `1.0-3.0` |
| `api_batch_delay_min/max` | Delay range for API batch requests (seconds) | `1.0-3.0` |

### Expected Performance Improvement

**Before (with delays):**
- 3 videos: ~30 seconds (includes 4.5-15 seconds of pure delay time)
- Each video: ~1.5-5.0 seconds in delays alone

**After (no delays with proxies):**
- 3 videos: ~5-10 seconds (actual processing time only)
- Each video: No artificial delays, just processing time

### When to Use Delays

Keep delays enabled (`disable_delays_with_proxy: false`) when:
- Not using rotating proxies
- Experiencing rate limiting issues
- Processing large batches without proxy rotation
- YouTube starts blocking your requests

### Troubleshooting

If you still experience slow processing:

1. **Verify proxy configuration:**
   ```bash
   # Check if credentials are set
   echo $WEBSHARE_USERNAME
   echo $WEBSHARE_PASSWORD
   ```

2. **Check logs for delay messages:**
   - Look for "Skipping delay - using rotating proxies" (delays disabled)
   - Look for "Adding X.XXs delay to avoid rate limiting" (delays active)

3. **Test with a single video first:**
   ```bash
   knowledge-system transcribe "https://youtu.be/VIDEO_ID" --verbose
   ```

4. **Monitor for rate limiting:**
   - If you get blocked, re-enable delays temporarily
   - Consider using smaller batch sizes

### Background

The original delays were implemented to avoid YouTube's rate limiting:
- Metadata requests: 0.5-2 seconds per video
- Transcript requests: 1-3 seconds per video  
- API batches: 1-3 seconds between batches

With rotating proxies, these delays are no longer necessary as each request appears to come from a different IP address, effectively bypassing rate limiting. 