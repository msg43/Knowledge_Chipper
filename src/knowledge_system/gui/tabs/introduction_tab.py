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

            <br><br><b style="color: #007acc;">3. Prompts</b> - Customize What Gets Extracted
            <br><b>What you'll do:</b> Edit the instructions that tell the AI what to look for and how to analyze content
            <br><b>Why this matters:</b> The AI follows written prompts (instructions) to extract claims. You can customize
            these to focus on what you care about - technical details, business insights, controversial arguments, etc.
            <br><b>Example uses:</b>
            <br>• Analyzing medical podcasts? Edit prompts to prioritize treatment claims and research findings
            <br>• Business content? Focus on strategic insights and market analysis
            <br>• Academic lectures? Extract definitions, theories, and evidence-based claims
            <br><b>What you'll see:</b> Text files containing the prompts, plus JSON schemas that define the output structure
            <br><b>Note:</b> The defaults work great for most content - only customize if you have specific needs

            <br><br><b style="color: #007acc;">4. Summarize</b> - The Analysis Engine
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

            <br><br><b style="color: #007acc;">5. Queue</b> - Monitor Processing Pipeline
            <br><b>What you'll do:</b> Watch your files as they move through the processing pipeline
            <br><b>What you'll see:</b> Real-time status of transcription, speaker detection, and claim extraction
            <br><b>When to use:</b> Check progress on long-running jobs, see if anything got stuck
            <br><b>Note:</b> This is for monitoring - actual review happens on the web at getreceipts.org

            <br><br><b style="color: #007acc;">6. Monitor</b> - Automated Background Processing
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

            <br><br><b style="color: #007acc;">7. Settings</b> - One-Time Setup
            <br><b>What you'll do:</b> Configure API keys, install AI models, and set preferences
            <br><b>Required:</b> Choose local AI (free via Ollama) or cloud AI (paid via OpenAI/Anthropic)
            <br><b>Optional:</b> Add PacketStream credentials if you want to process YouTube videos
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
        """Create YouTube bulk downloads guide section."""
        # Section header
        header_label = QLabel("📹 YouTube Bulk Downloads - Complete Setup Guide")
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
            <b>⚠️ IMPORTANT: This is for processing 10+ YouTube videos. Skip this section if you only need 1-5 videos.</b>

            <br><br><b>Why You Need This:</b>
            <br>YouTube has bot detection that blocks bulk downloads from anonymous requests. The solution is to use
            cookies from a <b>throwaway Google account</b> to authenticate downloads, combined with smart rate limiting
            to avoid account flags.

            <br><br><b style="color: #d32f2f;">🔒 Security First - Read This!</b>
            <br><b style="color: #d32f2f;">NEVER use your main Google account for this!</b> YouTube may flag accounts doing
            bulk downloads. Always create a dedicated throwaway account.

            <br><br><b>The Complete Setup Process:</b>

            <br><br><b style="color: #007acc;">Step 1: Create Throwaway Google Account</b>
            <br>1. Go to <a href="https://accounts.google.com">accounts.google.com</a> and create a new Google account
            <br>2. Use a name like "YouTube Downloader" or "Research Account" - doesn't matter
            <br>3. <b>Write down the email and password</b> - you'll need them again when cookies expire
            <br>4. Log in to YouTube with this account (visit youtube.com)
            <br>5. This is your dedicated download account - <b>never use it for anything personal</b>

            <br><br><b style="color: #007acc;">Step 2: Export Cookies from Throwaway Account</b>
            <br>1. <b>Open incognito/private browsing window</b> (this is crucial!)
            <br>   • Chrome: Ctrl+Shift+N (Windows) or Cmd+Shift+N (Mac)
            <br>   • Firefox: Ctrl+Shift+P (Windows) or Cmd+Shift+P (Mac)
            <br>   • Safari: File → New Private Window
            <br>2. In the private window, go to YouTube and log in with your <b>throwaway account only</b>
            <br>3. Install a cookie export extension in your browser:
            <br>   • Chrome: "<b>Get cookies.txt LOCALLY</b>" extension (search Chrome Web Store)
            <br>   • Firefox: "<b>cookies.txt</b>" add-on (search Firefox Add-ons)
            <br>   • Make sure it's a reputable extension with good reviews
            <br>4. With YouTube still open, click the extension icon
            <br>5. Click "Export" or "Download" to save cookies as a <b>.txt file</b> (Netscape format)
            <br>6. Save the file somewhere safe (e.g., Documents/youtube-cookies.txt)
            <br>7. Close the incognito window

            <br><br><b style="color: #007acc;">Step 3: Configure Cookie Authentication in Skip the Podcast</b>
            <br>1. Open Skip the Podcast Desktop → go to <b>Transcribe</b> tab
            <br>2. Scroll down to find "<b>Cookie Authentication (Throwaway Account)</b>" section
            <br>3. Check the box: <b>"Enable cookie-based authentication"</b>
            <br>4. Click the <b>"Browse..."</b> button next to "Cookie file"
            <br>5. Navigate to and select your youtube-cookies.txt file
            <br>6. You should see the file path appear in the text box

            <br><br><b style="color: #007acc;">Step 4: Configure Rate Limiting (Anti-Bot Protection)</b>
            <br>In the same Transcribe tab, scroll to "<b>Rate Limiting (Anti-Bot Protection)</b>" section:
            <br>• <b>Min delay:</b> 180 seconds (3 minutes) - <i>recommended default</i>
            <br>• <b>Max delay:</b> 300 seconds (5 minutes) - <i>recommended default</i>
            <br>• <b>Randomization:</b> 25% - <i>adds natural variation, keep this</i>
            <br>• Check <b>"Disable proxies when cookies enabled"</b> - <i>highly recommended</i>
            <br><br><b>What these settings mean:</b>
            <br>The app will wait 3-5 minutes between each download (randomly varied by ±25%). This mimics human
            behavior and prevents YouTube from flagging your throwaway account.

            <br><br><b style="color: #007acc;">Step 5: Start Bulk Downloads</b>
            <br>1. In the <b>Transcribe</b> tab, paste your YouTube URLs (one per line) or a playlist URL
            <br>2. Check <b>"Process automatically through entire pipeline"</b> if you want automatic analysis
            <br>3. Check <b>"Enable Speaker Diarization"</b> if the videos have multiple speakers
            <br>4. Click <b>"Start Transcription"</b>
            <br>5. Sit back and let it run - downloads will proceed one at a time with delays between them
            <br><br><b>Time estimates for bulk downloads:</b>
            <br>• 10 videos: 30-50 minutes (download time) + processing time
            <br>• 50 videos: 2.5-4 hours (download time) + processing time
            <br>• 100 videos: 5-8 hours (download time) + processing time
            <br>These are just download times - add transcription and analysis time on top

            <br><br><b style="color: #ffa000;">⚡ Troubleshooting Common Issues</b>

            <br><br><b>Issue: "Sign in to confirm you're not a bot" errors even with cookies</b>
            <br><b>Solution:</b> Your cookies may have expired. Repeat Step 2 to export fresh cookies from your throwaway account.

            <br><br><b>Issue: Downloads work for a while then start failing</b>
            <br><b>Solution:</b> YouTube flagged your usage. Stop downloads for 24 hours, then:
            <br>• Increase delays: Try min=300 (5 min), max=600 (10 min)
            <br>• Export fresh cookies
            <br>• Resume downloads slowly

            <br><br><b>Issue: "Cookie file not found" error</b>
            <br><b>Solution:</b> Check the file path in the text box. Click Browse again and make sure you select the
            .txt file you exported.

            <br><br><b>Issue: Some videos fail with "Video unavailable"</b>
            <br><b>Solution:</b> The video may be age-restricted, private, or region-locked. Your throwaway account needs to
            verify age or the video may simply not be accessible.

            <br><br><b>Issue: Want to download faster (smaller delays)</b>
            <br><b>⚠️ Not recommended!</b> But if you must:
            <br>• Min=60 seconds (1 min), Max=120 (2 min) - <b>high risk of account flags</b>
            <br>• Only use for small batches (5-10 videos max)
            <br>• Be prepared to get blocked and need to wait 24 hours

            <br><br><b style="color: #388e3c;">✅ Best Practices for Bulk Downloads</b>
            <br>• <b>Keep the defaults:</b> 3-5 minute delays work great and rarely get flagged
            <br>• <b>Run overnight:</b> Start a batch before bed, check results in the morning
            <br>• <b>Multiple accounts:</b> If you need to download thousands, create 2-3 throwaway accounts and rotate them
            <br>• <b>Refresh cookies weekly:</b> Export fresh cookies every 7-10 days to avoid expiration issues
            <br>• <b>Monitor first batch:</b> Watch the first 5-10 downloads to make sure everything works
            <br>• <b>Split large batches:</b> Instead of 500 videos at once, do 5 batches of 100
            <br>• <b>Use "Process automatically":</b> Transcription and analysis happen while downloads continue

            <br><br><b style="color: #007acc;">🎯 Real-World Example: Processing a 100-Video Playlist</b>

            <br><b>Scenario:</b> You found a lecture series with 100 videos and want to extract all key claims.

            <br><br><b>Your approach:</b>
            <br>1. Create throwaway Google account (5 minutes)
            <br>2. Export cookies following steps above (5 minutes)
            <br>3. Configure app with cookies and rate limiting (2 minutes)
            <br>4. Paste the playlist URL in Transcribe tab
            <br>5. Check "Process automatically through entire pipeline"
            <br>6. Click Start → go to bed 😴
            <br>7. Wake up → 100 videos transcribed, analyzed, and searchable in Review tab

            <br><br><b>What you get:</b>
            <br>• All videos downloaded with 3-5 minute delays (total: 5-8 hours)
            <br>• All transcripts with speaker labels
            <br>• All claims extracted and scored
            <br>• Searchable database in Review tab
            <br>• Can now find "What did the professor say about machine learning?" across all 100 lectures in seconds

            <br><br><b>Total time investment:</b>
            <br>• Your time: 12 minutes of setup
            <br>• Computer time: ~10-12 hours running unattended
            <br>• Result: 100 hours of lectures → searchable knowledge base

            <br><br><b style="color: #007acc;">📝 Summary Checklist</b>
            <br>✅ Created throwaway Google account (not main account!)
            <br>✅ Exported cookies in incognito window from throwaway account only
            <br>✅ Saved cookies.txt file somewhere accessible
            <br>✅ Enabled cookie authentication in Transcribe tab
            <br>✅ Selected cookie file using Browse button
            <br>✅ Set rate limiting to 3-5 minute delays
            <br>✅ Checked "Disable proxies when cookies enabled"
            <br>✅ Ready to paste YouTube URLs and start bulk downloads!

            <br><br><b>🎓 Remember:</b> This setup is one-time. After initial configuration, you just paste URLs and
            click Start. Cookies last 7-10 days before needing refresh. The system handles everything else automatically!
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
            <br>• <b>First time?</b> Start with one short video/audio file (5-10 min) to see how it works
            <br>• <b>Using YouTube?</b> Remember to set up PacketStream in Settings first
            <br>• <b>Want faster processing?</b> Use cloud models (OpenAI/Anthropic) instead of local Ollama
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
            """
        )

        workflows_text.setWordWrap(True)
        workflows_text.setTextFormat(Qt.TextFormat.RichText)
        workflows_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(workflows_text)
