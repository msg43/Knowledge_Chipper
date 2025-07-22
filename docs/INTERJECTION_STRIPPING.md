# Interjection Stripping Feature

## Overview

The YouTube transcript processor now includes an option to strip out common interjections like `[Applause]`, `[Laughter]`, `[Music]`, etc. from transcripts. This feature helps clean up transcripts by removing non-speech elements that are often included in YouTube captions.

## How to Use

### In the GUI

1. Open the Knowledge System GUI
2. Go to the "YouTube Extraction" tab
3. Check the "Strip interjections" checkbox in the Transcript Settings section
4. Process your YouTube videos as usual

The checkbox will be automatically saved and restored in your session.

### Interjections File

The system uses a text file located at `data/interjections.txt` that contains a list of interjections to strip. Each interjection should be on a separate line.

Default interjections include:
- `[Applause]`
- `[Laughter]`
- `[Music]`
- `[Cheering]`
- `[Crowd noise]`
- `[Background music]`
- `[Sound effects]`
- `[Silence]`
- `[Inaudible]`
- `[Unintelligible]`
- And many more...

### Customizing Interjections

You can customize the list of interjections by editing the `data/interjections.txt` file:

1. Open `data/interjections.txt` in a text editor
2. Add or remove interjections as needed
3. Each interjection should be on its own line
4. Lines starting with `#` are treated as comments and ignored
5. Empty lines are ignored

### Supported Output Formats

The interjection stripping works with all output formats:
- **Markdown (.md)**: Interjections are stripped from both timestamped and plain text versions
- **SRT (.srt)**: Interjections are stripped from subtitle text
- **Plain Text (.txt)**: Interjections are stripped from the full transcript
- **JSON (.json)**: Not affected (preserves original transcript data)

### Technical Details

- Interjections are matched exactly (case-sensitive)
- Multiple spaces created by stripping are cleaned up
- Empty segments after stripping are removed from timestamped output
- The feature uses regex patterns for efficient matching
- Interjections are loaded once per processing session for performance

### Example

**Before stripping:**
```
Hello everyone! [Applause] Welcome to our presentation.
Today we'll be discussing [Music] the future of technology.
[Laughter] That's a great question. Let me explain...
```

**After stripping:**
```
Hello everyone! Welcome to our presentation.
Today we'll be discussing the future of technology.
That's a great question. Let me explain...
``` 