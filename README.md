# Skip the Podcast Desktop App

> **Transform hours of content into structured knowledge in minutes**

Turn YouTube videos, podcasts, audio files, and documents into searchable claims, structured transcripts, and organized knowledge — all processed locally on your Mac with AI.

**Version 4.1.0** | **macOS Application** | **Offline-First + Cloud Sync**

---

## What Is This App?

Skip the Podcast is a macOS desktop application that extracts structured knowledge from your media and documents. Instead of listening to 3-hour podcasts or reading 200-page PDFs, the app:

✅ **Transcribes** audio/video using Whisper AI (offline)
✅ **Extracts** key claims, people, concepts, and terminology
✅ **Scores** each claim on 6 dimensions across 12 user archetypes
✅ **Attributes** speakers only to high-value claims (claims-first approach)
✅ **Organizes** everything in a searchable knowledge database
✅ **Syncs** to GetReceipts.org for web access and sharing

---

## How Does It Work?

### The Desktop App (Local Processing)

**1. Add Your Content**
- Paste YouTube URLs or playlists
- Drag and drop local audio/video files (MP4, MP3, WAV, etc.)
- Import documents (PDF, Word, Markdown, TXT)

**2. Automatic Processing**
Use the **Extract Tab** to process content through the claims-first pipeline:

```
URL Input → Fetch Metadata → Fetch Transcript → Mine Claims → Evaluate → Timestamps → Speakers
    ↓            ↓                 ↓               ↓            ↓           ↓           ↓
 YouTube    YT Metadata      YouTube API     UnifiedMiner   Flagship    Evidence   A/B Claims
 Playlist    + AI Summary    (or Whisper)   (configurable)  Evaluator    Matching     Only
```

*Speaker attribution is applied only to high-value (A/B-tier) claims, using LLM context analysis.*

**Features of the Extract Tab:**
- 📊 **6-stage progress display** with visual indicators
- 🔧 **LLM selection per stage** - choose provider/model for Miner and Evaluator
- ✏️ **Two-pane editor** - edit claims, jargon, people, concepts in-place
- ❌ **Rejected claims visible** - promote good claims back to accepted
- 📈 **Quality assessment** - acceptance rate, transcript quality, suggestions
- 🔄 **Whisper fallback** - re-run with local transcription if quality is low

**3. Review & Upload**
- Claims appear in the **Review Tab** with importance scores (A/B/C tiers)
- Click **"Upload to GetReceipts"** to sync to the web
- Desktop automatically hides uploaded claims (web becomes canonical source)

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

These files are automatically injected into the extraction prompts when you process new content.

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

## Getting Started

### Installation

**Requirements:**
- macOS 10.15 (Catalina) or later
- 8GB RAM minimum (16GB+ recommended for large batches)
- 2GB free disk space
- Apple Silicon (M1/M2/M3) or Intel Mac

