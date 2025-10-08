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
            <br>• <b>Audio Files:</b> Podcasts, interviews, lectures (MP3, WAV, M4A)
            <br>• <b>Video Files:</b> Local recordings, screen captures (MP4, MOV)
            <br>• <b>Documents:</b> Research papers, articles, reports (PDF, Word, Markdown)
            <br>• <b>RSS Feeds:</b> Automatically monitor and process new episodes

            <br><br><b>🌟 What You Get:</b>
            <br>• <b>Smart Summaries:</b> Not just "what was discussed" but the specific claims being made
            <br>• <b>Speaker Tracking:</b> Know who said what, even in multi-speaker content
            <br>• <b>Searchable Database:</b> Find claims across all your content instantly
            <br>• <b>Quality Scores:</b> Each claim rated for importance, novelty, and confidence
            <br>• <b>Export Options:</b> Markdown, CSV, or integrate with Obsidian vaults

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
            <br>If you want to process YouTube videos (optional):
            <br>• Add your PacketStream credentials in <b>Settings</b> (username and auth key)
            <br>• Skip this if you're only processing local files, PDFs, or RSS feeds

            <br><br><b>Step 3: Process Your First Item</b>
            <br>Navigate through the tabs from left to right:
            <br>1. <b>Transcribe</b> → Add YouTube URL, local file, or document
            <br>2. Check <b>"Process automatically through entire pipeline"</b> for one-click processing
            <br>3. Click <b>Start Transcription</b> and wait for completion
            <br>4. Review results in the <b>Review</b> tab or export from <b>Summarize</b> tab

            <br><br><b>✅ That's it!</b> The system handles transcription, speaker identification, claim extraction,
            scoring, and database storage automatically.

            <br><br><b>💡 Pro Tip:</b> Enable "Check for updates on startup" in Settings to get the latest features
            automatically. Updates are lightning-fast thanks to intelligent component caching.
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

            <br><br><b style="color: #007acc;">5. Review</b> - Your Claims Dashboard (This is Where You Spend Time!)
            <br><b>What you'll do:</b> Browse, search, edit, and export all your extracted claims in one place
            <br><b>The interface:</b> Spreadsheet-style table with color-coded rows
            <br>• <b>Green rows = Tier A:</b> Most important claims (high importance/novelty scores)
            <br>• <b>Blue rows = Tier B:</b> Significant supporting claims
            <br>• <b>Red rows = Tier C:</b> Background details and context
            <br><b>Key features:</b>
            <br>• <b>Filter by episode:</b> See claims from a specific video/podcast/document
            <br>• <b>Filter by tier:</b> Show only Tier A to see the "best of the best"
            <br>• <b>Filter by type:</b> Show only factual claims, or causal claims, etc.
            <br>• <b>Search text:</b> Find claims containing specific words or topics
            <br>• <b>Sort by scores:</b> Find highest importance, novelty, or confidence claims
            <br>• <b>Edit anything:</b> Click a claim to edit text, adjust scores, change tier or type
            <br>• <b>Real-time save:</b> Changes save to database immediately (or batch save if you prefer)
            <br><b>Practical uses:</b>
            <br>• Find all claims about "machine learning" across 100 podcast episodes
            <br>• Export Tier A claims from 10 research papers for your literature review
            <br>• Quality check: review AI's work and fix any mistakes
            <br>• Share insights: export filtered claims to CSV → paste into your notes or reports
            <br><b>Export options:</b> CSV (works in Excel, Google Sheets, Notion, Airtable)

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
            <br>• Results saved to database → view anytime in Review tab
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
            <br><b>When to revisit:</b> To install new models, update the app, or change API keys
            """
        )

        tabs_text.setWordWrap(True)
        tabs_text.setTextFormat(Qt.TextFormat.RichText)
        tabs_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(tabs_text)

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
            <br>5. When done, open <b>Review</b> tab
            <br>6. Click the <b>Tier filter dropdown</b> → select "A" to show only the most important claims
            <br>7. You'll see 10-20 green-highlighted rows with the key insights
            <br>8. Click any claim to read the full text and see its scores
            <br>9. Optional: Export these Tier A claims to CSV to paste into your notes
            <br><br><b>What you'll see:</b> Claims like "The guest argues that AI regulation should prioritize safety over
            innovation (Importance: 9/10, Novelty: 7/10)" - the essence of 2 hours distilled into a few minutes of reading.

            <br><br><b>Example 2: "I downloaded 50 podcast episodes and need summaries of all of them"</b>
            <br><br>1. Put all MP3 files in one folder
            <br>2. Open <b>Transcribe</b> tab → click "Select Folder" and choose that folder
            <br>3. Check <b>"Process automatically"</b> and <b>"Enable Speaker Diarization"</b>
            <br>4. Click <b>Start Transcription</b> → the app processes all 50 files (this will take a while!)
            <br>5. Go get lunch or do other work 🍔 (expect 2-4 hours for 50 episodes depending on your AI setup)
            <br>6. Come back → open <b>Review</b> tab
            <br>7. Use the <b>Episode filter</b> dropdown to browse individual episodes, or leave it on "All"
            <br>8. Use the <b>Search box</b> → type "climate change" to find all claims mentioning that topic across
            all 50 episodes
            <br>9. Filter to <b>Tier A</b> and <b>sort by Importance</b> to see the most critical insights across the
            entire series
            <br>10. Export the filtered results to CSV for your research database
            <br><br><b>Result:</b> Instead of 50+ hours of listening, you have a searchable database where you can
            find any topic in seconds.

            <br><br><b>Example 3: "I have a research paper (PDF) and need to extract the key findings"</b>
            <br><br>1. Open <b>Transcribe</b> tab → drag and drop your PDF
            <br>2. Check <b>"Process automatically"</b>
            <br>3. Click <b>Start Transcription</b> (yes, same button for PDFs!)
            <br>4. Wait for processing to finish
            <br>5. Open <b>Review</b> tab → filter to show factual claims only
            <br>6. Export to CSV to paste into your literature review spreadsheet
            <br><br><b>What you'll get:</b> Every significant claim from the paper, scored and categorized,
            ready to cite or compare with other papers.

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
            <br>• Results appear in Review tab database
            <br>• You get a notification (optional in Settings)
            <br><br><b>Your Weekly Routine:</b>
            <br>• Open <b>Review</b> tab → filter to claims from the last 7 days
            <br>• Scan Tier A claims to catch the most important insights
            <br>• Search for topics you're tracking across all episodes
            <br><br><b>Perfect for:</b> News podcasts, industry updates, or educational series - stay current without
            manual processing.

            <br><br><b>Example 5: "I recorded a meeting and need to know who said what"</b>
            <br><br>1. Open <b>Transcribe</b> tab → drag in your meeting recording (MP4, MOV, etc.)
            <br>2. Make sure <b>"Enable Speaker Diarization"</b> is checked
            <br>3. Don't check auto-process this time (we'll do Summarize manually)
            <br>4. Click <b>Start Transcription</b> and wait for completion
            <br>5. Check the transcript file → speakers labeled as Speaker 0, Speaker 1, etc.
            <br>6. Open <b>Summarize</b> tab → select the transcript
            <br>7. Click <b>Start Analysis</b> to extract claims
            <br>8. Open <b>Review</b> tab → see which speaker made which claims
            <br><br><b>Bonus:</b> Export the claims with speaker labels to share meeting notes with your team.

            <br><br><b>💡 Quick Tips for Success:</b>
            <br>• <b>First time?</b> Start with one short video/audio file (5-10 min) to see how it works
            <br>• <b>Using YouTube?</b> Remember to set up PacketStream in Settings first
            <br>• <b>Want faster processing?</b> Use cloud models (OpenAI/Anthropic) instead of local Ollama
            <br>• <b>Understanding the scores:</b> Importance = how significant, Novelty = how unique/surprising,
            Confidence = how reliable
            <br>• <b>Low on disk space?</b> The Review tab is your database - you can delete transcript files after processing
            <br>• <b>Finding too many low-value claims?</b> Filter to Tier A only in Review tab to see just the best stuff
            <br>• <b>Need claims in another app?</b> Export CSV from Review tab → works in Excel, Notion, Airtable, etc.
            <br>• <b>Want specialized extraction?</b> Edit prompts in Prompts tab (e.g., focus on statistics, prioritize
            medical claims, extract business metrics)
            <br>• <b>Experiment with models:</b> In Summarize tab, try different Miner/Flagship combinations - larger models
            = better quality but slower
            <br>• <b>Monitor vs Manual:</b> Use Monitor for ongoing series (podcasts, courses), use Transcribe for one-off processing
            """
        )

        workflows_text.setWordWrap(True)
        workflows_text.setTextFormat(Qt.TextFormat.RichText)
        workflows_text.setStyleSheet("line-height: 1.4;")
        parent_layout.addWidget(workflows_text)
