"""LayerCakeWidget - Main left pane managing all tiles and expansion panels.

Coordinates tile clicks, expansion panel display, and file accumulation.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from .layer_tile import LayerTile
from .droppable_tile import DroppableTile
from .sources_tile import SourcesTile
from .expansion_panel import FileListExpansionPanel, SimpleExpansionPanel
from .settings_tile import SettingsHelpContactTile
from .settings_panel_content import SettingsPanelContent, HelpPanelContent
from .claims_panel_content import ClaimsPanelContent, SummariesPanelContent, CloudPanelContent
from .color_customization_dialog import ColorCustomizationDialog


# Glassmorphism color palette - muted, sophisticated, translucent feel
DEFAULT_COLORS = {
    'settings': '#3D3D3D',    # Dark charcoal
    'sources': '#5B5FC7',     # Muted indigo
    'transcripts': '#C68B00', # Deep gold/amber
    'claims': '#2D9D78',      # Muted teal-green
    'summaries': '#B5568C',   # Muted rose
    'cloud': '#4A7FC1',       # Steel blue
}


class LayerCakeWidget(QWidget):
    """
    Main left pane widget managing all 6 tiles and their expansion panels.
    
    Tiles are arranged top to bottom:
    1. Settings/Help/Contact (gray) - TOP
    2. Sources (purple)
    3. Transcripts (orange)
    4. Claims (green)
    5. Summaries (pink)
    6. Cloud (blue) - BOTTOM
    
    Features:
    - Click tile → expansion panel unrolls below
    - Only one panel open at a time
    - Drag files onto Sources/Transcripts tiles
    - File accumulation before processing
    - Settings persistence
    """
    
    # Signals
    start_processing = pyqtSignal(str, list, dict)  # tile_id, files, options
    expansion_changed = pyqtSignal(str, int)  # tile_id, height (0 or 300)
    
    def __init__(self, gui_settings=None, db_service=None, include_settings=True, parent=None):
        """
        Initialize layer cake widget.
        
        Args:
            gui_settings: GUISettingsManager instance
            db_service: DatabaseService instance
            include_settings: Whether to include Settings tile (False when Settings is in main window)
        """
        super().__init__(parent)
        
        from ...gui.core.settings_manager import get_gui_settings_manager
        from ...database.service import DatabaseService
        
        self.gui_settings = gui_settings or get_gui_settings_manager()
        self.db_service = db_service or DatabaseService()
        self.include_settings = include_settings
        
        # Load saved colors or use defaults
        self.tile_colors = self.gui_settings.get_value(
            "Appearance",
            "tile_colors",
            DEFAULT_COLORS
        )
        
        # Track active tile/panel
        self.active_tile_id = None
        self.active_panel = None
        
        # Track active sub-tile for Settings/Help/Contact
        self.active_subtile = None  # 'settings', 'help', or 'contact'
        
        # File accumulation for Sources and Transcripts
        self.accumulated_files = {
            'sources': [],
            'transcripts': []
        }
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the layer cake UI."""
        # Main layout with spacing for expansion panels
        self.layout = QVBoxLayout(self)
        
        # No margins if Settings is handled by main window
        if self.include_settings:
            self.layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.layout.setSpacing(8)
        
        # Create tiles and panels (top to bottom)
        self._create_tiles()
        
        # Add stretch at bottom to push tiles to top
        self.layout.addStretch()
    
    def _create_tiles(self):
        """Create tiles with their expansion panels."""
        
        # 1. SETTINGS/HELP/CONTACT TILE (top) - Only if include_settings=True
        if self.include_settings:
            self.settings_tile = SettingsHelpContactTile(self.tile_colors['settings'])
            self.settings_tile.settings_clicked.connect(lambda: self._handle_subtile_click('settings'))
            self.settings_tile.help_clicked.connect(lambda: self._handle_subtile_click('help'))
            self.settings_tile.contact_clicked.connect(self._handle_contact_click)
            self.layout.addWidget(self.settings_tile)
            
            # Settings expansion panel with content
            self.settings_panel = SimpleExpansionPanel(
                'settings',
                self.tile_colors['settings']
            )
            self.settings_content = SettingsPanelContent(self.gui_settings)
            self.settings_content.color_customization_requested.connect(self._show_color_dialog)
            self.settings_panel.content_layout.addWidget(self.settings_content)
            self.settings_panel.hide()
            self.layout.addWidget(self.settings_panel)
            
            # Help expansion panel with content
            self.help_panel = SimpleExpansionPanel(
                'help',
                self.tile_colors['settings']
            )
            self.help_content = HelpPanelContent()
            self.help_panel.content_layout.addWidget(self.help_content)
            self.help_panel.hide()
            self.layout.addWidget(self.help_panel)
        else:
            # Initialize as None when not included
            self.settings_tile = None
            self.settings_panel = None
            self.settings_content = None
            self.help_panel = None
            self.help_content = None
        
        # 2. SOURCES TILE (droppable)
        self.sources_tile = SourcesTile(self.tile_colors['sources'])
        self.sources_tile.clicked.connect(self._handle_tile_click)
        self.sources_tile.files_dropped.connect(self._handle_files_dropped)
        self.layout.addWidget(self.sources_tile)
        
        # Sources expansion panel (with file list + Start button)
        self.sources_panel = FileListExpansionPanel(
            'sources',
            self.tile_colors['sources']
        )
        self.sources_panel.start_processing.connect(self._handle_start_processing)
        self.sources_panel.hide()
        self.layout.addWidget(self.sources_panel)
        
        # 3. TRANSCRIPTS TILE (droppable)
        self.transcripts_tile = DroppableTile(
            'transcripts',
            self.tile_colors['transcripts'],
            '📝',
            'I HAVE TRANSCRIPTS',
            accepted_extensions=['.txt', '.json', '.srt', '.vtt']
        )
        self.transcripts_tile.clicked.connect(self._handle_tile_click)
        self.transcripts_tile.files_dropped.connect(self._handle_files_dropped)
        self.layout.addWidget(self.transcripts_tile)
        
        # Transcripts expansion panel
        self.transcripts_panel = FileListExpansionPanel(
            'transcripts',
            self.tile_colors['transcripts']
        )
        self.transcripts_panel.start_processing.connect(self._handle_start_processing)
        self.transcripts_panel.hide()
        self.layout.addWidget(self.transcripts_panel)
        
        # 4. CLAIMS TILE
        self.claims_tile = LayerTile(
            'claims',
            self.tile_colors['claims'],
            '💡',
            'Review CLAIMS'
        )
        self.claims_tile.clicked.connect(self._handle_tile_click)
        self.layout.addWidget(self.claims_tile)
        
        # Claims expansion panel with content
        self.claims_panel = SimpleExpansionPanel(
            'claims',
            self.tile_colors['claims']
        )
        self.claims_content = ClaimsPanelContent(self.db_service)
        self.claims_panel.content_layout.addWidget(self.claims_content)
        self.claims_panel.hide()
        self.layout.addWidget(self.claims_panel)
        
        # 5. SUMMARIES TILE
        self.summaries_tile = LayerTile(
            'summaries',
            self.tile_colors['summaries'],
            '📄',
            'Review SUMMARIES'
        )
        self.summaries_tile.clicked.connect(self._handle_tile_click)
        self.layout.addWidget(self.summaries_tile)
        
        # Summaries expansion panel with content
        self.summaries_panel = SimpleExpansionPanel(
            'summaries',
            self.tile_colors['summaries']
        )
        self.summaries_content = SummariesPanelContent(self.db_service)
        self.summaries_panel.content_layout.addWidget(self.summaries_content)
        self.summaries_panel.hide()
        self.layout.addWidget(self.summaries_panel)
        
        # 6. CLOUD TILE (bottom)
        self.cloud_tile = LayerTile(
            'cloud',
            self.tile_colors['cloud'],
            '☁️',
            'SkipThePodcast.com'
        )
        self.cloud_tile.clicked.connect(self._handle_tile_click)
        self.layout.addWidget(self.cloud_tile)
        
        # Cloud expansion panel with content
        self.cloud_panel = SimpleExpansionPanel(
            'cloud',
            self.tile_colors['cloud']
        )
        self.cloud_content = CloudPanelContent()
        self.cloud_panel.content_layout.addWidget(self.cloud_content)
        self.cloud_panel.hide()
        self.layout.addWidget(self.cloud_panel)
        
        # Map tile IDs to tiles and panels
        self.tiles = {
            'settings': self.settings_tile,
            'sources': self.sources_tile,
            'transcripts': self.transcripts_tile,
            'claims': self.claims_tile,
            'summaries': self.summaries_tile,
            'cloud': self.cloud_tile,
        }
        
        self.panels = {
            'settings': self.settings_panel,
            'help': self.help_panel,
            'sources': self.sources_panel,
            'transcripts': self.transcripts_panel,
            'claims': self.claims_panel,
            'summaries': self.summaries_panel,
            'cloud': self.cloud_panel,
        }
        
        # Connect each panel's expansion_changed to our signal
        for panel in [self.sources_panel, self.transcripts_panel, 
                      self.claims_panel, self.summaries_panel, self.cloud_panel]:
            if panel:
                panel.expansion_changed.connect(self._forward_expansion_changed)
    
    def _forward_expansion_changed(self, tile_id: str, height: int):
        """Forward panel expansion changes to parent."""
        self.expansion_changed.emit(tile_id, height)
    
    def _handle_tile_click(self, tile_id: str):
        """Handle tile click - toggle expansion panel."""
        # If clicking the active tile, roll up panel
        if self.active_tile_id == tile_id and self.active_panel:
            self.active_panel.roll_up()
            self.active_tile_id = None
            self.active_panel = None
            # Notify parent to collapse spacer on right
            self._notify_expansion_change(tile_id, 0)
            return
        
        # Roll up current panel if any
        if self.active_panel:
            old_tile_id = self.active_tile_id
            self.active_panel.roll_up()
            # Collapse old spacer
            if old_tile_id:
                self._notify_expansion_change(old_tile_id, 0)
        
        # Unroll new panel
        panel = self.panels[tile_id]
        panel.unroll()
        
        self.active_tile_id = tile_id
        self.active_panel = panel
        
        # Notify parent to expand spacer on right (300px)
        self._notify_expansion_change(tile_id, 300)
    
    def _handle_subtile_click(self, subtile_id: str):
        """Handle Settings/Help/Contact sub-tile click."""
        # If clicking the active subtile, roll up panel
        if self.active_subtile == subtile_id and self.active_panel:
            self.active_panel.roll_up()
            self.active_subtile = None
            self.active_panel = None
            self.active_tile_id = None
            # Collapse spacer for settings
            self._notify_expansion_change('settings', 0)
            return
        
        # Roll up current panel if any
        if self.active_panel:
            old_tile = self.active_tile_id
            self.active_panel.roll_up()
            # Collapse old spacer
            if old_tile:
                self._notify_expansion_change(old_tile, 0)
        
        # Unroll appropriate panel
        panel = self.panels[subtile_id]
        panel.unroll()
        
        self.active_subtile = subtile_id
        self.active_tile_id = 'settings'  # Parent tile
        self.active_panel = panel
        
        # Expand spacer for settings (300px)
        self._notify_expansion_change('settings', 300)
    
    def _notify_expansion_change(self, tile_id: str, height: int):
        """
        Notify parent window about expansion panel change via signal.
        
        Args:
            tile_id: ID of tile whose panel expanded/collapsed
            height: New height (300 for expanded, 0 for collapsed)
        """
        # Emit signal for parent to handle
        self.expansion_changed.emit(tile_id, height)
    
    def _handle_contact_click(self):
        """Handle Contact sub-tile click - open browser."""
        import webbrowser
        webbrowser.open("https://skipthepodcast.com/contact")
    
    def _show_color_dialog(self):
        """Show color customization dialog."""
        dialog = ColorCustomizationDialog(self.tile_colors, self)
        
        # Live preview
        dialog.colors_updated.connect(self.update_colors)
        
        if dialog.exec():
            # User clicked Apply - colors already updated via live preview
            pass
        else:
            # User clicked Cancel - dialog already restored original colors
            pass
    
    def _handle_files_dropped(self, tile_id: str, files: list[str]):
        """Handle files dropped on a droppable tile."""
        # Add files to accumulation
        self.accumulated_files[tile_id].extend(files)
        
        # Unroll panel if not already open
        if self.active_tile_id != tile_id:
            self._handle_tile_click(tile_id)
        
        # Add files to panel's file list
        panel = self.panels[tile_id]
        if hasattr(panel, 'add_file'):
            for file in files:
                panel.add_file(file)
        
        # Save to recent files
        for file in files:
            self.gui_settings.add_recent_file(tile_id.capitalize(), file)
    
    def _handle_start_processing(self, tile_id: str, options: dict):
        """Handle Start button click from expansion panel."""
        # Get accumulated files
        files = self.accumulated_files.get(tile_id, [])
        
        if not files:
            # TODO: Show error message
            return
        
        # Save checkbox states
        self.gui_settings.set_value(
            "Processing",
            "create_claims",
            options.get('create_claims', True)
        )
        self.gui_settings.set_value(
            "Processing",
            "create_summary",
            options.get('create_summary', True)
        )
        self.gui_settings.set_value(
            "Processing",
            "upload",
            options.get('upload', True)
        )
        self.gui_settings.save()
        
        # Emit signal for parent to handle
        self.start_processing.emit(tile_id, files, options)
        
        # Clear accumulated files
        self.accumulated_files[tile_id] = []
        
        # Clear panel's file list
        panel = self.panels[tile_id]
        if hasattr(panel, 'clear_files'):
            panel.clear_files()
        
        # Roll up panel
        if self.active_panel:
            self.active_panel.roll_up()
            self.active_panel = None
            self.active_tile_id = None
    
    def update_colors(self, new_colors: dict[str, str]):
        """Update all tile and panel colors."""
        self.tile_colors = new_colors
        
        # Update tiles
        for tile_id, tile in self.tiles.items():
            if tile_id in new_colors:
                tile.set_color(new_colors[tile_id])
        
        # Update panels
        for tile_id, panel in self.panels.items():
            if tile_id in new_colors:
                panel.set_color(new_colors[tile_id])
        
        # Save to settings
        self.gui_settings.set_value("Appearance", "tile_colors", new_colors)
        self.gui_settings.save()
    
    def get_tile_colors(self) -> dict[str, str]:
        """Get current tile colors."""
        return self.tile_colors.copy()

