# GetReceipts + Knowledge_Chipper: Unified System

**A comprehensive knowledge management platform combining local AI processing with cloud-based collaboration**

**Last Updated:** January 17, 2026  
**Status:** Two separate repositories, planned for merge  
**Architecture:** Daemon (local) + Web (cloud)

---

## What Is This?

GetReceipts is a **hybrid system** that transforms videos, podcasts, and documents into structured, searchable knowledge:

- **Knowledge_Chipper (Daemon)** - Local macOS daemon that processes content and extracts knowledge
- **GetReceipts.org (Web)** - Cloud platform for storing, exploring, and collaborating on extracted knowledge

**The two codebases work together** as a unified system, but can also function independently.

---

## Quick Start

### 1. Install the Daemon (macOS)

```bash
# Download the latest PKG installer
open https://github.com/msg43/Skipthepodcast.com/releases/latest

# Run the installer
# Daemon auto-starts and creates desktop control app
```

### 2. Visit GetReceipts.org

```
https://getreceipts.org/contribute
```

The web interface will automatically detect your local daemon.

### 3. Process Your First Video

1. Paste a YouTube URL into the web interface
2. Click "Process"
3. Watch real-time progress in the job queue
4. Review extracted claims, people, jargon, and concepts
5. Results automatically upload to your GetReceipts account

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  GetReceipts.org (Web)                   │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │   Process   │  │  Job Queue   │  │   Settings     │ │
│  │   Content   │  │  Monitoring  │  │   & Config     │ │
│  └─────────────┘  └──────────────┘  └────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐│
│  │          Explore & Collaborate                       ││
│  │  • Claims network graph                              ││
│  │  • Debate arenas                                     ││
│  │  • Thinker portraits                                 ││
│  │  • Domain landscapes                                 ││
│  │  • Voting & comments                                 ││
│  └─────────────────────────────────────────────────────┘│
└────────────────┬────────────────────────────────────────┘
                 │
                 │ HTTP REST API (localhost:8765)
                 │
┌────────────────▼────────────────────────────────────────┐
│         Knowledge_Chipper Daemon (macOS)                 │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Download   │→ │  Transcribe  │→ │   Extract    │  │
│  │   (yt-dlp)   │  │  (whisper)   │  │   (LLM)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐│
│  │          Two-Pass AI Pipeline                        ││
│  │  Pass 1: Extract claims, jargon, people, concepts   ││
│  │  Pass 1.5a: Taste Filter (style validation)         ││
│  │  Pass 1.5b: Truth Critic (logic validation)         ││
│  │  Pass 1.5c: Evolution Detector (RAE deduplication)  ││
│  │  Pass 2: Synthesize long-form summary               ││
│  └─────────────────────────────────────────────────────┘│
│                                                           │
│  ┌──────────────┐                                        │
│  │   Upload to  │                                        │
│  │  GetReceipts │                                        │
│  └──────────────┘                                        │
└───────────────────────────────────────────────────────────┘
                 │
                 │ HTTPS Upload
                 │
