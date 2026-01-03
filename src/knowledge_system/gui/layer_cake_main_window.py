"""Layer Cake Main Window - New intuitive GUI design.

Two-pane layout with layer cake tiles on left and status boxes on right.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QStatusBar,
    QLabel,
)

from ..database.service import DatabaseService
from ..gui.core.settings_manager import get_gui_settings_manager
from ..gui.components.layer_cake_widget import LayerCakeWidget
from ..gui.components.status_box import LayerLogWidget
from .. import __version__


class LayerCakeMainWindow(QMainWindow):
    """
    Main window with layer cake interface.
    
    Layout:
    - Left pane (60%): Layer cake with 6 tiles
    - Right pane (40%): Status boxes showing logs
    - Top: macOS-style traffic lights + search/settings icons
    - Bottom: Status bar with version info
    """
    
    def __init__(self):
        super().__init__()
        
        # Initialize services
        self.gui_settings = get_gui_settings_manager()
        self.db_service = DatabaseService()
        
        # Set window properties
        self.setWindowTitle("Skip the Podcast")
        self.setMinimumSize(1200, 800)
        
        # Restore saved geometry or use default
        geometry = self.gui_settings.get_window_geometry()
        if geometry:
            self.setGeometry(
                geometry['x'],
                geometry['y'],
                geometry['width'],
                geometry['height']
            )
        else:
            # Default size and center on screen
            self.resize(1400, 900)
            self._center_on_screen()
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Setup UI
        self._setup_ui()
        
        # Load initial state
        self._load_initial_state()
    
    def _setup_ui(self):
        """Setup the main UI with Settings spanning full width."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 0)
        layout.setSpacing(8)
        
        # === TOP: Full-width Settings bar ===
        from ..gui.components.settings_tile import SettingsHelpContactTile
        from ..gui.components.expansion_panel import SimpleExpansionPanel
        from ..gui.components.settings_panel_content import SettingsPanelContent
        
        self.settings_tile = SettingsHelpContactTile(color='#4A4A4A')
        self.settings_tile.settings_clicked.connect(self._toggle_settings_panel)
        layout.addWidget(self.settings_tile)
        
        # Settings expansion panel (full width)
        self.settings_panel = SimpleExpansionPanel('settings', '#4A4A4A')
        self.settings_content = SettingsPanelContent(self.gui_settings)
        self.settings_panel.content_layout.addWidget(self.settings_content)
        self.settings_panel.hide()
        layout.addWidget(self.settings_panel)
        
        # Dummy help_panel for compatibility (hidden)
        self.help_panel = SimpleExpansionPanel('help', '#4A4A4A')
        self.help_panel.hide()
        
        # === BOTTOM: Horizontal splitter with tiles and status boxes ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Style splitter to have 8px handle
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2d2d30;
                width: 8px;
            }
            QSplitter::handle:hover {
                background-color: #3c3c3c;
            }
        """)
        splitter.setHandleWidth(8)
        
        # Left pane: Layer cake widget (60%) - WITHOUT settings
        self.layer_cake = LayerCakeWidget(self.gui_settings, self.db_service, include_settings=False)
        self.layer_cake.start_processing.connect(self._handle_start_processing)
        splitter.addWidget(self.layer_cake)
        
        # Right pane: Status boxes (40%) - WITHOUT settings
        tile_colors = self.layer_cake.get_tile_colors()
        # Remove settings from colors for status boxes
        status_colors = {k: v for k, v in tile_colors.items() if k != 'settings'}
        self.log_widget = LayerLogWidget(status_colors)
        splitter.addWidget(self.log_widget)
        
        # Connect expansion changes to maintain vertical alignment
        self.layer_cake.expansion_changed.connect(self._handle_expansion_changed)
        
        # Set splitter proportions (60/40)
        splitter.setSizes([840, 560])
        splitter.setChildrenCollapsible(False)
        
        layout.addWidget(splitter, 1)  # Stretch to fill
        
        # Status bar
        self._setup_status_bar()
    
    def _toggle_settings_panel(self):
        """Toggle settings expansion panel."""
        if self.settings_panel.isVisible() and self.settings_panel.height() > 0:
            self.settings_panel.roll_up()
        else:
            # Collapse help if open
            if self.help_panel.isVisible():
                self.help_panel.roll_up()
            self.settings_panel.show()
            self.settings_panel.unroll()
    
    def _toggle_help_panel(self):
        """Toggle help expansion panel."""
        if self.help_panel.isVisible() and self.help_panel.height() > 0:
            self.help_panel.roll_up()
        else:
            # Collapse settings if open
            if self.settings_panel.isVisible():
                self.settings_panel.roll_up()
            self.help_panel.show()
            self.help_panel.unroll()
    
    def _open_contact(self):
        """Open contact page in browser."""
        import webbrowser
        webbrowser.open("https://skipthepodcast.com/contact")
    
    def _setup_status_bar(self):
        """Setup status bar with version info."""
        from datetime import datetime
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Build date
        build_date = datetime.now().strftime("%Y-%m-%d")
        
        # Version label (right side)
        version_msg = f"Skip the Podcast v{__version__} • Built: {build_date}"
        version_label = QLabel(version_msg)
        version_label.setStyleSheet("color: #666;")
        self.status_bar.addPermanentWidget(version_label)
        
        # Status message (left side)
        self.status_bar.showMessage("Ready")
    
    def _apply_dark_theme(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d30;
            }
            QStatusBar {
                background-color: #2d2d30;
                color: #E0E0E0;
                border-top: 1px solid #3c3c3c;
            }
        """)
    
    def _center_on_screen(self):
        """Center window on screen."""
        from PyQt6.QtGui import QGuiApplication
        
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
    
    def _load_initial_state(self):
        """Load initial state and show welcome message."""
        # Check if first time user
        first_time = not self.gui_settings.get_value(
            "Settings",
            "setup_complete",
            False
        )
        
        if first_time:
            # Show welcome message in status bar
            self.status_bar.showMessage(
                "👋 Welcome! Click Settings (top tile) to configure API keys and models.",
                10000  # 10 seconds
            )
    
    def _handle_expansion_changed(self, tile_id: str, height: int):
        """
        Handle expansion panel change - adjust right pane spacer.
        
        Args:
            tile_id: ID of tile whose panel expanded/collapsed
            height: New height (300 for expanded, 0 for collapsed)
        """
        self.log_widget.set_expansion_spacer(tile_id, height)
    
    def _handle_start_processing(
        self,
        tile_id: str,
        files: list[str],
        options: dict
    ):
        """Handle start processing signal from layer cake widget."""
        # Log to appropriate status box
        box_id = tile_id  # tile_id matches box_id
        
        self.log_widget.append_log(
            box_id,
            f"Starting processing for {len(files)} file(s)..."
        )
        
        # Set status bar message
        self.status_bar.showMessage(
            f"Processing {len(files)} file(s) from {tile_id}..."
        )
        
        # Log files and options
        for i, file in enumerate(files, 1):
            self.log_widget.append_log(box_id, f"File {i}: {file}")
        
        self.log_widget.append_log(
            box_id,
            f"Options: Claims={options['create_claims']}, "
            f"Summary={options['create_summary']}, "
            f"Upload={options['upload']}"
        )
        
        # Route to appropriate orchestrator based on tile_id
        try:
            if tile_id == 'sources':
                self._process_sources(files, options)
            elif tile_id == 'transcripts':
                self._process_transcripts(files, options)
            else:
                self.log_widget.append_log(box_id, f"Unknown tile_id: {tile_id}")
        except Exception as e:
            self.log_widget.append_log(box_id, f"ERROR: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
    
    def _process_sources(self, files: list[str], options: dict):
        """Process source files (YouTube, MP3, PDF, etc.)."""
        from ..services.transcript_acquisition_orchestrator import TranscriptAcquisitionOrchestrator
        
        self.log_widget.append_log('sources', "Initializing TranscriptAcquisitionOrchestrator...")
        
        # TODO: Wire up progress callbacks to update status boxes
        # For now, just log that we would call the orchestrator
        self.log_widget.append_log(
            'sources',
            "TranscriptAcquisitionOrchestrator would process files here"
        )
        
        # If create_claims or create_summary, continue to next stages
        if options['create_claims']:
            self.log_widget.append_log('claims', "Would extract claims after transcription")
        if options['create_summary']:
            self.log_widget.append_log('summaries', "Would create summary after transcription")
        if options['upload']:
            self.log_widget.append_log('cloud', "Would upload to GetReceipts after processing")
    
    def _process_transcripts(self, files: list[str], options: dict):
        """Process existing transcript files."""
        from ..core.system2_orchestrator import System2Orchestrator
        
        self.log_widget.append_log('transcripts', "Initializing System2Orchestrator...")
        
        # TODO: Wire up progress callbacks
        self.log_widget.append_log(
            'transcripts',
            "System2Orchestrator would process transcripts here"
        )
        
        if options['create_claims']:
            self.log_widget.append_log('claims', "Would extract claims from transcripts")
        if options['create_summary']:
            self.log_widget.append_log('summaries', "Would create summary from transcripts")
        if options['upload']:
            self.log_widget.append_log('cloud', "Would upload to GetReceipts")
    
    def closeEvent(self, event):
        """Save window geometry on close."""
        # Save window geometry
        geometry = self.geometry()
        self.gui_settings.set_window_geometry(
            geometry.x(),
            geometry.y(),
            geometry.width(),
            geometry.height()
        )
        
        # Save all settings
        self.gui_settings.save()
        
        # Accept close event
        event.accept()


def main():
    """Entry point for layer cake GUI."""
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Skip the Podcast")
    app.setOrganizationName("SkipThePodcast")
    app.setOrganizationDomain("skipthepodcast.com")
    
    # Create and show main window
    window = LayerCakeMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

