"""Introduction tab providing comprehensive guidance for new users."""

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ...logger import get_logger
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


class IntroductionTab(BaseTab):
    """Introduction tab for new users."""

    # Signal for tab navigation
    navigate_to_tab = pyqtSignal(str)  # tab_name

    def __init__(self, parent: Any = None) -> None:
        self.tab_name = "Introduction"
        super().__init__(parent)

    def _setup_ui(self) -> None:
        """Setup the introduction UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Add margins

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Main content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # App overview
        self._create_overview_section(content_layout)

        # Quick start guide
        self._create_quick_start_section(content_layout)

        # Tab navigation guide
        self._create_tab_guide_section(content_layout)

        # YouTube bulk downloads guide
        self._create_youtube_guide_section(content_layout)

        # Common workflows
        self._create_workflows_section(content_layout)

        # Add stretch to push content to top
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def _create_overview_section(self, parent_layout: Any) -> None:
        """Create the app overview section."""
        # Section header
        header_label = QLabel("📚 Welcome to Skip the Podcast Desktop")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            "margin-top: 10px; margin-bottom: 10px; color: #007acc;"
        )
        parent_layout.addWidget(header_label)

        overview_text = QLabel(
            """
            <b style="font-size: 13pt;">Transform hours of media into minutes of insight</b>

            <br><br><b>What Skip the Podcast Does:</b>
            <br>Turn any podcast, video, lecture, or document into a searchable collection of <b>key claims</b> —
            the important facts, insights, and arguments that matter. Each claim is automatically scored and organized,
            so you can quickly find exactly what you need.

            <br><br><b>🎯 What You Can Process:</b>
            <br>• <b>YouTube:</b> Single videos or entire playlists (1000+ videos)
            <br>• <b>Audio Files:</b> Podcasts, interviews, lectures (MP3, WAV, M4A, FLAC, OGG, AAC, OPUS)
            <br>• <b>Video Files:</b> Local recordings, screen captures (MP4, WEBM, MOV, AVI, MKV)
            <br>• <b>Documents:</b> Research papers, articles, reports (PDF, Word, Markdown)
            <br>• <b>PDF Transcripts:</b> 🆕 Import podcaster-provided transcripts with automatic YouTube matching
            <br>• <b>RSS Feeds:</b> Automatically monitor and process new episodes

            <br><br><b>🌟 How It Works (Desktop + Web):</b>
            <br>• <b>Desktop App:</b> Processes files locally (transcribe, extract claims, score them)
            <br>• <b>Auto-Upload:</b> Claims automatically sync to GetReceipts.org (enabled by default)
            <br>• <b>Web App:</b> Review, edit, search, and curate your claims at getreceipts.org
            <br>• <b>Smart Sync:</b> Once uploaded, claims disappear from desktop (web is the source of truth)
            <br>• <b>Multi-Device:</b> Link multiple devices to one account using claim codes

            <br><br><b>💡 Perfect For:</b> Research, learning, content creation, meeting analysis, or building
            a personal knowledge base from audio/video sources.
            """
        )

        overview_text.setWordWrap(True)
        overview_text.setTextFormat(Qt.TextFormat.RichText)
        overview_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(overview_text)

    def _create_quick_start_section(self, parent_layout: Any) -> None:
        """Create the quick start guide section."""
        # Section header
        header_label = QLabel("🚀 Quick Start - Get Running in 3 Steps")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            "margin-top: 20px; margin-bottom: 10px; color: #007acc;"
        )
        parent_layout.addWidget(header_label)

        quickstart_text = QLabel(
            """
            <b>Step 1: Choose Your AI Provider</b>
            <br>Go to the <b>Settings</b> tab (far right) and configure your AI backend:
            <br>• <b>Local (Free):</b> The app will guide you to install Ollama for free local AI processing
            <br>• <b>Cloud (Paid):</b> Add your OpenAI or Anthropic API key for cloud-based models
            <br>• <b>Hybrid:</b> Use local models for transcription and cloud models for analysis

            <br><br><b>Step 2: Optional - Enable YouTube Access</b>
            <br>If you want to process YouTube videos (optional), you have two approaches:
            <br>• <b>Small Scale (1-10 videos):</b> Works without any setup - may hit rate limits
            <br>• <b>Bulk Downloads (10+ videos):</b> Use cookie authentication with throwaway Google account (see detailed guide below)
            <br>• Skip this entirely if you're only processing local files, PDFs, or RSS feeds

            <br><br><b>Step 3: Process Your First Item</b>
            <br>Navigate through the tabs from left to right:
            <br>1. <b>Transcribe</b> → Add YouTube URL, local file, or document
            <br>2. Check <b>"Process automatically through entire pipeline"</b> for one-click processing
            <br>3. Click <b>Start Transcription</b> and wait for completion
            <br>4. Claims are automatically uploaded to GetReceipts.org (if auto-upload is enabled)

            <br><br><b>Step 4: Review on the Web</b>
            <br>• Go to <b>getreceipts.org/dashboard</b> to see your uploaded claims
            <br>• Search, filter, edit, and organize your claims in the web interface
            <br>• Link your device to your account using the claim code from Settings tab

            <br><br><b>✅ That's it!</b> The desktop app handles processing, and the web app handles review and curation.
            Once uploaded, claims disappear from desktop (web is the canonical source).

            <br><br><b>💡 Pro Tip:</b> Auto-upload is enabled by default. You can disable it in Settings if you prefer
            manual uploads, but the web interface is where you'll do most of your review and editing.
            """
        )

        quickstart_text.setWordWrap(True)
        quickstart_text.setTextFormat(Qt.TextFormat.RichText)
        quickstart_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(quickstart_text)

    def _create_tab_guide_section(self, parent_layout: Any) -> None:
        """Create the tab guide section."""
        # Section header
        header_label = QLabel("🗂️ How to Use Each Tab")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            "margin-top: 20px; margin-bottom: 10px; color: #007acc;"
        )
        parent_layout.addWidget(header_label)

        tabs_text = QLabel(
            """
            <b style="color: #007acc;">1. Introduction</b> (You are here!)
            <br>Your starting point for learning how everything works. Come back here whenever you need a refresher.

            <br><br><b style="color: #007acc;">2. Transcribe</b> - Start Here for New Content
            <br><b>What you'll do:</b> Add content to process (YouTube URL, audio file, video, or PDF)
            <br><b>Key option:</b> Check "Process automatically through entire pipeline" to go from input to finished
            claims in one click
            <br><b>Batch mode:</b> Select entire folders to process multiple files at once
            <br><b>Output:</b> Transcript files with speaker labels and timestamps

            <br><br><b style="color: #007acc;">3. Import Transcripts</b> 🆕 - Import High-Quality PDF Transcripts
            <br><b>What you'll do:</b> Import podcaster-provided PDF transcripts with speaker labels already included
            <br><b>Why this matters:</b> Professional transcripts have explicit speaker attribution and better accuracy
            <br><b>Key features:</b>
            <br>• <b>Single import:</b> Browse for one PDF, optionally provide YouTube URL
            <br>• <b>Batch import:</b> Scan entire folders of PDFs
            <br>• <b>Auto-matching:</b> System automatically finds the YouTube video using 4 strategies
            <br>• <b>Multi-transcript:</b> PDF, YouTube, and Whisper transcripts can coexist per episode
            <br>• <b>Quality priority:</b> System uses highest-quality transcript (PDF > YouTube > Whisper)
            <br><b>Perfect for:</b> When podcasters provide official transcripts (better than auto-generated)

            <br><br><b style="color: #007acc;">4. Prompts</b> - Customize What Gets Extracted
            <br><b>What you'll do:</b> Edit the instructions that tell the AI what to look for and how to analyze content
            <br><b>Why this matters:</b> The AI follows written prompts (instructions) to extract claims. You can customize
            these to focus on what you care about - technical details, business insights, controversial arguments, etc.
            <br><b>Example uses:</b>
            <br>• Analyzing medical podcasts? Edit prompts to prioritize treatment claims and research findings
            <br>• Business content? Focus on strategic insights and market analysis
            <br>• Academic lectures? Extract definitions, theories, and evidence-based claims
            <br><b>What you'll see:</b> Text files containing the prompts, plus JSON schemas that define the output structure
            <br><b>Note:</b> The defaults work great for most content - only customize if you have specific needs

            <br><br><b style="color: #007acc;">5. Extract</b> - Claims-First Extraction
            <br><b>What you'll do:</b> Process transcripts through the claims-first pipeline
            <br><b>Output:</b> Structured claims with scoring, speaker attribution, and quality assessment

            <br><br><b style="color: #007acc;">6. Summarize</b> - The Analysis Engine
            <br><b>What you'll do:</b> This is where transcripts become structured knowledge
            <br><b>The process:</b>
            <br>1. Select transcript files (single file or entire folders)
            <br>2. Choose your analysis type (default: "Unified HCE" extracts claims, people, concepts)
            <br>3. Pick AI models: <b>Miner</b> (extracts raw claims) and <b>Flagship</b> (rates and validates them)
            <br>4. Click Start Analysis and watch progress
            <br><b>What gets extracted:</b>
            <br>• <b>Claims:</b> Specific statements being made ("The author argues that X causes Y")
            <br>• <b>Scores:</b> Each claim rated 1-10 for importance, novelty, and confidence
            <br>• <b>Types:</b> Categorized as factual, causal, normative, forecast, or definition
            <br>• <b>Tiers:</b> A (most important), B (significant), C (supporting details)
            <br>• <b>People:</b> Key figures mentioned and their roles
            <br>• <b>Concepts:</b> Important ideas and terminology
            <br><b>Output files:</b> Markdown summaries, CSV exports, and database entries you can review/edit
            <br><b>Time estimate:</b> ~30-90 seconds per 10,000 words, depending on AI model speed

            <br><br><b style="color: #007acc;">7. Queue</b> - Monitor Processing Pipeline
            <br><b>What you'll do:</b> Watch your files as they move through the processing pipeline
            <br><b>What you'll see:</b> Real-time status of transcription, speaker detection, and claim extraction
            <br><b>When to use:</b> Check progress on long-running jobs, see if anything got stuck
            <br><b>Note:</b> This is for monitoring - actual review happens on the web at getreceipts.org

            <br><br><b style="color: #007acc;">8. Monitor</b> - Automated Background Processing
            <br><b>What you'll do:</b> Set up a folder for automatic monitoring, then forget about it
            <br><b>How it works:</b>
            <br>1. Choose a folder to watch (e.g., your Downloads folder or podcast directory)
            <br>2. Set file patterns: <b>*.mp3</b> for audio, <b>*.mp4</b> for video, <b>*.pdf</b> for documents, or all of them
            <br>3. Optional: Enable "Watch subdirectories" to monitor nested folders
            <br>4. Set debounce delay (default 5 seconds) - waits for file to finish copying before processing
            <br>5. Click "Start Watching" - the app now monitors that folder continuously
            <br><b>What happens automatically:</b>
            <br>• New file appears → System waits 5 seconds (ensures file is complete)
            <br>• Automatic transcription with speaker detection
            <br>• Automatic claim extraction and scoring
            <br>• Automatic upload to GetReceipts.org (if enabled)
            <br>• View results on web at getreceipts.org/dashboard
            <br><b>Perfect scenarios:</b>
            <br>• <b>Podcast RSS feeds:</b> Your podcast app downloads episodes → Monitor auto-processes them
            <br>• <b>Regular meetings:</b> Meeting recordings saved to a folder → auto-transcribed with speaker labels
            <br>• <b>Content research:</b> Save videos/PDFs to a folder as you find them → wake up to processed summaries
            <br>• <b>Lecture series:</b> Professor uploads weekly lectures → all automatically analyzed
            <br><b>Control:</b> Stop/start watching anytime, change folders, adjust file patterns on the fly

            <br><br><b style="color: #007acc;">9. Settings</b> - One-Time Setup
            <br><b>What you'll do:</b> Configure API keys, install AI models, and set preferences
            <br><b>Required:</b> Choose local AI (free via Ollama) or cloud AI (paid via OpenAI/Anthropic)
            <br><b>Optional:</b>
            <br>• Add YouTube Data API key for reliable metadata (free 10,000 lookups/day)
            <br>• Add PacketStream credentials if you want to process YouTube videos
            <br><b>Device Linking:</b> Get your claim code here to link this device to your GetReceipts account
            <br>• <b>Auto-upload:</b> Enabled by default - claims automatically sync to web after processing
            <br>• <b>Claim code:</b> Use this code on getreceipts.org/dashboard to link your device
            <br><b>When to revisit:</b> To install new models, update the app, change API keys, or link/unlink devices
            """
        )

        tabs_text.setWordWrap(True)
        tabs_text.setTextFormat(Qt.TextFormat.RichText)
        tabs_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(tabs_text)

    def _create_youtube_guide_section(self, parent_layout: Any) -> None:
        """Create YouTube processing guide section."""
        # Section header
        header_label = QLabel("📹 YouTube Video Processing - Two-Phase System")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            "margin-top: 20px; margin-bottom: 10px; color: #007acc;"
        )
        parent_layout.addWidget(header_label)

        youtube_text = QLabel(
            """
            <b>🚀 NEW: Two-Phase Transcript Acquisition (10-100x Faster!)</b>

            <br><br><b>How It Works:</b>
            <br>The system now uses an intelligent two-phase approach to get transcripts from YouTube:

            <br><br><b style="color: #388e3c;">Phase 1: Rapid Metadata + Transcript Fetch (1-3 seconds per video)</b>
            <br>• Fetches video metadata (title, description, duration, etc.) via YouTube API
            <br>• Attempts to get official YouTube transcript (auto-generated or manual captions)
            <br>• Uses burst pattern: processes 20 videos rapidly, then pauses 30-60 seconds (mimics human browsing)
            <br>• <b>Result:</b> Most videos get transcripts instantly without downloading any audio!

            <br><br><b style="color: #ff9800;">Phase 2: Selective Whisper Fallback (3-5 minutes per video)</b>
            <br>• Only runs for videos that don't have YouTube transcripts available
            <br>• Downloads audio file from YouTube
            <br>• Transcribes with Whisper AI (no speaker diarization in fallback mode)
            <br>• Uses slow, careful pacing (3-5 minute delays) to avoid bot detection
            <br>• <b>Result:</b> High-quality Whisper transcripts for videos without captions

            <br><br><b>🎯 What This Means For You:</b>
            <br>• <b>Playlists with captions:</b> 100 videos processed in ~5-10 minutes (vs. 5-8 hours before!)
            <br>• <b>Mixed playlists:</b> Fast for videos with captions, slow only for those without
            <br>• <b>No setup required:</b> Works out of the box for most content
            <br>• <b>User control:</b> New "Force Whisper" checkbox if you prefer Whisper quality over speed

            <br><br><b style="color: #007acc;">Using the Force Whisper Option</b>
            <br>In the <b>Transcribe</b> tab, you'll now see a checkbox: <b>"Force Whisper Transcription"</b>

            <br><br><b>When to use it:</b>
            <br>• YouTube's auto-generated captions are poor quality for your content
            <br>• You need the highest accuracy possible (Whisper is often more accurate)
            <br>• You're processing technical content where precision matters
            <br>• You don't mind waiting longer for better quality

            <br><br><b>What it does:</b>
            <br>• Skips Phase 1 entirely (doesn't try YouTube transcripts)
            <br>• Goes straight to Phase 2 (downloads audio + Whisper transcription)
            <br>• Uses slow 3-5 minute delays between videos
            <br>• <b>Warning label appears:</b> "⚠️ Slow mode: 3-5 min delays"

            <br><br><b>Time comparison for 50 videos:</b>
            <br>• <b>Default (two-phase):</b> 5-15 minutes if all have captions, up to 4 hours if none do
            <br>• <b>Force Whisper:</b> 2.5-4 hours regardless (always downloads + transcribes)

            <br><br><b style="color: #007acc;">Small Scale (1-10 videos) - No Setup Needed</b>
            <br>For small batches, the system works without any configuration:
            <br>1. Paste YouTube URLs in the <b>Transcribe</b> tab
            <br>2. Check "Process automatically through entire pipeline"
            <br>3. Click <b>Start Transcription</b>
            <br>4. Phase 1 gets transcripts for videos with captions (~seconds)
            <br>5. Phase 2 handles any videos without captions (~minutes each)
            <br>6. Claims automatically upload to GetReceipts.org

            <br><br><b style="color: #007acc;">Bulk Downloads (10+ videos) - Cookie Authentication</b>
            <br>For larger batches or if you encounter rate limiting, use cookie authentication:

            <br><br><b>Why cookies help:</b>
            <br>• Phase 1 rarely needs them (metadata/transcript fetching is fast and light)
            <br>• Phase 2 benefits from cookies (audio downloads can trigger bot detection)
            <br>• Cookies authenticate you as a real user, not a bot

            <br><br><b style="color: #d32f2f;">🔒 Security First - Read This!</b>
            <br><b style="color: #d32f2f;">NEVER use your main Google account!</b> Create a throwaway account for bulk downloads.

            <br><br><b>Quick Cookie Setup (5 minutes):</b>

            <br><br><b style="color: #007acc;">Step 1: Create Throwaway Google Account</b>
            <br>1. Go to <a href="https://accounts.google.com">accounts.google.com</a> and create new account
            <br>2. Log in to YouTube with this account
            <br>3. This is your dedicated download account - never use for personal stuff

            <br><br><b style="color: #007acc;">Step 2: Export Cookies</b>
            <br>1. Open <b>incognito/private window</b> and log in to YouTube with throwaway account
            <br>2. Install cookie export extension (Chrome: "Get cookies.txt LOCALLY", Firefox: "cookies.txt")
            <br>3. Click extension icon → Export → Save as .txt file
            <br>4. Close incognito window

            <br><br><b style="color: #007acc;">Step 3: Configure in App</b>
            <br>1. <b>Transcribe</b> tab → scroll to "Cookie Authentication" section
            <br>2. Check "Enable cookie-based authentication"
            <br>3. Click "Browse" and select your cookies.txt file
            <br>4. Done! The system will now use cookies for Phase 2 downloads

            <br><br><b>⚡ New Time Estimates with Two-Phase System:</b>
            <br><b>10 videos (all with captions):</b>
            <br>• Phase 1: ~1-2 minutes (rapid transcript fetch)
            <br>• Phase 2: Not needed!
            <br>• <b>Total: 1-2 minutes</b> (vs. 30-50 minutes before)

            <br><br><b>50 videos (40 with captions, 10 without):</b>
            <br>• Phase 1: ~5-10 minutes (gets 40 transcripts)
            <br>• Phase 2: ~30-50 minutes (downloads + transcribes 10 videos)
            <br>• <b>Total: 35-60 minutes</b> (vs. 2.5-4 hours before)

            <br><br><b>100 videos (all with captions):</b>
            <br>• Phase 1: ~10-15 minutes (rapid transcript fetch)
            <br>• Phase 2: Not needed!
            <br>• <b>Total: 10-15 minutes</b> (vs. 5-8 hours before)

            <br><br><b>100 videos (Force Whisper enabled):</b>
            <br>• Phase 1: Skipped
            <br>• Phase 2: ~5-8 hours (downloads + transcribes all 100)
            <br>• <b>Total: 5-8 hours</b> (same as before, but higher quality)

            <br><br><b style="color: #ffa000;">⚡ Troubleshooting</b>

            <br><br><b>Issue: Phase 1 gets transcripts but they're poor quality</b>
            <br><b>Solution:</b> Check the "Force Whisper Transcription" checkbox to skip YouTube transcripts and use Whisper for higher accuracy.

            <br><br><b>Issue: "Sign in to confirm you're not a bot" during Phase 2</b>
            <br><b>Solution:</b> This only affects Phase 2 (audio downloads). Set up cookie authentication as described above.

            <br><br><b>Issue: Some videos fail with "No transcript available"</b>
            <br><b>Solution:</b> Normal! Phase 1 tries YouTube transcripts, Phase 2 automatically handles videos without them via Whisper.

            <br><br><b>Issue: Want faster processing for videos without captions</b>
            <br><b>Solution:</b> Phase 2 delays are intentionally slow (3-5 min) to avoid bot detection. This is necessary for reliability.
            <br>Consider: Most content has captions now - Phase 1 handles those in seconds!

            <br><br><b style="color: #388e3c;">✅ Best Practices with Two-Phase System</b>
            <br>• <b>Try default first:</b> Let Phase 1 get transcripts rapidly, Phase 2 handles exceptions
            <br>• <b>Use Force Whisper sparingly:</b> Only when you need maximum accuracy and don't mind waiting
            <br>• <b>Check "Process automatically":</b> Claims extraction happens while transcripts are being fetched
            <br>• <b>Cookies optional for Phase 1:</b> Only needed if you hit rate limits or for Phase 2 downloads
            <br>• <b>Monitor progress:</b> Watch the log to see which phase is handling each video
            <br>• <b>Refresh cookies weekly:</b> If using cookie auth, export fresh cookies every 7-10 days

            <br><br><b style="color: #007acc;">🎯 Real-World Example: Processing a 100-Video Lecture Series</b>

            <br><b>Scenario:</b> Educational playlist with 100 lectures, all have auto-generated captions.

            <br><br><b>OLD SYSTEM (before two-phase):</b>
            <br>• Setup: 12 minutes (create account, export cookies, configure)
            <br>• Processing: 5-8 hours (download all 100 audio files with delays)
            <br>• <b>Total: ~6-9 hours</b>

            <br><br><b>NEW SYSTEM (two-phase):</b>
            <br>• Setup: None required! (works out of the box)
            <br>• Phase 1: 10-15 minutes (rapid transcript fetch for all 100 videos)
            <br>• Phase 2: Not needed (all videos had captions)
            <br>• <b>Total: 10-15 minutes</b> 🎉

            <br><br><b>What you get (same as before):</b>
            <br>• All 100 transcripts
            <br>• All claims extracted and scored
            <br>• Automatically uploaded to GetReceipts.org
            <br>• Searchable on web: "What did the professor say about machine learning?"

            <br><br><b>Time savings: 6-9 hours → 10-15 minutes (30-50x faster!)</b>

            <br><br><b style="color: #007acc;">📝 Quick Decision Guide</b>

            <br><br><b>Processing 1-10 videos?</b>
            <br>→ Just paste URLs and click Start. No setup needed. Phase 1 handles most, Phase 2 handles exceptions.

            <br><br><b>Processing 10-100 videos with captions?</b>
            <br>→ No setup needed! Phase 1 gets all transcripts in minutes.

            <br><br><b>Processing 100+ videos or hitting rate limits?</b>
            <br>→ Set up cookie authentication (5 min setup). Helps with Phase 2 downloads.

            <br><br><b>Need maximum transcript accuracy?</b>
            <br>→ Check "Force Whisper Transcription". Slower but higher quality.

            <br><br><b>Videos don't have captions?</b>
            <br>→ Phase 2 automatically handles them. Set up cookies if processing many.

            <br><br><b>🎓 Remember:</b> The two-phase system is automatic. You don't choose phases - the system intelligently
            uses Phase 1 when possible (fast) and Phase 2 when needed (slow but thorough). Just paste URLs and go!
            """
        )

        youtube_text.setWordWrap(True)
        youtube_text.setTextFormat(Qt.TextFormat.RichText)
        youtube_text.setStyleSheet("line-height: 1.4;")
        youtube_text.setOpenExternalLinks(
            True
        )  # Allow clicking the Google accounts link
        parent_layout.addWidget(youtube_text)

    def _create_workflows_section(self, parent_layout: Any) -> None:
        """Create common workflows section."""
        # Section header
        header_label = QLabel("💼 Step-by-Step Examples")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            "margin-top: 20px; margin-bottom: 10px; color: #007acc;"
        )
        parent_layout.addWidget(header_label)

        workflows_text = QLabel(
            """
            <b>Example 1: "I want to understand a 2-hour podcast without listening to it"</b>
            <br><br>1. Get the podcast file (MP3) or YouTube URL
            <br>2. Open <b>Transcribe</b> tab → paste URL or drag in the MP3 file
            <br>3. Check <b>"Process automatically through entire pipeline"</b> (this is the magic checkbox!)
            <br>4. Click <b>Start Transcription</b> and grab coffee ☕ (takes 5-15 minutes depending on file length)
            <br>5. Claims are automatically uploaded to GetReceipts.org (if auto-upload is enabled)
            <br>6. Go to <b>getreceipts.org/dashboard</b> to see your claims
            <br>7. Use the <b>Tier filter</b> → select "A" to show only the most important claims
            <br>8. You'll see 10-20 Tier A claims with the key insights
            <br>9. Click any claim to read the full text, edit it, or see its scores
            <br>10. Export filtered claims to CSV if needed
            <br><br><b>What you'll see:</b> Claims like "The guest argues that AI regulation should prioritize safety over
            innovation (Importance: 9/10, Novelty: 7/10)" - the essence of 2 hours distilled into a few minutes of reading.
            <br><b>Where:</b> All review and editing happens on the web - desktop just processes and uploads.

            <br><br><b>Example 2: "I downloaded 50 podcast episodes and need summaries of all of them"</b>
            <br><br>1. Put all MP3 files in one folder
            <br>2. Open <b>Transcribe</b> tab → click "Select Folder" and choose that folder
            <br>3. Check <b>"Process automatically"</b> and <b>"Enable Speaker Diarization"</b>
            <br>4. Click <b>Start Transcription</b> → the app processes all 50 files (this will take a while!)
            <br>5. Go get lunch or do other work 🍔 (expect 2-4 hours for 50 episodes depending on your AI setup)
            <br>6. Claims automatically upload to GetReceipts.org as they're processed
            <br>7. Go to <b>getreceipts.org/dashboard</b> → all your claims are there
            <br>8. Use the <b>Search box</b> → type "climate change" to find all claims mentioning that topic across
            all 50 episodes
            <br>9. Filter to <b>Tier A</b> and <b>sort by Importance</b> to see the most critical insights across the
            entire series
            <br>10. Export the filtered results to CSV for your research database
            <br><br><b>Result:</b> Instead of 50+ hours of listening, you have a searchable database on the web where you can
            find any topic in seconds. Desktop processes, web stores and organizes.

            <br><br><b>Example 3: "I have a research paper (PDF) and need to extract the key findings"</b>
            <br><br>1. Open <b>Transcribe</b> tab → drag and drop your PDF
            <br>2. Check <b>"Process automatically"</b>
            <br>3. Click <b>Start Transcription</b> (yes, same button for PDFs!)
            <br>4. Wait for processing to finish → claims automatically upload to web
            <br>5. Go to <b>getreceipts.org/dashboard</b> → filter to show factual claims only
            <br>6. Export to CSV to paste into your literature review spreadsheet
            <br><br><b>What you'll get:</b> Every significant claim from the paper, scored and categorized,
            ready to cite or compare with other papers. All stored and searchable on the web.

            <br><br><b>Example 4: "I want my podcast RSS feed to auto-process every new episode"</b>
            <br><br><b>Initial Setup (One Time):</b>
            <br>1. Set up your podcast app to download episodes to a specific folder (e.g., ~/Downloads/Podcasts)
            <br>2. Open <b>Monitor</b> tab in Skip the Podcast
            <br>3. Click "Browse" and select that ~/Downloads/Podcasts folder
            <br>4. Set file patterns to <b>*.mp3</b> (or <b>*.mp3,*.m4a</b> if your podcast app uses multiple formats)
            <br>5. Keep "Watch subdirectories" checked if your podcast app organizes by show name
            <br>6. Debounce delay: Set to 30 seconds (gives podcast app time to finish downloading)
            <br>7. Click <b>"Start Watching"</b> → the app icon shows it's actively monitoring
            <br><br><b>What Happens Next (Automatic):</b>
            <br>• Your podcast app downloads a new episode → file appears in folder
            <br>• Monitor waits 30 seconds to ensure download is complete
            <br>• Automatic transcription with speaker detection
            <br>• Automatic claim extraction and scoring
            <br>• Automatic upload to GetReceipts.org
            <br>• You get a notification (optional in Settings)
            <br><br><b>Your Weekly Routine:</b>
            <br>• Go to <b>getreceipts.org/dashboard</b> → filter to claims from the last 7 days
            <br>• Scan Tier A claims to catch the most important insights
            <br>• Search for topics you're tracking across all episodes
            <br><br><b>Perfect for:</b> News podcasts, industry updates, or educational series - stay current without
            manual processing.

            <br><br><b>Example 5: "I recorded a meeting and need to know who said what"</b>
            <br><br>1. Open <b>Transcribe</b> tab → drag in your meeting recording (MP4, MOV, etc.)
            <br>2. Make sure <b>"Enable Speaker Diarization"</b> is checked
            <br>3. Check <b>"Process automatically"</b> to extract claims automatically
            <br>4. Click <b>Start Transcription</b> and wait for completion
            <br>5. Claims automatically upload to GetReceipts.org with speaker labels
            <br>6. Go to <b>getreceipts.org/dashboard</b> → see which speaker made which claims
            <br>7. Edit speaker names on the web if needed (assign real names to Speaker 0, Speaker 1, etc.)
            <br><br><b>Bonus:</b> Export the claims with speaker labels from the web to share meeting notes with your team.

            <br><br><b>💡 Quick Tips for Success:</b>
            <br>• <b>First time?</b> Start with one YouTube video to see the two-phase system in action
            <br>• <b>YouTube playlists?</b> No setup needed for most content - Phase 1 gets transcripts in seconds!
            <br>• <b>Force Whisper checkbox:</b> Use when you need maximum accuracy (slower but better quality)
            <br>• <b>Want faster processing?</b> Use cloud models (OpenAI/Anthropic) instead of local Ollama for claim extraction
            <br>• <b>Understanding the scores:</b> Importance = how significant, Novelty = how unique/surprising,
            Confidence = how reliable
            <br>• <b>Auto-upload enabled?</b> Claims automatically sync to getreceipts.org - that's where you review and edit
            <br>• <b>Finding too many low-value claims?</b> Filter to Tier A only on the web to see just the best stuff
            <br>• <b>Need claims in another app?</b> Export CSV from getreceipts.org/dashboard → works in Excel, Notion, Airtable, etc.
            <br>• <b>Want specialized extraction?</b> Edit prompts in Prompts tab (e.g., focus on statistics, prioritize
            medical claims, extract business metrics)
            <br>• <b>Experiment with models:</b> In Summarize tab, try different Miner/Flagship combinations - larger models
            = better quality but slower
            <br>• <b>Monitor vs Manual:</b> Use Monitor for ongoing series (podcasts, courses), use Transcribe for one-off processing
            <br>• <b>Link your device:</b> Get your claim code from Settings → use it on getreceipts.org/dashboard to link multiple devices
            <br>• <b>Desktop vs Web:</b> Desktop processes files, web stores and organizes claims. Once uploaded, claims disappear from desktop.
            <br>• <b>Two-phase is automatic:</b> You don't choose phases - system uses Phase 1 when possible, Phase 2 when needed
            """
        )

        workflows_text.setWordWrap(True)
        workflows_text.setTextFormat(Qt.TextFormat.RichText)
        workflows_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(workflows_text)
