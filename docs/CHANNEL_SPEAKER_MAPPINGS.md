# Channel-Based Speaker Mapping Guide

## Overview

The Channel-Based Speaker Mapping system automatically expands partial speaker names to full proper names based on the YouTube channel hosting the content. This is especially powerful for podcast channels with consistent hosts.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  1. LLM analyzes transcript                                 │
│     Speaker says: "Hi, I'm Tony..."                         │
│     LLM suggests: "Tony" (confidence: 0.7)                  │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  2. System checks channel metadata                          │
│     Channel: "China Update"                                 │
│     Looks up channel in speaker_attribution.yaml            │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  3. Channel mapping applied                                 │
│     "Tony" matches partial_names: ["Tony", "Anthony", "AJ"] │
│     Maps to full_name: "Anthony Johnson"                    │
│     Confidence upgraded: 0.7 -> 0.95                        │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│  4. Final result                                            │
│     Speaker assigned: "Anthony Johnson"                     │
│     High confidence = auto-applied without user review      │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Edit `/config/speaker_attribution.yaml`:

```yaml
channel_mappings:
  "China Update":
    hosts:
      - full_name: "Anthony Johnson"
        partial_names: ["Tony", "Anthony", "AJ"]
        role: "host"
  
  "Eurodollar University":
    hosts:
      - full_name: "Jeff Snider"
        partial_names: ["Jeff", "Jeffrey"]
        role: "host"
      - full_name: "Emil Kalinowski"
        partial_names: ["Emil", "Em"]
        role: "co-host"
  
  "Your Podcast Name":
    hosts:
      - full_name: "Full Proper Name"
        partial_names: ["Short", "Nick", "Variations"]
        role: "host"
```

## Configuration Fields

| Field | Description | Example |
|-------|-------------|---------|
| **Channel Name** | YouTube channel name (case-insensitive, partial match) | `"China Update"` |
| **full_name** | Complete proper name to assign | `"Anthony Johnson"` |
| **partial_names** | List of name variations to match | `["Tony", "Anthony", "AJ"]` |
| **role** | Speaker's role (optional, for documentation) | `"host"`, `"co-host"`, `"regular_guest"` |

## Matching Rules

The system matches partial names using **fuzzy matching**:

1. **Exact match**: `"Tony"` == `"tony"` ✅
2. **Substring match**: `"Tony"` in `"Tony Smith"` ✅
3. **Contained match**: `"tony"` in `"I'm Tony"` ✅
4. **Case-insensitive**: `"TONY"` matches `"tony"` ✅

### Examples:

| LLM Suggestion | Partial Names | Match? | Result |
|----------------|---------------|--------|---------|
| `"Tony"` | `["Tony", "Anthony"]` | ✅ Yes | `"Anthony Johnson"` |
| `"I'm Tony"` | `["Tony"]` | ✅ Yes | `"Anthony Johnson"` |
| `"Anthony"` | `["Tony", "Anthony"]` | ✅ Yes | `"Anthony Johnson"` |
| `"Jeff Snider"` | `["Jeff"]` | ✅ Yes | `"Jeff Snider"` (already full) |
| `"Emily"` | `["Emil"]` | ❌ No | `"Emily"` (no match) |

## Use Cases

### Single Host Podcast
```yaml
"The Daily Show":
  hosts:
    - full_name: "Trevor Noah"
      partial_names: ["Trevor", "Noah"]
      role: "host"
```

### Multiple Co-Hosts
```yaml
"The Podcast Brothers":
  hosts:
    - full_name: "John Smith"
      partial_names: ["John", "Johnny"]
      role: "host"
    - full_name: "Mike Johnson"
      partial_names: ["Mike", "Michael"]
      role: "co-host"
```

### Host + Regular Guest
```yaml
"Financial News Network":
  hosts:
    - full_name: "Sarah Williams"
      partial_names: ["Sarah", "Williams"]
      role: "host"
    - full_name: "Dr. Robert Chen"
      partial_names: ["Robert", "Bob", "Dr. Chen"]
      role: "regular_guest"
```

## Priority System

Channel mappings have **highest priority** in the speaker assignment pipeline:

1. **Channel Mapping** (0.95 confidence) - Applied FIRST
2. Conversational Context Analysis (0.8-0.9 confidence)
3. LLM Suggestions (0.5-0.9 confidence)
4. Fallback Names (0.3 confidence)

This means channel mappings **override** LLM suggestions when there's a match.

## When It Applies

