"""Introduction tab providing comprehensive guidance for new users."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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

        # Documentation section
        self._create_documentation_section(content_layout)

        # Add stretch to push content to top
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def _create_overview_section(self, parent_layout: Any) -> None:
        """Create the app overview section."""
        # Section header
        header_label = QLabel("📚 What is Skipthepodcast.com?")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        overview_text = QLabel(
            """
            <b>Skipthepodcast.com transforms your YouTube videos, RSS Feeds, and Documents into CLAIMS.</b>

            <br><br>What are claims? Claims are the carefully sourced, atomized statements that make up the heart of any informative video or document. They form the backbone of a world class summary. Not just an overview of what was discussed, but a point by point inventory of the most novel, important, controversial insightful views of the source.

            <br><br><b>⚡ What it does:</b>
            <br>📹 <b>Transcribes</b> → Videos (YouTube or local), audio files (RSS feeds or local files), and documents
            <br>📝 <b>Summarizes</b> → Creates summaries unlike any you have ever seen. Highly intelligent summaries using the most cutting edge AI strategies
            <br>🗺️ <b>Organizes</b> → Generates knowledge maps and connections
            <br>🔍 <b>Collaborates</b> → This data can go out in multiple formats, including to Obsidian vaults or to our Skipthepodcast.com website, where you can share your insight with others

            <br><br><b>🚀 Key Features:</b>
            <br>• <b>One-click YouTube Integration:</b> Enter a URL or a Playlist URL with 5000 videos in it and we do the rest!
            <br>• <b>Speaker Diarization:</b> Identify different speakers in multi-speaker content
            <br>• <b>Local and Cloud AI Options:</b> Highly granular control over the AI models you use for each step of the process, including OpenAI, Anthropic, local models via Ollama
            <br>• <b>Batch Processing:</b> Handle thousands of files simultaneously
            <br>• <b>File Watching:</b> Automatic processing of new files
            """
        )

        overview_text.setWordWrap(True)
        overview_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(overview_text)

    def _create_quick_start_section(self, parent_layout: Any) -> None:
        """Create the quick start guide section."""
        # Section header
        header_label = QLabel("🚀 Quick Start Guide")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        quickstart_text = QLabel(
            """
            <b>Get started in two simple steps:</b>

            <br><br><b>1. Decide if you want to access YouTube videos for summarization.</b>
            <br>• If so, go to the <b>Settings</b> tab and add your Bright Data API key
            <br>• If not, you can still use the app to summarize local audio and video files and RSS feeds and documents

            <br><br><b>2. Decide if you want to use cloud or local AI models.</b>
            <br>• For Local, just follow the prompts in the app to install Ollama (and maybe get a HuggingFace token if you want to use certain local models)
            <br>• For Cloud, go to Settings and add your OpenAI or Anthropic API key

            <br><br><b>THAT'S IT! You are ready to go.</b>

            <br><br><b>3. Just work your way through the tabs in order left to right.</b>
            <br>For example, if you want to summarize a YouTube video, you would go to the <b>Cloud Transcription</b> tab, enter the URL, and click "Extract Transcripts".
            <br>If you prefer to summarize a local video, you would go to the <b>Local Transcription</b> tab, select the audio or video file or text document, and click "Extract Transcripts".
            <br>Either way, you will get a .md file with the transcript, a nice thumbnail, and a bunch of metadata.

            <br><br>Then you would go to the <b>Summarization</b> tab, select the .md file with the transcript, and click "Start Summarization".
            <br>The summary can be saved in a variety of formats both in separate files or inline with Obsidian .md files
            """
        )

        quickstart_text.setWordWrap(True)
        quickstart_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(quickstart_text)

    def _create_tab_guide_section(self, parent_layout: Any) -> None:
        """Create the advanced features section."""
        # Section header
        header_label = QLabel("🔧 Advanced Features")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        tabs_text = QLabel(
            """
            <b>Advanced Features Tabs:</b>

            <br><br><b>🔍 Claim Search</b> - Search for claims across all processed content

            <br><br><b>👁️ File Watcher</b> - Automated processing
            <br>• Set up folders to watch for new files
            <br>• Automatically process files as they're added
            <br>• Perfect for ongoing projects or regular content

            <br><br><b>🎙️ Speaker Attribution</b> - Speaker identification
            <br>• Identify the speakers in the transcript
            <br>• Assign names to the speakers
            <br>• The app will learn from your corrections and improve over time

            <br><br><b>✏️ Summary Cleanup</b> - Review and edit summaries, claims, and entities post-generation

            <br><br><b>☁️ Cloud Uploads</b> - Upload claims to the cloud
            <br>• Upload claims to the cloud for sharing and collaboration
            """
        )

        tabs_text.setWordWrap(True)
        tabs_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(tabs_text)

    def _create_documentation_section(self, parent_layout: Any) -> None:
        """Create the documentation section."""
        # Section header
        header_label = QLabel("📚 Documentation & Resources")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        # Documentation links in main text
        doc_text = QLabel(
            """
            <b>📖 Complete Documentation:</b>
            <br>• <a href="readme://open">README.md</a> - Full setup guide, troubleshooting, and advanced features
            <br>• <a href="changelog://open">CHANGELOG.md</a> - Latest updates and version history
            <br>• <a href="contributing://open">CONTRIBUTING.md</a> - Development and contribution guidelines

            <br><br><b>🎯 Quick Reference:</b>
            <br>• <a href="youtube://setup">YouTube API Setup Guide</a> - Configure YouTube integration
            <br>• <a href="performance://guide">Performance Optimization</a> - Get the best results
            <br>• <a href="troubleshooting://help">Troubleshooting Guide</a> - Common issues and solutions
            """
        )

        doc_text.setWordWrap(True)
        doc_text.setTextFormat(Qt.TextFormat.RichText)
        doc_text.setOpenExternalLinks(False)  # Handle clicks manually
        doc_text.linkActivated.connect(self._handle_documentation_link)
        parent_layout.addWidget(doc_text)

    def _handle_documentation_link(self, link: str) -> None:
        """Handle clicks on documentation links."""
        try:
            project_root = Path(__file__).parents[4]  # Go up to Knowledge_Chipper root

            if link == "readme://open":
                readme_path = project_root / "README.md"
                self.async_open_file(str(readme_path), "README.md")

            elif link == "changelog://open":
                changelog_path = project_root / "CHANGELOG.md"
                self.async_open_file(str(changelog_path), "CHANGELOG.md")

            elif link == "contributing://open":
                contributing_path = project_root / "CONTRIBUTING.md"
                self.async_open_file(str(contributing_path), "CONTRIBUTING.md")

            elif link == "youtube://setup":
                youtube_setup_path = project_root / "docs" / "YOUTUBE_API_SETUP.md"
                self.async_open_file(str(youtube_setup_path), "YouTube API Setup Guide")

            elif link == "performance://guide":
                # Open the README section on performance
                readme_path = project_root / "README.md"
                self.async_open_file(str(readme_path), "Performance Guide (README.md)")

            elif link == "troubleshooting://help":
                # Open the README section on troubleshooting
                readme_path = project_root / "README.md"
                self.async_open_file(
                    str(readme_path), "Troubleshooting Guide (README.md)"
                )

        except Exception as e:
            logger.error(f"Error opening documentation: {e}")
            self.show_error("Error", f"Could not open documentation: {str(e)}")

    # Override base class methods since this is an informational tab
    def _get_start_button_text(self) -> str:
        """Return start button text."""
        return "Get Started"

    def _start_processing(self) -> None:
        """Navigate to the process tab when start is clicked."""
        self.show_info(
            "Welcome!",
            "Let's start by configuring your API Keys, then move to Process Management to begin!",
        )
        self.navigate_to_tab.emit("API Keys")