┌────────────────▼────────────────────────────────────────┐
│              Supabase (Cloud Database)                   │
│                                                           │
│  • Canonical knowledge storage                           │
│  • Deduplication & entity merging                        │
│  • User accounts & authentication                        │
│  • Collaboration features                                │
└───────────────────────────────────────────────────────────┘
```

### Responsibilities

#### Knowledge_Chipper Daemon (Local)
- **Video/Audio Processing**: Download, transcribe, extract metadata
- **AI Extraction**: Claims, jargon, people, mental models using two-pass pipeline
- **Quality Control**: Taste Filter, Truth Critic, Evolution Detector
- **Local Storage**: SQLite database for processing state
- **Auto-Upload**: Seamless upload to GetReceipts.org

#### GetReceipts.org (Web)
- **User Interface**: All user interaction happens here
- **Job Management**: Submit jobs, monitor progress, view results
- **Configuration**: API keys, model selection, daemon settings
- **Canonical Storage**: Supabase PostgreSQL with deduplication
- **Collaboration**: Voting, comments, annotations, merge proposals
- **Visualization**: Interactive graphs, debate arenas, domain landscapes
- **Knowledge Exploration**: 10 paradigms for exploring claims

#### Supabase (Cloud Database)
- **Single Source of Truth**: Canonical knowledge storage
- **Deduplication**: Hash-based episode dedup, fuzzy entity matching
- **User Management**: Authentication, roles, permissions
- **Real-Time**: Live updates, notifications
- **Vector Search**: pgvector for semantic similarity

---

## Features

### What Runs Where

| Feature | Local Daemon | Web Interface | Cloud Database |
|---------|--------------|---------------|----------------|
| **Video Download** | ✅ yt-dlp | - | - |
| **Transcription** | ✅ whisper.cpp | - | - |
| **AI Extraction** | ✅ Two-pass pipeline | - | - |
| **Job Submission** | - | ✅ REST API | - |
| **Job Monitoring** | - | ✅ Real-time UI | - |
| **Settings Management** | - | ✅ Web forms | ✅ Stored |
| **Results Viewing** | - | ✅ Interactive UI | ✅ Queried |
| **Knowledge Storage** | ⚠️ Ephemeral | - | ✅ Canonical |
| **Deduplication** | - | - | ✅ Automatic |
| **Collaboration** | - | ✅ Full features | ✅ Stored |
| **Visualization** | - | ✅ D3.js graphs | ✅ Data source |

### Processing Features (Daemon)

**Content Types Supported:**
- YouTube videos
- Local audio files (MP3, WAV, M4A, etc.)
- Local video files (MP4, MOV, etc.)
- PDF documents
- DOCX documents
- RSS/podcast feeds

**AI Extraction:**
- **Claims** - Factual assertions with evidence and speaker attribution
- **People** - Mentioned individuals with roles and context
- **Jargon** - Domain terminology with definitions
- **Mental Models** - Concepts and frameworks with explanations
- **Questions** - Implicit and explicit questions raised

**Quality Control:**
- **6-Dimension Scoring** - Importance, novelty, specificity, verifiability, impact, clarity
- **Taste Filter** - Vector similarity to accepted/rejected examples
- **Truth Critic** - LLM validation of high-importance entities
- **Evolution Detector** - RAE-based duplicate/contradiction detection

**Advanced Features:**
- Multi-account YouTube downloads (parallel, session-based anti-bot)
- YouTube AI summary scraping (compare with local LLM)
- Speaker attribution from content (no diarization needed)
- Batch processing with smart resume
- Folder monitoring for automation
- Auto-update system

### Web Features (GetReceipts.org)

**Knowledge Management:**
- Universal entity codes (E/Q/C/P/J/M prefixes)
- Hash-based episode deduplication
- Fuzzy entity matching (95% threshold)
- Provenance tracking (which devices extracted what)
- Merge proposals for duplicate resolution

**Interactive Visualizations:**
- Claims network graph (D3.js)
- Debate arenas (polar layout)
- Thinker portraits (radial tree)
- Domain landscapes (force-directed)
- Question web topology
- People network

**Community Engagement:**
- Multi-dimensional voting (upvote/downvote + credible/disputed)
- Threaded comments with nested replies
- User reputation and trust levels
- Universal annotations (public/private notes)
- Edit proposals with community voting

**Knowledge Exploration (10 Paradigms):**
1. Debate Arena - Questions with opposing sides
2. Intellectual Portrait - Thinker's complete footprint
3. Constellation Mapper - Curated claim groups
4. Contradiction Detector - Intellectual tensions
5. Consensus Finder - Where thinkers converge
6. Concept Genealogy - Ideas across claims
7. Domain Landscape - Bird's-eye field view
8. Evidence Trail - Supporting evidence drill-down
9. Question Web - Question topology
10. People Network - Intellectual relationships

**Advanced Analytics:**
- Consensus Meter (red → yellow → green)
- Evidence strength scoring
- Engagement metrics
- Faction analysis

---

## Installation

### Daemon (macOS)

**Requirements:**
- macOS 11.0 or later
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

**Installation:**

1. Download PKG installer from [GitHub Releases](https://github.com/msg43/Skipthepodcast.com/releases/latest)
2. Run the installer
3. Desktop control app created: `~/Desktop/GetReceipts Daemon.app`
4. Daemon auto-starts on login via LaunchAgent

**Manual Control:**

```bash
# Start daemon
launchctl start org.getreceipts.daemon

