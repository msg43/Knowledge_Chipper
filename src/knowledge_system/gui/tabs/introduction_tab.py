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
        header_label = QLabel("📚 What is Knowledge Chipper?")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        overview_text = QLabel(
            """
            <b>Knowledge Chipper transforms your media content into organized, searchable knowledge.</b>

<br><br><b>🎯 Perfect for:</b>
• Researchers processing interview recordings
• Students transcribing lectures and creating study materials
• Content creators organizing video libraries
• Professionals building knowledge bases from meetings

<br><br><b>⚡ What it does:</b>
<br>📹 <b>Transcribes</b> → Videos, audio files, and documents using advanced AI
<br>📝 <b>Summarizes</b> → Creates intelligent summaries with smart chunking
<br>🗺️ <b>Organizes</b> → Generates knowledge maps and connections
<br>🔍 <b>Makes Searchable</b> → Everything becomes easily findable

<br><br><b>🚀 Key Features:</b>
<br>• <b>Smart Model-Aware Chunking:</b> 95% efficiency vs 25% with hardcoded limits
<br>• <b>Real-time Progress Tracking:</b> Accurate ETAs and detailed status updates
<br>• <b>YouTube Integration:</b> Direct video download and processing with proxy support
<br>• <b>Speaker Diarization:</b> Identify different speakers in multi-speaker content
<br>• <b>Multiple AI Providers:</b> OpenAI, Anthropic, local models via Ollama
<br>• <b>Batch Processing:</b> Handle multiple files simultaneously
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
            <b>Get started in 4 simple steps:</b>

<br><br><b>1. Configure API Keys</b> 🔑
• Go to the <b>API Keys</b> tab
• Add your OpenAI or Anthropic API key for summarization
• For YouTube: Add WebShare proxy credentials (required)
• For speaker diarization: Add HuggingFace token (optional)

<br><br><b>2. Extract YouTube metadata and full transcript with optional diarization</b> 📺
• Go to the <b>Extraction</b> tab
• Enter YouTube URLs or RSS feeds, or upload a file with URLs
• Enable speaker diarization for multi-speaker content
• Click "Extract Transcripts"

<br><br><b>3. Summarize YouTube transcript or any other document using advanced AI techniques</b> 📝
• Go to the <b>Summarization</b> tab
• Upload your transcripts or other documents
• Choose your AI provider and custom prompts
• Click "Start Summarization"

<br><br><b>4. View your results, which can be saved in a variety of formats both in separate files or inline with Obsidian .md files</b> 📄
• Transcripts are saved as .txt files
• Summaries are saved as .md files with YAML frontmatter
• Knowledge maps (MOCs) organize everything
• Output supports Obsidian integration
• Use "View Last Report" to see detailed results

<br><br><b>💡 Pro Tip:</b> Start with shorter files (under 30 minutes) to get familiar with the workflow, then scale up to longer content!
        """
        )

        quickstart_text.setWordWrap(True)
        quickstart_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(quickstart_text)

    def _create_tab_guide_section(self, parent_layout: Any) -> None:
        """Create the tab navigation guide section."""
        # Section header
        header_label = QLabel("🧭 Tab Navigation Guide")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)

        tabs_text = QLabel(
            """
            <b>Each tab serves a specific purpose:</b>

<br><br><b>📁 Process Management</b> - Your main workspace
• Upload and process multiple files at once
• Configure transcription and summarization settings
• Monitor progress with real-time updates
• Generate knowledge maps (MOCs) from your content

<br><br><b>👁️ File Watcher</b> - Automated processing
• Set up folders to watch for new files
• Automatically process files as they're added
• Perfect for ongoing projects or regular content

<br><br><b>📺 YouTube</b> - Video content processing
• Download videos directly from YouTube URLs or RSS feeds with proxy support
• Process entire playlists or channels automatically
• Speaker diarization for multi-speaker content
• Automatic metadata extraction and organization
• Requires WebShare proxy credentials

<br><br><b>🎙️ Transcription</b> - Audio-to-text conversion
• Advanced Whisper-based transcription
• Multiple model sizes for speed vs accuracy
• GPU acceleration support for faster processing

<br><br><b>📝 Summarization</b> - AI-powered insights
• Create intelligent summaries with custom prompts
• Smart chunking for long content
• Multiple AI providers (OpenAI, Anthropic, Ollama)

<br><br><b>🔑 API Keys</b> - Configuration and setup
• Manage all your API credentials securely
• Test connections and validate keys
• Required for AI-powered features
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