Channel mapping applies when:
- ✅ Channel is configured in `speaker_attribution.yaml`
- ✅ Channel name matches (case-insensitive, partial)
- ✅ LLM suggested name matches a partial name
- ✅ Metadata contains channel information (`uploader` field)

Channel mapping does NOT apply when:
- ❌ Channel not configured
- ❌ No metadata available
- ❌ LLM suggested name doesn't match any partial names
- ❌ Audio is uploaded file (no channel info)

## Benefits

| Scenario | Without Channel Mapping | With Channel Mapping |
|----------|------------------------|---------------------|
| Speaker says "I'm Tony" | LLM suggests: "Tony" (0.7 conf) → User must verify | Auto-mapped: "Anthony Johnson" (0.95 conf) → Auto-applied ✅ |
| Speaker says "Hi, I'm Jeff" | LLM suggests: "Jeff" (0.6 conf) → Might trigger fallback | Auto-mapped: "Jeff Snider" (0.95 conf) → Auto-applied ✅ |
| Whisper transcription error: "I'm Stacy Rasgon" | LLM suggests: "Stacey Raskin" (0.5 conf) | Channel mapping corrects phonetic errors ✅ |

## Adding Your Own Channels

1. Open `/config/speaker_attribution.yaml`
2. Add your channel under `channel_mappings`:

```yaml
channel_mappings:
  # Your channel here
  "My Awesome Podcast":
    hosts:
      - full_name: "Your Full Name"
        partial_names: ["Your", "First", "Nick"]
        role: "host"
  
  # Existing channels
  "China Update":
    hosts:
      - full_name: "Anthony Johnson"
        partial_names: ["Tony", "Anthony", "AJ"]
        role: "host"
```

3. Save the file
4. Next transcription will automatically use the new mapping

## Logging

When channel mapping is applied, you'll see these log messages:

```
📺 Found channel mapping for: China Update
🎯 Channel mapping: 'Tony' -> 'Anthony Johnson' (channel: China Update)
✅ Applied channel-based speaker mappings for China Update
```

When no mapping is found:

```
No channel mappings configured for channel: Random Channel Name
```

## Database Learning

Channel mappings are **static** (defined in YAML), but the system also has a **dynamic learning system** that:

1. Remembers user-corrected speaker names
2. Stores them in the speaker assignments database
3. Auto-applies them on future transcriptions from the same audio file

Channel mappings complement database learning by providing **channel-wide defaults** before any user corrections.

## Best Practices

### ✅ DO:
- Use full proper names (e.g., "Anthony Johnson", not "Tony")
- Include common variations and nicknames in `partial_names`
- Use case-insensitive matching (system handles this automatically)
- Update mappings when hosts change

### ❌ DON'T:
- Don't use generic names (e.g., "Host", "Guest")
- Don't duplicate entries (one host per channel, unless co-hosts)
- Don't use overly long channel names (partial matching works)

## Troubleshooting

**Q: Channel mapping not applying?**
- Check channel name in metadata (logs show: `Found channel mapping for: ...`)
- Verify channel name in YAML matches (case-insensitive, partial match OK)
- Ensure LLM suggested name matches a partial name

**Q: Wrong person mapped?**
- Check if multiple hosts have overlapping partial names
- Make partial names more specific
- User can always override in the speaker assignment dialog

**Q: How do I find the exact channel name?**
- Run a transcription
- Check logs for: `Retrieved YouTube metadata for VIDEO_ID: CHANNEL_NAME`
- Or check the database `media_sources` table, `uploader` field

## Example Workflow

1. **Download video** from "China Update" channel
2. **Transcribe** with diarization enabled
3. **LLM analyzes** transcript, detects "Tony" in first segment
4. **Channel mapping** checks: "China Update" channel
5. **Matches** "Tony" to `partial_names: ["Tony", "Anthony", "AJ"]`
6. **Maps** to `full_name: "Anthony Johnson"`
7. **Upgrades** confidence from 0.7 to 0.95
8. **Auto-applies** without user intervention
9. **Transcript saved** with "Anthony Johnson" as speaker
10. **HCE processing** extracts claims attributed to "Anthony Johnson"

---

## Summary

Channel-based speaker mapping is a powerful feature that:
- ✅ Eliminates manual speaker verification for known channels
- ✅ Corrects transcription errors (phonetic mistakes)
- ✅ Expands partial names to full proper names
- ✅ Works automatically without user intervention
- ✅ Integrates seamlessly with voice fingerprinting and LLM analysis

Perfect for podcast channels with consistent hosts!

