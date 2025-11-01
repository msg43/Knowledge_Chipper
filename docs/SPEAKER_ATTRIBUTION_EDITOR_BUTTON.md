# Speaker Attribution Editor Button

**Date:** October 31, 2025  
**Status:** ✅ Complete  
**Location:** Settings Tab → "🎤 Edit Speaker Mappings" Button

## Overview

Added a convenient button to the Settings tab that allows users to directly open and edit the `speaker_attribution.yaml` file, which contains channel-to-speaker mappings for improved speaker recognition in transcriptions.

## Implementation Details

### Location

The button is placed in the Settings tab (API Keys tab) after the "Show Introduction Tab At Launch" checkbox, grouped with other settings controls.

### Features

1. **One-Click Access**
   - Opens `config/speaker_attribution.yaml` in the system's default text editor
   - No need to navigate file system manually

2. **Platform Support**
   - **macOS**: Uses `open` command
   - **Windows**: Uses `start` command
   - **Linux**: Uses `xdg-open` command

3. **User Guidance**
   - Tooltip explains what the file does and how to use it
   - Informational dialog shows after opening with:
     - File location
     - Edit instructions
     - Example format
     - Confirmation that changes take effect immediately

4. **Error Handling**
   - Validates file exists before attempting to open
   - Shows helpful error messages if file not found
   - Catches and reports any subprocess errors

### Button Styling

```python
QPushButton {
    background-color: #9C27B0;  # Purple color
    color: white;
    font-weight: bold;
    padding: 10px;
    font-size: 14px;
    border-radius: 4px;
}
```

### Tooltip Content

```
Open the speaker attribution YAML file to edit channel-speaker mappings.
• Maps YouTube channels to their regular hosts/speakers
• Edit or add custom channel mappings for better speaker recognition
• Changes take effect immediately after saving the file
• Useful for adding your favorite podcasts not in the default list
```

## Use Cases

### Adding a Custom Podcast

Users can easily add their favorite podcast channels that aren't in the default 300+ channel list:

```yaml
channel_mappings:
  "My Favorite Podcast":
    hosts:
      - full_name: "John Smith"
        partial_names: ["John", "Smith"]
        role: "host"
```

### Correcting Speaker Names

If the system incorrectly identifies speakers, users can add or modify mappings:

```yaml
channel_mappings:
  "Tech Talk Daily":
    hosts:
      - full_name: "Jane Doe"
        partial_names: ["Jane", "Doe", "JD"]
        role: "host"
      - full_name: "Bob Johnson"
        partial_names: ["Bob", "Johnson"]
        role: "co-host"
```

## Benefits

1. **Accessibility**: No need to navigate to config folder manually
2. **User-Friendly**: Clear instructions and examples provided
3. **Immediate Feedback**: Changes take effect as soon as file is saved
4. **Empowers Users**: Users can customize speaker recognition for their favorite content
5. **No Code Required**: Simple YAML editing, no Python knowledge needed

## Technical Details

### File Path Resolution

```python
config_dir = Path("config")
if not config_dir.exists():
    config_dir = Path("../config")

speaker_file = config_dir / "speaker_attribution.yaml"
```

### Opening Logic

```python
if sys.platform == "darwin":  # macOS
    subprocess.run(["open", str(speaker_file.absolute())], check=True)
elif sys.platform == "win32":  # Windows
    subprocess.run(["start", str(speaker_file.absolute())], shell=True, check=True)
else:  # Linux
    subprocess.run(["xdg-open", str(speaker_file.absolute())], check=True)
```

## Integration

### Files Modified

1. **src/knowledge_system/gui/tabs/api_keys_tab.py**
   - Added button to UI (line ~472)
   - Added `_open_speaker_attribution_file()` method (line ~1062)

2. **MANIFEST.md**
   - Documented new feature in Recent Additions section

## Future Enhancements

Potential improvements for future versions:

1. **In-App Editor**: Build a custom YAML editor within the GUI
2. **Validation**: Real-time validation of YAML syntax
3. **Templates**: Provide templates for common podcast formats
4. **Auto-Discovery**: Suggest channels based on user's transcription history
5. **Cloud Sync**: Sync custom mappings across devices
6. **Import/Export**: Share custom mappings with other users

## Testing

To test the feature:

1. Launch the application
2. Navigate to the Settings tab
3. Click the "🎤 Edit Speaker Mappings" button
4. Verify the file opens in your default editor
5. Read the informational dialog
6. Make a test edit (add a custom channel)
7. Save the file
8. Process a video from that channel
9. Verify speaker attribution uses your custom mapping

## Related Files

- `config/speaker_attribution.yaml` - The file being edited
- `src/knowledge_system/voice/voice_fingerprinting.py` - Uses the mappings
- `src/knowledge_system/processors/hce/unified_pipeline.py` - Loads speaker mappings
- `docs/SPEAKER_ATTRIBUTION_OPERATIONAL_ORDER_FIX.md` - Related speaker attribution fix

## Conclusion

This feature makes speaker attribution customization accessible to non-technical users, empowering them to improve transcription quality for their favorite content. The simple button interface removes the barrier of navigating file systems and provides helpful guidance for editing the YAML configuration.
