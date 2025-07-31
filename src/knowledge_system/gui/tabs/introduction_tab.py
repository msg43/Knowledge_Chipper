"""Introduction tab providing comprehensive guidance for new users."""

import subprocess
import sys
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QScrollArea, QWidget, QFrame,
    QTextBrowser, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QDesktopServices
from PyQt6.QtCore import QUrl

from ..components.base_tab import BaseTab
from ...logger import get_logger

logger = get_logger(__name__)


class IntroductionTab(BaseTab):
    """Introduction tab for new users."""
    
    # Signal for tab navigation
    navigate_to_tab = pyqtSignal(str)  # tab_name
    
    def __init__(self, parent=None):
        self.tab_name = "Introduction"
        super().__init__(parent)
        
    def _setup_ui(self):
        """Setup the introduction UI."""
        main_layout = QVBoxLayout(self)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Main content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Welcome header
        self._create_welcome_section(content_layout)
        
        # App overview
        self._create_overview_section(content_layout)
        
        # Quick start guide
        self._create_quick_start_section(content_layout)
        
        # Tab navigation guide
        self._create_tab_guide_section(content_layout)
        
        # Tips and best practices
        self._create_tips_section(content_layout)
        
        # Documentation section
        self._create_documentation_section(content_layout)
        
        # Add stretch to push content to top
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
    def _create_welcome_section(self, parent_layout):
        """Create the welcome header section."""
        # Title
        title_label = QLabel("🎉 Welcome to Knowledge Chipper!")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Your comprehensive knowledge management system")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle_font.setItalic(True)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; margin-bottom: 20px;")
        parent_layout.addWidget(subtitle_label)
        
    def _create_overview_section(self, parent_layout):
        """Create the app overview section."""
        # Section header
        header_label = QLabel("📚 What is Knowledge Chipper?")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)
        
        overview_text = QLabel("""
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
• <b>Smart Model-Aware Chunking:</b> 95% efficiency vs 25% with hardcoded limits
• <b>Real-time Progress Tracking:</b> Accurate ETAs and detailed status updates
• <b>YouTube Integration:</b> Direct video download and processing
• <b>Multiple AI Providers:</b> OpenAI, Anthropic, local models via Ollama
• <b>Batch Processing:</b> Handle multiple files simultaneously
• <b>File Watching:</b> Automatic processing of new files
        """)
        
        overview_text.setWordWrap(True)
        overview_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(overview_text)
        
    def _create_quick_start_section(self, parent_layout):
        """Create the quick start guide section."""
        # Section header
        header_label = QLabel("🚀 Quick Start Guide")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)
        
        quickstart_text = QLabel("""
<b>Get started in 3 simple steps:</b>

<br><br><b>1. Configure API Keys</b> 📁
• Go to the <b>API Keys</b> tab
• Add your OpenAI or Anthropic API key for summarization
• Optionally add HuggingFace token for speaker diarization

<br><br><b>2. Process Your First File</b> 🎵
• Go to the <b>Process Management</b> tab
• Click "Add Files" and select audio/video files
• Choose your AI provider and summarization settings
• Click "Start Processing"

<br><br><b>3. View Your Results</b> 📄
• Transcripts are saved as .txt files
• Summaries are saved as .md files  
• Knowledge maps (MOCs) organize everything
• Use "View Last Report" to see detailed results

<br><br><b>💡 Pro Tip:</b> Start with shorter files (under 30 minutes) to get familiar with the workflow, then scale up to longer content!
        """)
        
        quickstart_text.setWordWrap(True)
        quickstart_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(quickstart_text)
        
    def _create_tab_guide_section(self, parent_layout):
        """Create the tab navigation guide section."""
        # Section header
        header_label = QLabel("🧭 Tab Navigation Guide")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)
        
        tabs_text = QLabel("""
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
• Download videos directly from YouTube URLs
• Process entire playlists or channels
• Automatic metadata extraction and organization

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
        """)
        
        tabs_text.setWordWrap(True)
        tabs_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(tabs_text)
        
    def _create_tips_section(self, parent_layout):
        """Create the tips and best practices section."""
        # Section header
        header_label = QLabel("💡 Tips & Best Practices")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)
        
        tips_text = QLabel("""
<b>🏆 Best Practices for Success:</b>

<br><br><b>File Organization:</b>
• Use descriptive filenames for better organization
• Keep source files in dedicated folders
• Check output directories for generated content

<br><br><b>Performance Optimization:</b>
• Larger Whisper models = better accuracy but slower processing
• GPU acceleration significantly speeds up transcription
• Batch similar files together for efficiency

<br><br><b>AI Model Selection:</b>
• <b>OpenAI GPT-4:</b> Best overall quality, costs per token
• <b>Anthropic Claude:</b> Excellent for analysis, different pricing
• <b>Local Ollama:</b> Free but requires good hardware

<br><br><b>Quality Tips:</b>
• Clear audio = better transcriptions
• Use speaker diarization for multi-speaker content
• Custom prompts improve summary relevance

<br><br><b>🔧 Troubleshooting:</b>
• Check the output log in each tab for detailed information
• Use "View Last Report" buttons to see processing results
• Dry run mode lets you test settings without processing

<br><br><b>🎯 Remember:</b> Knowledge Chipper is designed to handle everything from quick voice memos to multi-hour lectures. Start small and scale up as you get comfortable!
        """)
        
        tips_text.setWordWrap(True)
        tips_text.setTextFormat(Qt.TextFormat.RichText)
        parent_layout.addWidget(tips_text)
        
    def _create_documentation_section(self, parent_layout):
        """Create the documentation section."""
        # Section header
        header_label = QLabel("📚 Documentation & Resources")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-top: 20px; margin-bottom: 10px;")
        parent_layout.addWidget(header_label)
        
        # Documentation group
        doc_group = QGroupBox()
        doc_layout = QVBoxLayout()
        
        # README file section
        readme_section = QLabel("""
<b>📖 Complete Documentation:</b>
<br>• <a href="readme://open">README.md</a> - Full setup guide, troubleshooting, and advanced features
<br>• <a href="changelog://open">CHANGELOG.md</a> - Latest updates and version history
<br>• <a href="contributing://open">CONTRIBUTING.md</a> - Development and contribution guidelines

<br><br><b>🎯 Quick Reference:</b>
<br>• <a href="youtube://setup">YouTube API Setup Guide</a> - Configure YouTube integration
<br>• <a href="performance://guide">Performance Optimization</a> - Get the best results
<br>• <a href="troubleshooting://help">Troubleshooting Guide</a> - Common issues and solutions
        """)
        
        readme_section.setWordWrap(True)
        readme_section.setTextFormat(Qt.TextFormat.RichText)
        readme_section.setOpenExternalLinks(False)  # Handle clicks manually
        readme_section.linkActivated.connect(self._handle_documentation_link)
        readme_section.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 15px;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
            QLabel a {
                color: #007bff;
                text-decoration: none;
            }
            QLabel a:hover {
                color: #0056b3;
                text-decoration: underline;
            }
        """)
        doc_layout.addWidget(readme_section)
        
        doc_group.setLayout(doc_layout)
        parent_layout.addWidget(doc_group)
        
    def _handle_documentation_link(self, link: str):
        """Handle clicks on documentation links."""
        try:
            project_root = Path(__file__).parents[4]  # Go up to Knowledge_Chipper root
            
            if link == "readme://open":
                readme_path = project_root / "README.md"
                if readme_path.exists():
                    # Try to open with default markdown viewer/editor
                    if sys.platform == "darwin":  # macOS
                        subprocess.run(["open", str(readme_path)], check=False)
                    elif sys.platform == "win32":  # Windows
                        subprocess.run(["start", str(readme_path)], shell=True, check=False)
                    else:  # Linux
                        subprocess.run(["xdg-open", str(readme_path)], check=False)
                else:
                    self.show_error("File Not Found", f"README.md not found at {readme_path}")
                    
            elif link == "changelog://open":
                changelog_path = project_root / "CHANGELOG.md"
                if changelog_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(changelog_path)], check=False)
                    elif sys.platform == "win32":
                        subprocess.run(["start", str(changelog_path)], shell=True, check=False)
                    else:
                        subprocess.run(["xdg-open", str(changelog_path)], check=False)
                else:
                    self.show_error("File Not Found", f"CHANGELOG.md not found at {changelog_path}")
                    
            elif link == "contributing://open":
                contributing_path = project_root / "CONTRIBUTING.md"
                if contributing_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(contributing_path)], check=False)
                    elif sys.platform == "win32":
                        subprocess.run(["start", str(contributing_path)], shell=True, check=False)
                    else:
                        subprocess.run(["xdg-open", str(contributing_path)], check=False)
                else:
                    self.show_error("File Not Found", f"CONTRIBUTING.md not found at {contributing_path}")
                    
            elif link == "youtube://setup":
                youtube_setup_path = project_root / "docs" / "YOUTUBE_API_SETUP.md"
                if youtube_setup_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(youtube_setup_path)], check=False)
                    elif sys.platform == "win32":
                        subprocess.run(["start", str(youtube_setup_path)], shell=True, check=False)
                    else:
                        subprocess.run(["xdg-open", str(youtube_setup_path)], check=False)
                else:
                    self.show_error("File Not Found", f"YouTube setup guide not found at {youtube_setup_path}")
                    
            elif link == "performance://guide":
                # Open the README section on performance
                readme_path = project_root / "README.md"
                if readme_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(readme_path)], check=False)
                    elif sys.platform == "win32":
                        subprocess.run(["start", str(readme_path)], shell=True, check=False)
                    else:
                        subprocess.run(["xdg-open", str(readme_path)], check=False)
                else:
                    self.show_error("File Not Found", f"README.md not found at {readme_path}")
                    
            elif link == "troubleshooting://help":
                # Open the README section on troubleshooting
                readme_path = project_root / "README.md"
                if readme_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(readme_path)], check=False)
                    elif sys.platform == "win32":
                        subprocess.run(["start", str(readme_path)], shell=True, check=False)
                    else:
                        subprocess.run(["xdg-open", str(readme_path)], check=False)
                else:
                    self.show_error("File Not Found", f"README.md not found at {readme_path}")
                    
        except Exception as e:
            logger.error(f"Error opening documentation: {e}")
            self.show_error("Error", f"Could not open documentation: {str(e)}")
    
    def _create_navigation_buttons(self, parent_layout):
        """Create quick navigation buttons."""
        nav_group = QGroupBox("🚀 Quick Actions")
        nav_layout = QHBoxLayout()
        
        # API Keys button
        api_keys_btn = QPushButton("🔑 Setup API Keys")
        api_keys_btn.clicked.connect(lambda: self.navigate_to_tab.emit("API Keys"))
        api_keys_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        nav_layout.addWidget(api_keys_btn)
        
        # Process files button
        process_btn = QPushButton("📁 Start Processing Files")
        process_btn.clicked.connect(lambda: self.navigate_to_tab.emit("Process Management"))
        process_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        nav_layout.addWidget(process_btn)
        
        # YouTube button
        youtube_btn = QPushButton("📺 Process YouTube Videos")
        youtube_btn.clicked.connect(lambda: self.navigate_to_tab.emit("YouTube"))
        youtube_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        nav_layout.addWidget(youtube_btn)
        
        nav_group.setLayout(nav_layout)
        parent_layout.addWidget(nav_group)
        
    # Override base class methods since this is an informational tab
    def _get_start_button_text(self) -> str:
        """Return start button text."""
        return "Get Started"
        
    def _start_processing(self):
        """Navigate to the process tab when start is clicked."""
        self.show_info("Welcome!", "Let's start by setting up your API keys, then move to Process Management to begin!")
        self.navigate_to_tab.emit("API Keys")
        
    def _create_action_layout(self):
        """Override to provide custom action layout for intro tab."""
        layout = QHBoxLayout()
        
        # Custom start button that navigates
        self.start_btn = QPushButton("🚀 Get Started Now")
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.start_btn)
        
        layout.addStretch()
        return layout
        
    def _create_output_section(self):
        """Override to provide custom output section."""
        layout = QVBoxLayout()
        
        # Welcome message instead of log output
        welcome_label = QLabel("👋 Ready to transform your content into organized knowledge?")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("""
            QLabel {
                background-color: #e8f5e8;
                padding: 15px;
                border: 1px solid #4caf50;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        layout.addWidget(welcome_label)
        
        return layout 