**Install:**
1. Download the DMG from [Releases](https://github.com/yourusername/knowledge_chipper/releases)
2. Drag to Applications folder
3. Right-click → Open (first launch only - macOS Gatekeeper)
4. App walks you through initial setup

### First Processing Session

**Step 1: Configure AI Models**

The app can use local AI (offline, free) or cloud AI (requires API key):

- **Local (Recommended)**: Install [Ollama](https://ollama.ai), then run:
  ```bash
  ollama pull qwen2.5:7b-instruct
  ```
  The app auto-detects Ollama models and picks the best one for your Mac.

- **Cloud**: Add API keys in Settings tab (OpenAI GPT-4, Anthropic Claude, Google Gemini, etc.)

**Step 2: Process Your First Video**

1. Open the **Transcribe** tab
2. Paste a YouTube URL: `https://youtube.com/watch?v=...`
3. Check **"Process automatically through entire pipeline"**
4. Click **"Start Transcription"**

The app will:
- Download the video (audio only)
- Transcribe with timestamps
- Extract claims, people, concepts (claims-first mode)
- Score claims by importance (A/B/C tiers)
- Attribute speakers to high-value claims

**Step 3: Review & Upload**

1. Go to the **Review** tab
2. Browse extracted claims sorted by importance
3. Fix any speaker names (app learns from corrections)
4. Click **"Upload to GetReceipts"** when ready
5. Claims disappear from desktop (now live on web)

**Step 4: Access via Web**

1. Go to [GetReceipts.org](https://getreceipts.org)
2. Your claims appear automatically (device auto-linked)
3. Edit, search, share, and explore connections

---

## Understanding the 8 Tabs

### 1. **Introduction**
Quick tour and getting started guide

### 2. **Transcribe**
**Purpose:** Upload YouTube URLs or local files for transcription

**Features:**
- Single videos or entire playlists
- Local audio/video files (drag & drop)
- Claims-first mode (default): Extract claims, then attribute speakers to important ones
- Full pipeline mode (one-click transcribe → analyze → upload)

**Best For:** Getting transcripts and extracting structured knowledge

---

### 3. **Prompts**
**Purpose:** Manage analysis templates

**What It Does:**
- Contains prompts for claim extraction, summarization, etc.
- Optimized for different content types (podcasts, lectures, documents)
- Advanced users can customize prompts

**Best For:** Leave default unless you want custom extraction logic

---

### 4. **Summarize**
**Purpose:** Extract knowledge from transcripts or documents

**Two Modes:**

**A. Summarize from Files**
- Add PDFs, Word docs, Markdown files
- Import third-party transcripts
- Process multiple files in batch

**B. Summarize from Database** *(Recommended)*
- Browse all previously transcribed content
- Re-analyze with improved models
- No need to manage intermediate files
- Shows duration, token counts, existing summaries

**Content Type Selection:**

The app adapts its analysis based on your content type:

| Type | When to Use | Special Handling |
|------|-------------|------------------|
| **Transcript (Own)** | Content you transcribed with this app | Uses speaker labels, timestamps, conversational context |
| **Transcript (Third-party)** | External transcripts from other sources | Handles missing metadata gracefully |
| **Document (PDF/eBook)** | Books, reports, long-form articles | Respects chapters, handles citations |
| **Document (White Paper)** | Technical papers, research | Focuses on methodologies, frameworks |

**Smart Chunking:**
- Automatically breaks large content into optimal chunks
- Respects natural boundaries (sentences, speaker changes, sections)
- Smart overlap maintains context between chunks

---

### 5. **Queue**
**Purpose:** Real-time monitoring of all processing jobs

**Features:**
- Live progress tracking (download %, transcription stage, analysis status)
- Multi-stage pipeline view
- Filter by status: In Progress, Completed, Failed
- Performance metrics and throughput rates
- Auto-refreshes every 5 seconds

**View:**
```
Queue Tab Display:
├─ Download Stage
│  ├─ Video 1: 67% (Account 2) [3.2 MB/s]
│  └─ Video 2: Queued (Account 1)
├─ Transcription Stage
│  └─ Video 3: Processing [42:10 / 1:23:45]
├─ Summarization Stage
│  └─ Video 4: Extracting claims...
└─ Completed (24)
```

---

### 6. **Review**
**Purpose:** Browse and edit extracted claims

**Features:**
- Claims organized by importance (A-tier, B-tier, C-tier, D-tier)
- Multi-dimensional scoring across 12 user archetypes
- Edit claim text, fix speaker attribution
- Upload to GetReceipts with one click

**6-Dimension Scoring System:**

Each claim is evaluated on 6 independent dimensions:
1. **Epistemic Value** - Reduces uncertainty about how the world works
2. **Actionability** - Enables better decisions
3. **Novelty** - Surprisingness, challenges assumptions
4. **Verifiability** - Evidence strength and source reliability
5. **Understandability** - Clarity and accessibility
6. **Temporal Stability** - How long will this remain true? (ephemeral → timeless)
7. **Scope** - How broadly applicable? (narrow → universal)

**12 User Archetypes:**

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

**Tier Assignment:**

Final importance = max(all profile scores) — rescues niche-but-valuable insights!

- **A-tier** (≥8.0): Core insights, highly valuable to at least one archetype
- **B-tier** (6.5-7.9): Significant claims with substantial value
- **C-tier** (5.0-6.4): Useful context and background
- **D-tier** (<5.0): Rejected or trivial

**After Upload:**
- Claims marked as "uploaded" in local database
- Hidden from Review tab (web becomes source of truth)
- Re-processing same video creates new version on web

---

### 7. **Monitor**
**Purpose:** Watch folders for automatic processing

**Use Case:** Drop files into a folder, app processes them automatically

**Setup:**
1. Choose folder to monitor
2. Configure processing options
3. Enable auto-processing
4. Drop files → app processes → uploads to GetReceipts

---

### 8. **Settings**
**Purpose:** Configure API keys, models, and preferences

**Key Settings:**

**AI Providers:**
- Local Models (Ollama): Free, offline, private
- OpenAI (GPT-4, GPT-3.5): Cloud-based, API key required
- Anthropic (Claude): Cloud-based, API key required
- Google (Gemini 2.0, 1.5): Cloud-based, API key required

**Hardware-Aware Model Selection:**
- App automatically picks best model for your Mac
- M2/M3 Ultra: Larger, more capable models
- Base M1/M2: Optimized smaller models

**GetReceipts Integration:**
- Enable/disable auto-upload
- View device ID
- Reset device credentials

**Processing Options:**
- Enable speaker diarization (who said what)
- Output file locations
- Obsidian vault integration paths

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
- `claims`: Extracted knowledge claims (HCE pipeline)
- `people`, `concepts`, `jargon`: Knowledge graph entities
- `speaker_fingerprints`: Voice identification data
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

### Hybrid Claim Extraction (HCE)

**What Is HCE?**
The app uses a sophisticated pipeline to extract high-quality claims:

**Pipeline Stages:**

1. **Mining** (Parallel)
   - Breaks transcript into segments
   - Extracts claims from each segment in parallel
   - 3-8x faster than sequential processing

2. **Evaluation** (Flagship Model)
   - Scores each claim with flagship model (best available)
   - Assigns A/B/C tiers based on:
     - Importance (how significant?)
     - Novelty (how new?)
     - Confidence (how well-supported?)
     - Controversy (how disputed?)

3. **Categorization**
   - Assigns domain categories (science, politics, business, etc.)
   - Uses Wikidata taxonomy (506 categories)

4. **Storage**
   - Unified SQLite database
   - Full provenance tracking
   - Version history

**Why This Matters:**
- Higher quality claims than simple LLM extraction
- Importance scores help you focus on what matters
- Tiers make it easy to filter (show only A-tier)

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

# Launch GUI
python src/knowledge_system/gui/main_window_pyqt6.py
```

**Development Commands:**
```bash
make lint          # Run linting (flake8)
make format        # Auto-format (black + isort)
make security-check # Security scan (bandit)
make build         # Build distribution packages
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
- **Frontend:** PyQt6 (macOS native)
- **Transcription:** whisper.cpp (offline)
- **AI Models:** Ollama (local), OpenAI/Anthropic (cloud)
- **Database:** SQLite (local), Supabase (web)
- **Web App:** Next.js 15, React 19, TypeScript
- **Downloads:** yt-dlp (YouTube)

**License:** MIT

**Architecture Decision:** Web-canonical with ephemeral local (November 2025)

---

## Support

- **Documentation:** See `/docs` directory
- **Logs:** Check `logs/` folder for error details
- **Issues:** [GitHub Issues](https://github.com/yourusername/knowledge_chipper/issues)
- **Changelog:** See `CHANGELOG.md` for version history

---

**Ready to transform your content into structured knowledge?**

Download Skip the Podcast and start extracting insights from hours of media in minutes.
