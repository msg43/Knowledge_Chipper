# macOS Permissions Guide for Skip the Podcast Desktop

## Overview

Skip the Podcast Desktop uses the standard macOS security model for file access. The app works perfectly without any special permissions, using secure file dialogs to access files you explicitly choose.

**New**: The app now includes an optional Full Disk Access enhancement (similar to Disk Drill) that can make file access more convenient by eliminating repeated permission dialogs.

## How File Access Works

### The Secure Approach
When you use Skip the Podcast Desktop:
1. **Select Input Files**: Use the "Browse" button to choose media files → macOS automatically grants read permission
2. **Choose Output Directory**: Select where to save transcriptions → macOS automatically grants write permission
3. **No System-Wide Access**: The app only accesses files and folders you explicitly select

This is Apple's recommended approach that:
- Protects your privacy
- Requires no special permissions
- Works immediately after installation
- Follows macOS security best practices

## What Permissions Are Actually Used

### Folder-Specific Permissions (via Info.plist)
The app declares usage descriptions for common folders:
- **Documents Folder**: For saving transcriptions
- **Downloads Folder**: For processing downloaded media
- **Desktop Folder**: For quick access to files
- **External Drives**: For processing media on external storage

These are informational only - the app still requires you to explicitly select files/folders through dialogs.

### Optional Enhancements
- ✨ **Full Disk Access**: Optional - Makes file access more convenient (Disk Drill-style)
- ❌ **Microphone Access**: Not used (no recording features)
- ❌ **Screen Recording**: Not used
- ❌ **Camera Access**: Not used

### Full Disk Access (Optional Enhancement)
**New!** The app now offers a Disk Drill-style FDA request:
- **What it does**: Allows the app to access files without repeated permission dialogs
- **When offered**: On first launch (can be declined)
- **Benefits**: 
  - Process files from any location without dialogs
  - Batch process entire folders
  - Access external drives seamlessly
- **Without it**: App works perfectly using standard file dialogs

## Common Questions

### "Why doesn't the app show up in Privacy & Security settings?"
Because it doesn't request any special permissions! The app uses standard file dialogs, which is the secure way to access files on macOS.

### "How do I grant access to a folder?"
Simply use the "Browse" button in the app to select the folder. macOS automatically grants access when you choose it through the dialog.

### "What if I see 'Permission Denied' errors?"
This usually means:
1. You're trying to access a file that wasn't selected through a dialog
2. The file is locked or in use by another app
3. You don't have user permissions for that file (check Finder > Get Info)

## For Developers

The app's permission system:
- Uses `NSOpenPanel` and `NSSavePanel` (via PyQt) for file selection
- Stores selected paths in app settings for convenience
- Re-requests access if saved paths become inaccessible
- Falls back gracefully if access is denied

## Technical Implementation

### Files Modified
- `scripts/build_macos_app.sh` - Added folder usage descriptions to Info.plist
- `src/knowledge_system/utils/macos_permissions.py` - Simplified permission handler
- `src/knowledge_system/gui/main_window_pyqt6.py` - Basic startup checks
- `requirements.txt` - Removed unnecessary PyObjC dependencies

### Key Changes from Previous Approach
1. Removed Full Disk Access requests (overly broad)
2. Removed Microphone permission (not currently used)
3. Focused on standard file dialog approach
4. Simplified permission checking to basic file access tests

## Benefits

1. **Privacy First**: Only accesses files you explicitly choose
2. **No Setup Required**: Works immediately after installation
3. **Standard Behavior**: Works like other well-designed macOS apps
4. **Future Proof**: Follows Apple's security guidelines

## Installation

Simply drag Skip the Podcast Desktop to your Applications folder and run it. No special permissions or setup required!