# Stop daemon
launchctl stop org.getreceipts.daemon

# Check status
curl http://localhost:8765/health
```

**Or use the desktop app** - Double-click for GUI dialogs to start/stop/restart.

### Web Interface (No Installation)

Simply visit: https://getreceipts.org

**Sign up with:**
- Google OAuth
- GitHub OAuth
- Email/password

**Link your daemon:**
1. Daemon generates claim code (e.g., "ABCD-12")
2. Visit GetReceipts.org/claim
3. Enter code and sign in
4. All uploads now attributed to your account

---

## Configuration

### API Keys (Required)

Configure via GetReceipts.org/contribute/settings:

**LLM Providers (at least one required):**
- OpenAI (GPT-4, GPT-4o)
- Anthropic (Claude Sonnet 4.5, Opus 4.5)
- Google (Gemini 2.0 Flash, Gemini 2.5 Pro)

**Optional:**
- YouTube Data API (for metadata fetching)
- HuggingFace (for model downloads)

### Processing Defaults

**Whisper Model:**
- Base (fastest, least accurate)
- Medium (default, good balance)
- Large-v3 (slowest, most accurate)

**LLM Provider:**
- Anthropic (default, Claude Sonnet 4.5)
- OpenAI (GPT-4o)
- Google (Gemini 2.0 Flash)

**Auto-Upload:**
- Enabled by default
- Uploads to GetReceipts.org after extraction
- Requires device linking

---

## Development

### Repository Structure

```
Knowledge_Chipper/          GetReceipts/
├── daemon/                 ├── src/
│   ├── api/               │   ├── app/
│   ├── config/            │   │   ├── api/
│   ├── models/            │   │   ├── contribute/
│   └── services/          │   │   ├── explore/
├── installer/             │   │   └── dashboard/
├── src/knowledge_system/  │   ├── components/
│   ├── core/              │   ├── lib/
│   ├── processors/        │   └── hooks/
│   ├── services/          ├── database/migrations/
│   ├── database/          ├── tests/
│   └── utils/             └── public/
├── tests/
└── scripts/
```

### Tech Stack

#### Knowledge_Chipper (Python)
- **Framework:** FastAPI (daemon), SQLAlchemy (ORM)
- **Transcription:** whisper.cpp (pywhispercpp binding)
- **Downloads:** yt-dlp (requires Deno runtime)
- **LLMs:** OpenAI, Anthropic, Google Gemini APIs
- **Storage:** SQLite (local), ChromaDB (Dynamic Learning)
- **Testing:** pytest, pytest-asyncio
- **Build:** PyInstaller, Packages.app (PKG creation)

#### GetReceipts (TypeScript)
- **Framework:** Next.js 15.5 + React 19
- **UI:** shadcn/ui + Radix UI + Tailwind CSS v4
- **Visualization:** D3.js, Sigma.js, Three.js
- **Database:** Supabase PostgreSQL + pgvector
- **Backend:** Supabase (Auth/Storage/RLS) + Next.js API Routes
- **Testing:** Vitest + Testing Library
- **Deployment:** Vercel

### Development Setup

#### Knowledge_Chipper

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Install dependencies
make install

# Run tests
make test-quick

# Start daemon (development)
cd daemon && python3 -m uvicorn app_factory:app --reload --port 8765

# Build PKG installer
installer/build_pkg.sh
```

#### GetReceipts

```bash
cd /Users/matthewgreer/Projects/GetReceipts

# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm run test

# Build for production
npm run build
```

### Testing

#### Knowledge_Chipper

```bash
make test          # Full test suite
make test-quick    # Fast unit tests (~30s)
make test-daemon   # Daemon-specific tests
make smoke-test    # Basic functionality
```

#### GetReceipts

