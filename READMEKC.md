# Knowledge Chipper

> **Transform hours of content into structured knowledge in minutes**

Turn YouTube videos, podcasts, audio files, and documents into searchable claims, structured transcripts, and organized knowledge — processed locally on your Mac with AI, controlled from your browser.

**Version 4.1.0** | **Web-First Architecture** | **Local Processing + Cloud Sync**

---

## What Is This?

Knowledge Chipper is a **web-controlled local processing engine** that extracts structured knowledge from your media and documents. Instead of listening to 3-hour podcasts or reading 200-page PDFs:

✅ **Control from Web Browser** - Process content via [GetReceipts.org/contribute](https://getreceipts.org/contribute)
✅ **Process Locally** - Transcription and extraction run on your Mac (offline-capable)
✅ **Extract Knowledge** - Key claims, people, concepts, and terminology automatically identified
✅ **Score Claims** - 6-dimension scoring across 12 user archetypes
✅ **Speaker Attribution** - Speakers attributed to high-value claims (claims-first approach)
✅ **Sync to Web** - Everything syncs to GetReceipts.org for sharing and collaboration

---

## Architecture: Web UI + Local Daemon

**No Desktop UI** - Everything is controlled through your web browser at [GetReceipts.org](https://getreceipts.org).

### How It Works

```
You (Browser)  →  GetReceipts.org/contribute  →  Local Daemon (Background)
                          ↓                              ↓
                   Submit URLs/Files              Process Locally
                   Configure Options              (Whisper + LLM)
                   Monitor Progress                     ↓
                          ↑                        Auto-Upload
                          └──────────────────────────────┘
```

### The Web Interface (User Control)

Visit **[GetReceipts.org/contribute](https://getreceipts.org/contribute)** to:

1. **Submit Content**
   - Paste YouTube URLs or playlists
   - Upload local audio/video files (MP4, MP3, WAV, etc.)
   - Import documents (PDF, Word, Markdown, TXT)
   - Import podcaster-provided PDF transcripts

2. **Configure Processing**
   - Select Whisper model (base/medium/large)
   - Choose LLM provider (Ollama, OpenAI, Anthropic, Google)
   - Enable/disable auto-upload
   - Set output preferences

3. **Monitor Jobs**
   - Real-time progress tracking
   - Filter by status (pending/processing/completed/failed)
   - Retry failed jobs
   - Bulk actions

4. **Folder Monitoring**
   - Watch folders for automatic processing
   - Drop files → auto-process → auto-upload

### The Local Daemon (Processing Engine)

Runs silently in the background on your Mac:

- **No UI Required** - Controlled entirely via web browser
- **Local AI Processing** - Whisper transcription, LLM extraction (offline-capable)
- **RESTful API** - HTTP API for web integration (port 8765)
- **Auto-Start** - Launches on login (macOS LaunchAgent)
- **Auto-Update** - Checks for updates every 24 hours and on startup, installs automatically
- **Resource Management** - Optimized for M1/M2/M3 Macs

**Installation:**
```bash
# Download daemon installer from releases
# Double-click DMG → installs daemon + sets up auto-launch
```

**Auto-Updates:**
The daemon automatically keeps itself up-to-date by checking GitHub releases every 24 hours. When a new version is available, it downloads and installs the update automatically with zero downtime (LaunchAgent restarts it seamlessly). No manual updates required!

---

## How Knowledge Extraction Works

**1. Submit Content** (via web interface)
- YouTube URLs or playlists
- Local audio/video files (MP4, MP3, WAV, etc.)
- Documents (PDF, Word, Markdown, TXT)
- Podcaster-provided PDF transcripts

**2. Automatic Processing** (local daemon)
Two-pass extraction pipeline:

```
URL Input → Fetch Metadata → Fetch Transcript → Extract & Score → Synthesize Summary
    ↓            ↓                 ↓                    ↓                  ↓
 YouTube    YT Metadata      YouTube API         Pass 1: Extract    Pass 2: Synthesize
 Playlist    + AI Summary    (or Whisper)      (whole document)   (long summary)
```

*Speaker attribution is inferred during extraction using LLM context analysis.*

**Processing Features:**
- 📊 **Two-pass pipeline** - Extract all entities in one pass, then synthesize summary
- 🔧 **Configurable models** - Choose provider/model for extraction and synthesis
- ✏️ **Quality assessment** - Transcript quality, improvement suggestions
- 🔄 **Automatic fallback** - Re-run with Whisper if transcript quality is low
- ⚡ **Batch processing** - Handle multiple items simultaneously
- 📈 **Progress tracking** - Real-time status updates in web interface

**3. Auto-Upload to GetReceipts**
- Processed claims automatically sync to [GetReceipts.org](https://getreceipts.org)
- Local database acts as processing cache (web is canonical source)
- Review and edit claims on the web
- Share knowledge with the community

### The Web App (GetReceipts.org)

Once uploaded, your knowledge lives at **[GetReceipts.org](https://getreceipts.org)** where you can:

🌐 **Browse** all your claims in an interactive graph
✏️ **Edit** claims, fix speaker names, merge duplicates
🔍 **Search** across all your processed content
📊 **Visualize** connections between claims, people, and concepts
🔗 **Share** individual claims or entire episodes with others
🎯 **Refine** entity extraction by rejecting incorrect extractions

---

## Improving Extraction Quality (Entity Refinement)

The AI sometimes makes mistakes when extracting entities. For example, it might extract "US President" as a person instead of "Donald Trump", or mark common words as specialized jargon.

**The Solution**: Review and reject incorrect entities on the web, and the system learns to avoid similar mistakes.

### How It Works

```
1. Process Content (Desktop)     2. Review on Web              3. Desktop Auto-Improves
        ↓                              ↓                              ↓
   AI extracts entities         See "US President" in         Refinements injected
   (people, jargon, etc.)       people list → reject it       into extraction prompts
        ↓                              ↓                              ↓
   Upload to GetReceipts        AI synthesizes pattern:       Future extractions skip
                                "titles aren't people"        "US President", "CEO", etc.
```

### Step-by-Step

1. **Review Entities**: Go to `getreceipts.org/dashboard/entities`
2. **Find Mistakes**: Browse through People, Jargon, or Concepts tabs
3. **Reject with Reason**: Click an incorrect entity, select a category:
   - `title_not_name` → "US President", "CEO"
   - `role_not_name` → "US Marine", "the professor"  
   - `too_generic` → "investors", "people"
   - `not_jargon` → common words marked as jargon
4. **Synthesize Patterns**: Click "Synthesize Patterns" to have AI analyze your rejections
5. **Approve Suggestions**: Review AI-generated prompt improvements at `/dashboard/patterns`
6. **Automatic Sync**: Approved refinements automatically sync to all desktop apps

### Where Refinements Are Stored

On your Mac, synced refinements are stored in:
```
~/Library/Application Support/Knowledge Chipper/refinements/
├── person_refinements.txt      # Bad examples for people extraction
├── jargon_refinements.txt      # Bad examples for jargon extraction
├── concept_refinements.txt     # Bad examples for concept extraction
└── sync_metadata.json          # Sync timestamp and statistics
```

### How Refinements Are Applied

**Automatic Injection** (January 2026):
When you process new content, the two-pass extraction system automatically:
1. **Syncs on startup** - Downloads latest refinements from GetReceipts.org
2. **Injects into prompts** - Adds `<bad_example>` patterns before LLM call
3. **LLM learns** - The AI sees your corrections and avoids those mistakes
4. **Logs activity** - Shows "✅ Injected N refinement type(s)" in logs

**Example Injected Content:**
```
# 🔄 LEARNED PATTERNS - AVOID THESE MISTAKES

## Patterns to Avoid (From Previous Web Corrections)

### ❌ People Extraction Mistakes:

<bad_example>
  <input>"The US President announced policy changes..."</input>
  <explanation>DON'T extract titles like "US President", "CEO" 
    as people. Extract actual names only.</explanation>
</bad_example>

# EXTRACTION INSTRUCTIONS
[... rest of prompt ...]
```

This closes the learning loop - your web corrections automatically improve all future extractions!

### Dynamic Learning System (January 2026)

The Entity Refinement system has been upgraded to a **Dynamic Learning System** that learns from your feedback in real-time using vector embeddings.

**Architecture: "Sandwich" Validation**

```
Pass 1: Extraction (with dynamic few-shot injection)
    ↓
Pass 1.5a: Taste Filter (vector similarity - catches style errors)
    ↓
Pass 1.5b: Truth Critic (LLM - catches logic errors)
    ↓
Pass 2: Synthesis
```

**Key Components:**

1. **Taste Engine (ChromaDB)** - Stores all Accept/Reject feedback as vector embeddings
   - Location: `~/Library/Application Support/KnowledgeChipper/taste_engine/`
   - Automatic backup on every daemon startup (keeps 5 copies)
   
2. **Taste Filter** - Fast vector similarity check (~50ms/entity)
   - >95% similar to past rejection → Auto-discard
   - 80-95% similar → Flag for review
   - >95% similar to past acceptance → +2.0 importance boost (Positive Echo)

3. **Truth Critic** - LLM logic validation for novel entities
   - Catches misclassifications: "Washington University" as Person
   - Only reviews high-importance entities (≥7.0) for efficiency
   - Uses entity-local context (not transcript beginning)

4. **Dynamic Prompt Injection** - Injects relevant past feedback into extraction prompts
   - Uses signal hierarchy: Tags > Summaries > Title (excludes Description)
   - Shows human-readable rejection reasons to the LLM

**Configurable Feedback Reasons:**

Feedback reasons are soft-coded in `feedback_reasons.yaml`. Adding a new reason automatically propagates to:
- Web UI buttons (via `/config/feedback-reasons` API)
- Prompt injection labels
- TasteEngine validation

**API Endpoints:**
- `GET /api/feedback/stats` - TasteEngine statistics
- `POST /api/feedback/sync` - Trigger feedback sync from web
- `GET /api/config/feedback-reasons` - Get all reason categories for Web UI

---

## How Claims Are Scored

### Multi-Profile Scoring System

The app uses a sophisticated **6-dimension, 12-archetype** scoring system to determine claim importance:

**Step 1: LLM Evaluates 6 Dimensions (once per claim)**
```
Claim: "Dopamine regulates motivation, not pleasure"
    ↓
LLM scores 6 dimensions:
- Epistemic Value: 9 (resolves major misconception)
- Actionability: 6 (some practical implications)
- Novelty: 8 (challenges popular belief)
- Verifiability: 8 (well-supported by research)
- Understandability: 7 (clear but some jargon)
- Temporal Stability: 9 (lasting neuroscience principle)
- Scope: 7 (applies broadly to human behavior)
```

**Step 2: Calculate Importance for 12 User Archetypes (pure arithmetic, FREE)**
```
Scientist:     (9×0.45) + (8×0.28) + (8×0.13) + ... = 8.4
Investor:      (6×0.48) + (8×0.23) + (9×0.13) + ... = 7.1
Philosopher:   (9×0.37) + (8×0.27) + (8×0.18) + ... = 8.2
Educator:      (7×0.37) + (9×0.27) + (6×0.15) + ... = 7.8
... (8 more profiles)
```

**Step 3: Max-Scoring Aggregation**
```
Final Importance = max(8.4, 7.1, 8.2, 7.8, ...) = 8.4
Best Profile = "Scientist"
Tier = A (because 8.4 ≥ 8.0)
```

**Key Benefit:** This rescues niche-but-valuable insights! A technical neuroscience claim might score low for investors (7.1) but high for scientists (8.4), so it gets promoted to A-tier.

**Cost Efficiency:** Adding 100 user profiles costs the same as 1 profile — just one LLM call. Profile scoring is pure arithmetic (<1ms).

---

## Why This Architecture?

### Web-Canonical Design (Inspired by Happy)

The app follows a **web-canonical** architecture where:

- **Desktop = Smart Processor**: Fast local extraction, then upload and forget
- **Web = Source of Truth**: Long-term storage, editing, curation, and sharing
- **No Sync Conflicts**: One-way flow from desktop → web (no two-way sync)
- **Zero Sign-In**: Desktop auto-generates device credentials on first launch

**Benefits:**
- ✅ No confusing "which version is newer?" situations
- ✅ Edit anywhere via web browser (phone, tablet, laptop)
- ✅ Share links to claims without desktop app
- ✅ Automatic device authentication (Happy-style)

**How Device Auth Works:**
```
First Launch:
  ↓
Desktop generates unique device ID + key
  ↓
Stored securely in macOS Keychain
  ↓
First upload auto-registers device with GetReceipts
  ↓
All future uploads authenticated automatically
  ↓
No OAuth, no passwords, no browser popups!
```

---

## New Features (December 2025)

### PDF Transcript Import

Import high-quality transcripts provided by podcasters with automatic YouTube video matching:

**Features:**
- 📄 **Import PDF transcripts** with speaker labels and timestamps preserved
- 🔍 **Automatic YouTube matching** using 4 strategies (database fuzzy, title search, metadata search, LLM query)
- 📊 **Quality scoring** based on speaker attribution, timestamps, and formatting
- 🎯 **Confidence-based matching** with manual review for low-confidence matches
- 📁 **Batch import** for folders of PDFs or CSV mapping files
- 🔄 **Multi-transcript coexistence** - PDF, YouTube, and Whisper transcripts can all exist per episode
- ⚙️ **Configurable priority** - Choose which transcript type to prefer for processing

**Why This Matters:**
- Podcaster-provided transcripts have **explicit speaker labels** (no diarization needed)
- Professional formatting and **higher accuracy** than auto-generated transcripts
- Works seamlessly with the **two-pass workflow** (no special handling required)

**Access:** New "Import Transcripts" tab in the GUI

### YouTube Data API Integration

Official YouTube API for reliable metadata extraction:

**Features:**
- 🎯 **Official API** for metadata (guaranteed JSON structure, no parsing errors)
- ⚡ **Batch optimization** - Fetch 50 videos in 1 API call (50x more efficient)
- 📊 **Quota tracking** - 10,000 free lookups per day
- 🔄 **Automatic fallback** to yt-dlp if API unavailable or quota exceeded
- ✅ **Validation layer** - Handles both API and yt-dlp formats
- 🎵 **Audio separation** - yt-dlp used only for downloads, API for metadata

**Benefits:**
- **Faster** - API is quicker than web scraping
- **More reliable** - Won't break when YouTube updates their site
- **Cleaner code** - No validation/cleanup needed for API responses
- **Better separation** - Metadata and audio are independent operations

**Configuration:**
```yaml
youtube_api:
  enabled: true
  api_key: "YOUR_API_KEY"  # Free from Google Cloud Console
```

---

## Getting Started

### Installation

**Requirements:**
- macOS 10.15 (Catalina) or later
- 8GB RAM minimum (16GB+ recommended for large batches)
- 2GB free disk space
- Apple Silicon (M1/M2/M3) or Intel Mac

**Install:**
1. Download the daemon installer DMG from [Releases](https://github.com/yourusername/knowledge_chipper/releases)
2. Double-click to mount, run installer
3. Daemon automatically installs and starts
4. Visit [GetReceipts.org/contribute](https://getreceipts.org/contribute) to begin

**First-Time Setup:**
- Daemon runs in background (no UI window)
- Web interface auto-detects local daemon
- One-time device linking via browser

### First Processing Session

**Step 1: Configure AI Models**

The daemon can use local AI (offline, free) or cloud AI (requires API key):

- **Local (Recommended)**: Install [Ollama](https://ollama.ai), then run:
  ```bash
  ollama pull qwen2.5:7b-instruct
  ```
  Daemon auto-detects Ollama models and picks the best one for your Mac.

- **Cloud**: Add API keys at [GetReceipts.org/contribute/settings](https://getreceipts.org/contribute/settings)

**Step 2: Process Your First Video**

1. Visit **[GetReceipts.org/contribute](https://getreceipts.org/contribute)**
2. Paste a YouTube URL: `https://youtube.com/watch?v=...`
3. Select processing options (Whisper model, LLM provider)
4. Click **"Start Processing"**

The daemon will:
- Download the video (audio only)
- Transcribe with timestamps
- Extract claims, people, concepts (two-pass whole-document extraction)
- Score claims by importance (A/B/C tiers)
- Infer speakers from context
- Auto-upload to GetReceipts

**Step 3: Monitor Progress**

1. Stay on the contribute page or visit **[GetReceipts.org/contribute/jobs](https://getreceipts.org/contribute/jobs)**
2. Watch real-time progress updates
3. See completion notifications
4. Retry failed jobs if needed

**Step 4: Access Your Knowledge**

1. Go to [GetReceipts.org/dashboard](https://getreceipts.org/dashboard)
2. Browse extracted claims, people, concepts
3. Edit, search, share, and explore connections
4. Review quality and flag corrections

---

## Web Interface Features

All interaction happens through your browser at **[GetReceipts.org/contribute](https://getreceipts.org/contribute)**.

### 1. **Main Processing Page** (`/contribute`)
- **Smart Input** - Auto-detects YouTube URLs, local files, or text content
- **Processing Options** - Configure Whisper model, LLM provider, pipeline settings
- **Batch Support** - Submit multiple URLs or files at once
- **Real-time Status** - See daemon connection and processing status

### 2. **Jobs Queue** (`/contribute/jobs`)
- **Live Progress** - Real-time updates from local daemon
- **Multi-stage Pipeline** - Track download → transcribe → extract → evaluate
- **Filters** - Status (pending/processing/completed/failed), date range
- **Bulk Actions** - Retry failed jobs, delete completed jobs
- **Performance Metrics** - Throughput rates, time estimates

### 3. **Settings** (`/contribute/settings`)
- **API Keys** - OpenAI, Anthropic, Google Gemini (optional - use Ollama locally)
- **Model Defaults** - Set preferred Whisper model and LLM provider
- **Device Linking** - One-time browser-based device authentication
- **Processing Defaults** - Auto-upload toggle, output preferences

### 4. **Folder Monitor** (`/contribute/monitor`)
- **Automatic Processing** - Watch local folders for new content
- **Configuration** - Choose folders, set processing options
- **Event Log** - See what files were detected and processed
- **Start/Stop Control** - Enable/disable monitoring remotely

### 5. **Help & Documentation** (`/contribute/help`)
- **Getting Started** - Step-by-step setup guide
- **Troubleshooting** - Common issues and solutions
- **API Reference** - For advanced integrations

---

## Knowledge Extraction System

### 6-Dimension Scoring System

Each claim is evaluated on 6 independent dimensions:
1. **Epistemic Value** - Reduces uncertainty about how the world works
2. **Actionability** - Enables better decisions
3. **Novelty** - Surprisingness, challenges assumptions
4. **Verifiability** - Evidence strength and source reliability
5. **Understandability** - Clarity and accessibility
6. **Temporal Stability** - How long will this remain true? (ephemeral → timeless)
7. **Scope** - How broadly applicable? (narrow → universal)

### 12 User Archetypes

The system calculates importance for each user type:
- **Scientist** - Values deep understanding and evidence
- **Investor** - Values actionable market intelligence
- **Philosopher** - Values conceptual clarity and novelty
- **Educator** - Values clear explanations and broad applicability
- **Student** - Values accessible insights and surprising facts
- **Skeptic** - Values evidence quality above all
- **Policy Maker** - Values broad impact and systemic thinking
- **Tech Professional** - Values practical implementation
- **Health Professional** - Values clinical evidence and safety
- **Journalist** - Values newsworthy insights and clarity
- **Generalist** - Values interesting, accessible knowledge
- **Pragmatist** - Values immediate utility

### Tier Assignment

Final importance = max(all profile scores) — rescues niche-but-valuable insights!

- **A-tier** (≥8.0): Core insights, highly valuable to at least one archetype
- **B-tier** (6.5-7.9): Significant claims with substantial value
- **C-tier** (5.0-6.4): Useful context and background
- **D-tier** (<5.0): Rejected or trivial

---

## GetReceipts Integration Deep Dive

### How Upload Works

When you click "Upload to GetReceipts" in the Review tab:

**1. Desktop Prepares Data**
```python
session_data = {
    "episodes": [...],      # Video/audio metadata
    "claims": [...],        # Extracted claims with scores
    "people": [...],        # Mentioned individuals
    "jargon": [...],        # Technical terms + definitions
    "concepts": [...],      # Mental models, frameworks
    "evidence": [...],      # Timestamps, quotes, sources
    "relations": [...]      # Claim-to-claim relationships
}
```

**2. Device Authentication** (Automatic)
```
Desktop sends:
  Headers:
    X-Device-ID: "abc123..."
    X-Device-Key: "secret..."

Backend checks:
  ├─ Device exists? → Authenticate
  └─ New device? → Register and authenticate
```

**3. Backend Processing**
```
GetReceipts API:
  ├─ Creates/updates episode records
  ├─ Stores claims with full metadata
  ├─ Links people, jargon, concepts to claims
  ├─ Builds relationship graph
  └─ Indexes for search and visualization
```

**4. Desktop Hides Claims**
```sql
-- Local database marks claims as uploaded
UPDATE claims SET hidden = 1, uploaded_at = NOW()
WHERE claim_id IN (uploaded_ids);

-- Review tab filters out hidden claims
SELECT * FROM claims WHERE hidden = 0;
```

### Reprocessing Workflow

**Scenario:** You upgrade your AI model and want better claim extraction from an old video.

**What Happens:**

1. **Desktop Re-Processing**
   - You re-run extraction on the same YouTube video
   - New, improved claims extracted with better model
   - Upload to GetReceipts

2. **Version Detection** (Automatic)
   ```
   Backend sees:
     source_id: "dQw4w9WgXcQ" (same video)
     device_id: "abc123..." (same device)

   Backend creates:
     Version 2 of claims
     Links to Version 1 (replaces_claim_id)
   ```

3. **Web UI Shows**
   ```
   GetReceipts.org displays:

   "You have 2 versions of claims from this video:"

   Version 1 (Nov 1, 2025): 12 claims, Model: Qwen 7B
   Version 2 (Nov 18, 2025): 15 claims, Model: Qwen 14B ← Current

   [Compare Versions] [Merge Best Of Both] [Keep v2 Only]
   ```

### Why This Matters

**Problem This Solves:**
- ❌ **Old Way**: "I edited this claim... wait, which version did I edit? Desktop or web?"
- ✅ **New Way**: "All edits happen on web. Desktop just uploads and forgets."

**Benefits:**
- No sync conflicts (one-way flow)
- Web is always the source of truth
- Desktop remains fast extraction tool
- Share links work forever (web-hosted)

---

## Processing Different Content Types

### YouTube Videos & Playlists

**Single Video:**
1. Transcribe tab → Paste URL
2. Check "Process automatically"
3. Results appear in Review tab

**Playlist (100+ videos):**
1. Settings → Enable cookie authentication
2. Export cookies from throwaway Google account (Netscape format)
3. Upload cookie file in Settings
4. Paste playlist URL
5. App processes all videos in parallel

**Bulk Processing Security:**
- Never use your main Google account
- Create throwaway account for bulk downloads
- Cookies stay local, never shared
- Browser cookie extraction disabled for safety

---

### Local Audio/Video Files

**Supported Formats:**
- Audio: MP3, WAV, M4A, FLAC, OGG
- Video: MP4, MOV, AVI, WEBM, MKV

**Batch Processing:**
1. Monitor tab → Choose folder
2. Drop files into folder
3. App processes automatically
4. Results upload to GetReceipts

---

### Documents (PDFs, Word, Markdown)

**Best for:**
- Research papers
- Books and ebooks
- Technical documentation
- Blog posts and articles

**Workflow:**
1. Summarize tab → "Summarize from Files"
2. Add PDFs/documents
3. Select content type (PDF/eBook or White Paper)
4. App extracts:
   - Key claims and arguments
   - Citations and references
   - Technical terminology
   - Conceptual frameworks

**Smart Chunking:**
- Respects chapter/section boundaries
- Maintains context across chunks
- Handles academic citations
- Preserves document structure

---

### Re-Analyzing Transcribed Content

**Scenario:** You transcribed 50 videos months ago. Now you have a better AI model.

**Workflow:**
1. Summarize tab → "Summarize from Database"
2. Browse your 50 transcribed videos
3. Select videos to re-analyze
4. Choose new, better model
5. Click "Analyze"
6. New version uploads to GetReceipts

**No Files Needed:**
- Database-centric approach
- Transcripts stored in local SQLite
- No need to regenerate markdown files
- Faster than file-based workflow

---

### YouTube AI Summary Integration

**New Feature:** Automatically scrape and save YouTube's AI-generated summaries alongside Knowledge_Chipper's local LLM summaries.

**What It Does:**
- Scrapes YouTube's AI summary during video download
- Saves to database for comparison with local LLM summaries
- Includes in markdown output with hyperlinked timestamps
- Works seamlessly with existing pipeline

**Requirements:**
- Playwright (auto-installed on first use)
- YouTube account (logged in to Chrome, Safari, or Firefox)
- YouTube Premium recommended (AI summaries may be limited without it)

**Database Storage:**
Each YouTube video can have **four distinct fields**:
- `description` - YouTube's video description (show notes, chapters)
- `youtube_ai_summary` - YouTube's AI-generated summary (scraped)
- `short_summary` - Knowledge_Chipper short summary (local LLM)
- `long_summary` - Knowledge_Chipper long summary (local LLM)

This allows quality comparison and testing between YouTube AI and Knowledge_Chipper summaries.

**Markdown Output:**
Generated markdown files include:
- ✅ Complete metadata (title, uploader, duration, tags, view count)
- ✅ Thumbnail image (auto-downloaded)
- ✅ Description with hyperlinked chapter timestamps
- ✅ YouTube AI Summary section (if available)
- ✅ Full transcript with every timestamp hyperlinked

**Standalone Tools:**
```bash
# Scrape complete video data (metadata + transcript + AI summary)
python scrape_youtube_complete.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Compare YouTube AI vs Knowledge_Chipper summaries
python compare_youtube_summaries.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Performance:**
- YouTube AI summary: ~15-20 seconds
- Knowledge_Chipper summary: ~2-5 minutes (download + transcribe + analyze)
- **10-20x faster** when YouTube AI is available

**Note:** YouTube AI summaries require YouTube Premium in most regions. The system gracefully falls back to local LLM processing if scraping fails.

---

## Common Use Cases

### 📚 Research & Academic

**Use:** Process lecture recordings, research papers, academic podcasts

**Workflow:**
1. Transcribe lectures → Extract claims
2. Import PDFs of research papers
3. Combine insights across sources
4. Export to Obsidian vault
5. Access via GetReceipts graph visualization

**Output:**
- Searchable knowledge base of academic insights
- Transcripts with claims extraction
- Connected concepts across different courses
- Citable claims with timestamps

---

### 🎙️ Podcast Analysis

**Use:** Extract insights from 3-hour podcast episodes

**Workflow:**
1. Paste YouTube URL of podcast
2. App transcribes and extracts claims
3. Scores claims by importance (A/B/C tiers)
4. Attributes speakers to important claims
5. Upload to GetReceipts for sharing

**Output:**
- 5-minute read instead of 3-hour listen
- Important claims with speaker attribution
- Controversy and novelty scores
- Share specific claims via GetReceipts links

---

### 💼 Business & Professional

**Use:** Process meetings, training materials, presentations

**Workflow:**
1. Record Zoom/Teams meeting (audio file)
2. Drop into Monitor folder
3. App transcribes and extracts claims
4. Extracts action items and decisions
5. Upload to GetReceipts for team access

**Output:**
- Searchable meeting archive
- Key claims with importance scores
- Decision tracking over time
- Shareable team knowledge base

---

### 🧠 Personal Knowledge Management

**Use:** Build a personal knowledge graph from all your learning

**Workflow:**
1. Process educational videos, podcasts, books
2. App extracts claims, people, concepts
3. Upload to GetReceipts
4. Explore graph of interconnected ideas

**Output:**
- Visual knowledge graph
- Cross-referenced insights across sources
- Search entire knowledge base
- Export to note-taking system (Obsidian, Notion)

---

## Troubleshooting

### Installation Issues

**"App can't be opened because it is from an unidentified developer"**
- Right-click app → Open
- Click "Open" in security dialog
- This is normal for apps outside Mac App Store

---

### Processing Issues

**"Transcription stuck or very slow"**
- Check Ollama is running: `ollama list`
- Verify model is downloaded: `ollama pull qwen2.5:7b-instruct`
- Check available disk space (processing creates temporary files)
- Large files take time: 1-hour video = 10-15 minutes

**"Speaker attribution not appearing"**
- Ensure Claims-First Mode is enabled in Transcription tab
- Speaker attribution only applies to A/B-tier (high-importance) claims
- Low-importance claims (C-tier) intentionally skip speaker attribution

**"Claims extraction failed"**
- Check AI model is available (local or cloud)
- Verify API key if using cloud models
- Check logs in `/logs` directory for error details

---

### Upload Issues

**"Upload to GetReceipts failed"**
- Check internet connection
- Verify GetReceipts.org is accessible
- Check device credentials in Settings → "View Device ID"
- Try "Reset Device Credentials" if persistent errors

**"Claims not appearing on GetReceipts.org"**
- Wait 30 seconds (processing delay)
- Refresh browser page
- Check if device is linked (Settings tab shows device ID)
- Verify upload succeeded in Queue tab

---

### Model Selection Issues

**"No models available"**
- **Local**: Install Ollama, then `ollama pull qwen2.5:7b-instruct`
- **Cloud**: Add API key in Settings tab
- Restart app after installing new models

**"Model running out of memory"**
- M1/M2 base Macs: Use smaller models (7B instead of 14B)
- Close other apps during processing
- Process fewer videos in parallel
- Reduce batch size in Queue settings

---

## Advanced Topics

### Cookie-Based YouTube Downloads

**When to Use:**
- Processing 100+ YouTube videos
- Avoiding rate limiting
- Downloading age-restricted content

**Setup:**
1. Create throwaway Google account (NOT your main account)
2. Log into YouTube with throwaway account
3. Export cookies using browser extension:
   - Chrome: "Get cookies.txt"
   - Firefox: "cookies.txt"
   - Export in Netscape format
4. Settings → Enable cookie authentication
5. Upload cookie file
6. Configure delays (3-5 minutes recommended)

**Security:**
- Desktop app cannot extract browser cookies (disabled for safety)
- Only manual cookie file upload supported
- Use throwaway account to protect main account
- Cookies stay local, never uploaded to GetReceipts

---

### Speaker Attribution (Claims-First Architecture)

**v4.0.0+ Approach:**
Starting with v4.0.0, the app uses a **claims-first** approach to speaker attribution:

1. **Extract claims first** from undiarized transcripts
2. **Evaluate and score** each claim by importance (A/B/C tiers)
3. **Attribute speakers** only to high-value (A/B-tier) claims using LLM context analysis

**Benefits:**
- **Faster processing**: No diarization overhead for most content
- **Lower cost**: Speaker attribution only where it matters
- **Context-aware**: LLM uses dialogue context for better accuracy

**Legacy Voice Fingerprinting:**
The previous voice fingerprinting system (wav2vec2 + ECAPA-TDNN embeddings) has been deprecated in v4.0.0. 
If you need the legacy speaker-first pipeline, you can restore it from the `speaker-first-archive` Git branch.

---

### Obsidian Integration

**Setup:**
1. Settings → Output Settings
2. Set Obsidian vault path
3. Enable "Auto-export to Obsidian"

**What Gets Exported:**
- Transcripts in Markdown format
- Claims as individual notes
- Maps of Content (MOCs) linking related content
- Speaker-attributed quotes

**Link Format:**
```markdown
---
tags: [claim, youtube, importance-A]
source: https://youtube.com/watch?v=abc123
speaker: John Doe
timestamp: 12:34
---

# Claim: Large language models exhibit emergent capabilities

**Importance:** A (0.89)
**Novelty:** High (0.76)
**Confidence:** Medium (0.68)

Research shows sudden capability jumps at specific model scales...

[[Related Claims]] | [[John Doe]] | [[Emergent Properties]]
```

---

### Database-Centric Architecture

**Why Database-First?**
- ✅ Database is single source of truth
- ✅ Files regenerated from DB on demand
- ✅ Metadata lookups use database (not filename parsing)
- ✅ Faster queries, better organization

**Database Location:**
```
~/Library/Application Support/SkipThePodcast/knowledge_system.db
```

**Key Tables:**
- `media_sources`: Videos, podcasts, documents
- `transcripts`: Transcription data with timestamps
- `claims`: Extracted knowledge claims (two-pass pipeline)
- `people`, `concepts`, `jargon`: Knowledge graph entities
- `summaries`: Analysis results with metrics

**Querying Your Data:**
```bash
# Install SQLite browser or use command line
sqlite3 ~/Library/Application\ Support/SkipThePodcast/knowledge_system.db

# Example: Find all A-tier claims
SELECT canonical, importance_score
FROM claims
WHERE tier = 'A'
ORDER BY importance_score DESC
LIMIT 10;
```

---

### Two-Pass Extraction System

**What Is Two-Pass Extraction?**
The app uses a whole-document extraction approach:

**Pipeline Stages:**

1. **Pass 1: Extraction & Scoring** (Single API Call)
   - Processes entire transcript in one pass
   - Extracts all entities: claims, jargon, people, concepts
   - Scores each claim with 6-dimension system
   - Assigns A/B/C tiers based on importance
   - Infers speakers from context
   - Learns from previous corrections via refinement injection

2. **Pass 2: Synthesis** (Single API Call)
   - Generates world-class long summary
   - Synthesizes high-importance claims (≥7.0)
   - Integrates all entity types thematically
   - Dynamic length based on content complexity

**Why This Matters:**
- Faster than segment-based processing (2 API calls vs dozens)
- Better context understanding (whole document vs fragments)
- Learning system improves over time via web corrections
- Importance scores help you focus on what matters

---

## For Developers

### Running from Source

**Setup:**
```bash
git clone https://github.com/yourusername/knowledge_chipper.git
cd knowledge_chipper

# Install dependencies
make install

# Run tests
make test-quick

# Launch daemon locally
python -m daemon.main
```

**Development Commands:**
```bash
make lint           # Run linting (flake8)
make format         # Auto-format (black + isort)
make security-check # Security scan (bandit)
make build          # Build daemon installer
```

**Daemon API:**
```bash
# Health check
curl http://localhost:8851/health

# Submit processing job
curl -X POST http://localhost:8851/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=..."}'

# Check job status
curl http://localhost:8851/jobs
```

---

### Architecture Documentation

**Key Docs:**
- `ARCHITECTURE_WEB_CANONICAL.md`: Web-canonical architecture explanation
- `docs/DATABASE_CENTRIC_ARCHITECTURE.md`: Database design
- `docs/FILE_ORGANIZATION.md`: Output file structure
- `docs/AUTOMATED_TESTING_GUIDE.md`: Testing strategy
- `CHANGELOG.md`: Version history

**Code Structure:**
```
src/knowledge_system/
├── core/                    # Orchestration & pipeline
│   └── system2_orchestrator.py  # Main job orchestrator
├── processors/              # Content processing
│   ├── hce/                # Hybrid Claim Extraction
│   ├── youtube_download.py # yt-dlp wrapper
│   └── audio_processor.py  # Whisper transcription
├── services/                # Business logic
│   ├── device_auth.py      # Happy-style device auth
│   └── claims_upload_service.py # GetReceipts upload
├── database/                # Database layer
│   └── models.py           # SQLAlchemy ORM
└── gui/                     # PyQt6 interface
    └── tabs/               # 8 main tabs
```

---

### Testing

**Test Suites:**
```bash
make test-quick        # Fast unit tests (~30s)
make test-unit         # All unit tests
make test-integration  # Integration tests (requires Ollama)
make test-gui          # GUI tests (PyQt6)
make smoke-test        # Basic functionality
```

**Single Test:**
```bash
pytest tests/test_basic.py -v
pytest tests/test_basic.py::test_function_name -v
```

---

### Contributing

See `CONTRIBUTING.md` for:
- Code style guidelines
- Testing requirements
- Pre-commit hooks
- Pull request process

---

## Credits & License

**Built with:**
- [Claude Code](https://claude.ai/code) - AI-powered development
- [Happy](https://happy.engineering) - Device authentication inspiration

**Technology Stack:**
- **Web UI:** Next.js 15, React 19, TypeScript (GetReceipts.org)
- **Daemon API:** FastAPI (Python) + REST endpoints
- **Transcription:** whisper.cpp (offline)
- **AI Models:** Ollama (local), OpenAI/Anthropic/Google (cloud)
- **Database:** SQLite (local cache), Supabase PostgreSQL (web canonical)
- **Downloads:** yt-dlp (YouTube)
- **Installer:** DMG with LaunchAgent auto-start

**License:** MIT

**Architecture Decision:** Web-first with local processing (January 2026)

---

## ⚠️ Desktop GUI Deprecated (January 2026)

The PyQt6 desktop GUI has been **deprecated** in favor of the web-first architecture:

- **Old:** Desktop app with tabs and windows
- **New:** Web browser control + background daemon

**Why the change?**
- ✅ Better user experience (familiar web UI)
- ✅ Cross-platform accessibility (any browser)
- ✅ Easier updates (no app reinstalls)
- ✅ Unified interface with GetReceipts.org
- ✅ Mobile-friendly (future)

**GUI Code Location:** Moved to `_deprecated/gui/` for reference

---

## Support

- **Documentation:** See `/docs` directory
- **Logs:** Check `logs/` folder for error details
- **Issues:** [GitHub Issues](https://github.com/yourusername/knowledge_chipper/issues)
- **Changelog:** See `CHANGELOG.md` for version history

---

**Ready to transform your content into structured knowledge?**

1. Install the Knowledge Chipper daemon (one-time setup)
2. Visit [GetReceipts.org/contribute](https://getreceipts.org/contribute)
3. Start extracting insights from hours of media in minutes
