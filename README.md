# Skipthepodcast.com (Skip the Podcast Desktop)

> Transform audio, video, and documents into structured knowledge with AI-powered analysis

**Version 3.4.0** | **macOS Application** | **Offline-First Design**

## What Does This App Do?

Skipthepodcast.com extracts **structured knowledge** from your content:

- **📹 YouTube Videos**: Process individual videos or entire playlists
- **🎙️ Local Audio/Video**: Transcribe MP4, MP3, WAV, and other formats
- **📄 Documents**: Analyze PDFs, Word docs, Markdown, and text files
- **🗣️ Speaker Identification**: Automatically identify who said what with 97% accuracy
- **🧠 Knowledge Extraction**: Extract claims, key people, concepts, and technical terms
- **📊 Smart Organization**: Store everything in a searchable database with automatic categorization

Perfect for researchers, students, professionals, and anyone who needs to process large volumes of content efficiently.

## Why Use Skipthepodcast.com?

Instead of manually listening to hours of podcasts or reading through long documents, Skipthepodcast.com:

✅ **Extracts Key Claims**: Automatically identifies important statements with importance, novelty, and confidence scores  
✅ **Identifies Speakers**: 97% accurate voice fingerprinting tells you who said what  
✅ **Organizes Knowledge**: Builds a searchable database of insights across all your content  
✅ **Finds Connections**: Links related concepts, people, and ideas together  
✅ **Works Offline**: Core features work without internet using local AI models  
✅ **Batch Processing**: Process entire folders automatically  

---

## Getting Started

### Installation

1. **Download**: Get the DMG from the releases page
2. **Install**: Drag to Applications folder
3. **First Launch**: Right-click → Open (macOS may require this the first time)
4. **Setup**: The app walks you through initial configuration

**System Requirements:**
- macOS 10.15 (Catalina) or later
- 8GB RAM minimum (16GB+ recommended)
- 2GB free disk space
- Apple Silicon (M1/M2/M3) or Intel Mac

### Your First Processing Session

**Step 1: Add Content**
- Open the **Transcribe** tab
- Paste a YouTube URL, or drag and drop a local audio/video file
- Check "Process automatically through entire pipeline" to do everything in one go

**Step 2: Let It Process**
- Click "Start Transcription"
- The app will:
  1. Download/load your content
  2. Transcribe the audio
  3. Identify speakers
  4. Extract key claims, people, and concepts
  5. Organize everything into a searchable database

**Step 3: Explore Results**
- **Review Tab**: See all extracted claims with importance scores
- **Speaker Attribution**: Assign names to speakers and correct any mistakes
- **Claim Search**: Search across all your processed content

### The 7 Tabs Explained

1. **Introduction**: Quick tour and getting started guide
2. **Transcribe**: Upload YouTube URLs or local files for processing
3. **Summarize**: Extract knowledge from transcripts or documents
4. **Review**: Browse and edit extracted claims, organized by importance
5. **Upload**: Optional cloud storage backup (future feature)
6. **Monitor**: Watch folders for automatic processing of new files
7. **Settings**: Configure API keys, models, and preferences

### Supported File Types

**Audio/Video**: MP4, MOV, MP3, WAV, M4A, WEBM, and more  
**Documents**: PDF, DOCX, DOC, RTF, TXT, Markdown  
**Batch**: Process entire folders at once

## Common Use Cases

### Research & Learning
Process lecture recordings, research papers, and academic content:
- Extract key claims and concepts from hours of content
- Build a searchable knowledge base of insights
- Connect related ideas across multiple sources
- Export to Obsidian or other knowledge management tools

### Content Analysis
Analyze podcasts, interviews, and video content:
- Identify who said what with automatic speaker identification
- Extract important statements with confidence scores
- Organize by topics and categories automatically
- Find connections between different episodes or videos

### Business & Professional
Process meetings, presentations, and training materials:
- Create searchable archives of team knowledge
- Track key insights and decisions from meetings
- Build internal knowledge bases from training content
- Export structured data for reporting and analysis

### Personal Knowledge Management
Organize your learning and reference materials:
- Process educational videos and podcasts
- Build personal knowledge graphs
- Connect concepts across different sources
- Export to your preferred note-taking system

## Configuration

### API Keys & Models

The app can use different AI providers:

- **Local Models** (Recommended): Uses Ollama with Qwen models - works offline, free, private
- **OpenAI**: GPT-4, GPT-3.5 for cloud-based processing
- **Anthropic**: Claude models for cloud-based processing

**Setting Up Local Models:**
1. Install [Ollama](https://ollama.ai) if you haven't already
2. Download a Qwen model: `ollama pull qwen2.5:7b-instruct`
3. The app automatically detects available models
4. Models are selected based on your Mac's capabilities

**Hardware-Aware Model Selection:**
- The app automatically picks the best model for your Mac
- M2/M3 Ultra: Larger, more capable models
- Base M1/M2: Optimized smaller models
- Everything configured automatically - no technical knowledge needed

### Processing Options

**Speaker Diarization:**
- Automatically enabled for audio/video files
- Identifies when different people are speaking
- Can be disabled in settings if you don't need it

**Pipeline Mode:**
- Check "Process automatically through entire pipeline" to:
  1. Transcribe → Extract knowledge → Organize in one go
  2. No manual steps required
  3. Perfect for batch processing

**Output Settings:**
- Choose where transcribed files are saved
- Configure export formats (Markdown, JSON, CSV, etc.)
- Set up Obsidian integration paths

## YouTube Bulk Processing

For processing large numbers of YouTube videos, the app supports cookie-based authentication:

**Setup Steps:**
1. Create a throwaway Google account (never use your main account)
2. Log into YouTube with the throwaway account
3. Export cookies using a browser extension (Netscape format)
4. In the app, enable cookie authentication and upload your cookie file
5. Configure rate limiting (3-5 minute delays recommended)

**Why Use Cookies?**
- More reliable downloads for large batches
- Reduces rate limiting issues
- Designed for processing 100+ videos
- Cookies stay local - never shared with anyone

**Security:**
- Browser extraction disabled to prevent using your main account
- Only manual cookie file upload supported
- Use a throwaway account exclusively for bulk downloads

## Troubleshooting

### Common Issues

**Installation Warnings:**
- macOS may show a security warning on first launch
- Right-click the app → Open to bypass Gatekeeper
- This is normal for apps not distributed through the App Store

**Processing Stuck or Slow:**
- Check that Ollama is running (if using local models)
- Larger files take longer - a 1-hour video may take 10-15 minutes
- Check available disk space - processing creates temporary files

**Speaker Identification Issues:**
- If speakers aren't being identified correctly, manually assign names
- The app learns from your corrections and improves over time
- Enable speaker diarization in settings if it's disabled

**API Errors:**
- Verify your API keys in the Settings tab
- Check that the selected model is available
- For local models, ensure Ollama is running and the model is downloaded

### Getting Help

- Check the `/docs` directory for detailed technical documentation
- Review processing logs in the app for specific error messages
- See `CHANGELOG.md` for version-specific information

---

**Ready to get started?** Download Skipthepodcast.com and begin transforming your content into structured knowledge today.

For developers and technical details, see the `/docs` directory and `CHANGELOG.md`.