```bash
npm run test       # Vitest test suite
npm run type-check # TypeScript validation
npm run build      # Production build
npm run lint       # ESLint checks
```

### Contributing

#### Code Style

**Knowledge_Chipper:**
- Black (formatting)
- isort (import sorting)
- flake8 (linting)
- mypy (type checking)
- Pre-commit hooks enforce all

**GetReceipts:**
- Prettier (formatting)
- ESLint (linting)
- TypeScript strict mode
- Husky pre-commit hooks

#### Commit Guidelines

- Use conventional commits
- Reference issues in commit messages
- Update CHANGELOG.md for notable changes
- Update MANIFEST.md when adding/removing files

---

## Data Flow

### Upload Flow (Daemon → Web)

```
1. User submits content via GetReceipts.org/contribute
   ↓
2. Web sends job to daemon via REST API (localhost:8765)
   ↓
3. Daemon processes content:
   - Downloads video/audio
   - Transcribes with whisper.cpp
   - Extracts entities with two-pass LLM pipeline
   - Validates with Taste Filter and Truth Critic
   - Detects evolutions/contradictions with RAE
   - Generates long-form summary
   ↓
4. Daemon uploads results to GetReceipts API:
   - POST /api/knowledge-chipper/upload
   - Includes device credentials for attribution
   ↓
5. GetReceipts processes upload:
   - Deduplicates episodes (hash-based)
   - Fuzzy matches entities (95% threshold)
   - Merges duplicates automatically
   - Assigns entity codes (C/P/J/M prefixes)
   - Stores in Supabase
   ↓
6. User views results in web interface:
   - Claims page shows all extracted claims
   - Graph visualizes relationships
   - Explore paradigms for different views
```

### Offline Capabilities

**Daemon (Local):**
- Can process content offline
- Stores results in local SQLite database
- Queues uploads for when connection restored

**Web (Cloud):**
- Requires internet connection
- Can view previously synced data offline (browser cache)
- Cannot submit new jobs offline

---

## Database Schemas

### Knowledge_Chipper (SQLite)

**10 core tables** for local processing:

- `media_sources` - Videos, podcasts, documents
- `transcripts` - Transcription data with timestamps
- `summaries` - Analysis results with metrics
- `claims` - Extracted knowledge claims
- `people` - Mentioned individuals
- `jargon_terms` - Domain terminology
- `concepts` - Mental models
- `jobs` - Processing job tracking
- `feedback_examples` - Dynamic Learning feedback
- `pending_feedback` - Async feedback sync queue

**Purpose:** Ephemeral local storage for processing. Canonical data lives in Supabase.

### GetReceipts (Supabase PostgreSQL)

**40+ tables** for web features:

#### Core Knowledge
- `episodes` - Canonical episodes with deduplication
- `claims` - Knowledge claims with entity codes
- `people` - Individuals with entity codes
- `jargon` - Terminology with entity codes
- `concepts` - Mental models with entity codes
- `questions` - Extracted questions
- `evidence` - Supporting/opposing evidence

#### User Engagement
- `users` - User profiles with trust levels and Mana balance
- `annotations` - Universal notes (public/private)
- `claim_votes` - Community voting
- `claim_comments` - Threaded discussions (legacy)
- `annotations` - Enhanced threaded comments (new)
- `merge_proposals` - User-suggested entity merges
- `edit_proposals` - Proposed edits with voting
- `speaker_corrections` - Speaker attribution corrections

#### Knowledge Exploration
- `claim_groups` - User-created claim collections
- `claim_group_members` - Claims within groups
- `group_relations` - Relationships between groups
- `thinker_notes` - Annotations on people/thinkers
- `question_sides` - Explicit positions in debates

#### Prediction Markets
- `predictions` - Binary prediction markets
- `prediction_positions` - User bets with Mana
- `prediction_evidence` - Linked entities

#### Provenance & Security
- `devices` - Device authentication (Happy-style)
- `episode_uploads` - Provenance tracking per device
- `upload_audit_log` - Complete audit trail
- `upload_rate_limits` - Rate limiting tracking

---

## API Contract

### Daemon → Web Endpoints

**Active Endpoints:**

1. **Device Authentication**
   ```
   POST /api/knowledge-chipper/device-auth
   Body: { device_id, device_key }
   Returns: { authenticated: true }
   ```

2. **Upload Extracted Knowledge**
   ```
   POST /api/knowledge-chipper/upload
   Headers: X-Device-ID, X-Device-Key
   Body: { episode, claims, people, jargon, concepts, ... }
   Returns: { success: true, episode_code, ... }
   ```

3. **Validate Upload** (pre-flight check)
   ```
   POST /api/knowledge-chipper/validate
   Body: { episode, claims, ... }
   Returns: { valid: true, warnings: [] }
   ```

4. **Get Configuration** (sync settings from web)
   ```
   GET /api/knowledge-chipper/config
   Returns: { prompt_refinements, ... }
   ```

5. **Channel History** (RAE support)
   ```
   GET /api/channels/{channelId}/history
   Returns: { jargon_registry, top_claims, ... }
   ```

### Web → Daemon Endpoints

**Daemon REST API (localhost:8765):**

1. **Health Check**
   ```
   GET /health
   Returns: { status: "healthy", version: "1.1.x" }
   ```

2. **Process Content**
   ```
   POST /process
   Body: { url, whisper_model, llm_provider, ... }
   Returns: { job_id, status: "queued" }
   ```

3. **Batch Process**
   ```
   POST /process/batch
   Body: { urls: [...], local_paths: [...], ... }
   Returns: { job_ids: [...] }
   ```

4. **Get Jobs**
   ```
   GET /jobs?status=running&limit=50
   Returns: { jobs: [...], total: 123 }
   ```

5. **Get Job Details**
   ```
   GET /jobs/{job_id}
   Returns: { id, status, progress, result, ... }
   ```

6. **Retry/Cancel/Delete Jobs**
   ```
   POST /jobs/{job_id}/retry
   POST /jobs/{job_id}/cancel
   DELETE /jobs/{job_id}
   ```

7. **Configuration**
   ```
   GET /config
   POST /config
   GET /config/api-keys
   POST /config/api-keys
   GET /config/device-status
   ```

8. **Folder Monitoring**
   ```
   GET /monitor/status
   POST /monitor/start
   POST /monitor/stop
   POST /monitor/config
   ```

9. **Auto-Update**
   ```
   GET /updates/check
   POST /updates/install
   GET /updates/status
   ```

10. **Dynamic Learning**
    ```
    GET /feedback/stats
    POST /feedback/sync
    GET /feedback/queue-status
    ```

---

## Deployment

### Daemon Releases

**Automated via GitHub Actions:**

1. Tag version: `git tag v1.1.x`
2. Push tag: `git push origin v1.1.x`
3. GitHub Action triggers:
   - Runs daemon tests
   - Builds signed & notarized PKG
   - Creates GitHub release
   - Uploads PKG to releases

**Manual via script:**

```bash
~/Desktop/Release_Daemon.command
```

**Distribution:**
- **GitHub Releases:** https://github.com/msg43/Skipthepodcast.com/releases
- **Auto-Update:** Built-in update checker (24-hour interval)
- **Installation:** Users download PKG, run installer

### Web Deployment

**Platform:** Vercel  
**Database:** Supabase  
**Domain:** getreceipts.org

**Deployment Process:**

1. Push to main branch
2. Vercel auto-deploys
3. Run database migrations via Supabase SQL Editor
4. Verify deployment health

**Environment Variables:**
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL`
- `OPENAI_API_KEY` (for embeddings)

---

## Roadmap

### Planned Repo Merge

**Goal:** Merge Knowledge_Chipper and GetReceipts into single monorepo

**Benefits:**
- Unified version control
- Shared CI/CD pipelines
- Easier cross-codebase refactoring
- Single issue tracker
- Simplified development setup

**Structure (Proposed):**
```
getreceipts-monorepo/
├── daemon/           # Python daemon (from Knowledge_Chipper)
├── web/              # Next.js web app (from GetReceipts)
├── shared/           # Shared types, schemas, docs
├── database/         # Unified migrations
└── docs/             # Combined documentation
```

**Timeline:** TBD (after cleanup stabilizes)

### Near-Term Features

**Daemon:**
- Windows support (via WSL or native port)
- Linux support
- GPU acceleration for transcription
- Improved speaker attribution
- Document OCR support

**Web:**
- Mobile app (React Native)
- Advanced search with vector similarity
- AI-powered moderation
- Export features (CSV, JSON, Markdown)
- Federation (connect multiple instances)

### Long-Term Vision

- Real-time collaborative editing
- Topic modeling and trend analysis
- Knowledge graph reasoning
- Multi-language support
- Academic citation integration
- Podcast network analysis

---

## Known Limitations

### Daemon
- **macOS only** - No Windows/Linux support yet
- **Single user** - No multi-user support on same machine
- **English only** - Language detection not implemented
- **No GPU acceleration** - Whisper runs on CPU only

### Web
- **OpenAI required** - Fuzzy matching needs OpenAI embeddings API
- **No offline mode** - Requires internet connection
- **Limited mobile** - Not optimized for mobile browsers yet

### Both
- **No real-time sync** - Daemon uploads after processing completes
- **No conflict resolution** - Manual merge proposals only
- **No version control** - No history of entity edits

---

## Security

### Daemon
- **Device credentials** - UUID + bcrypt-hashed secret key
- **Local storage** - SQLite database in user's Application Support folder
- **API keys** - Stored in daemon config, never sent to GetReceipts
- **Auto-update** - Signed & notarized PKG installers only

### Web
- **Authentication** - Supabase JWT with OAuth support
- **Row-Level Security** - All tables protected with RLS policies
- **Rate Limiting** - 20 uploads/hour per device
- **Audit Trail** - Complete upload history with attribution
- **Content Validation** - Size limits, suspicious activity detection

---

## Troubleshooting

### Daemon Not Detected

1. Check daemon is running: `curl http://localhost:8765/health`
2. Restart daemon: Double-click desktop app → Restart
3. Check LaunchAgent: `launchctl list | grep getreceipts`
4. View logs: `~/Library/Logs/GetReceipts/daemon.log`

### Extraction Failures

1. Check API keys configured in web settings
2. Verify model is available (check provider API)
3. Check daemon logs for error messages
4. Try different LLM provider
5. See `ZERO_CLAIMS_DIAGNOSTIC_IMPLEMENTATION.md`

### Upload Failures

1. Verify device is linked to account
2. Check internet connection
3. Verify GetReceipts.org is accessible
4. Check rate limits (20 uploads/hour)
5. View upload audit log in web dashboard

---

## Support & Community

### Documentation
- **Knowledge_Chipper:** `READMEKC.md`, `CLAUDE.md`, `docs/`
- **GetReceipts:** `README.md`, `Docs/`
- **This Document:** Unified overview of both systems

### Links
- **Web App:** https://getreceipts.org
- **Daemon Releases:** https://github.com/msg43/Skipthepodcast.com/releases
- **Web Repo:** https://github.com/msg43/getreceipts-web
- **Daemon Repo:** https://github.com/msg43/Knowledge_Chipper

### Issues & Discussions
- **Daemon Issues:** https://github.com/msg43/Knowledge_Chipper/issues
- **Web Issues:** https://github.com/msg43/getreceipts-web/issues
- **Discussions:** GitHub Discussions on both repos

---

## License

Both projects are licensed under the MIT License.

---

## Acknowledgments

**Key Technologies:**
- OpenAI (GPT models, embeddings API)
- Anthropic (Claude models)
- Google (Gemini models)
- Supabase (database, auth, storage)
- Vercel (web hosting)
- yt-dlp (YouTube downloads)
- whisper.cpp (transcription)

**Open Source Libraries:**
- Next.js, React, FastAPI, SQLAlchemy
- D3.js, Sigma.js, Three.js
- shadcn/ui, Radix UI, Tailwind CSS
- And 100+ other amazing open source projects

---

**This document serves as the unified README for both Knowledge_Chipper and GetReceipts codebases in preparation for eventual repository merge.**

*Last Updated: January 17, 2026*
