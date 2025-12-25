"""Unified Review Queue component with table model and view."""

from enum import Enum
from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTableView,
    QWidget,
)


class EntityType(Enum):
    """Types of entities in the review queue."""
    CLAIM = "claim"
    JARGON = "jargon"
    PERSON = "person"
    CONCEPT = "concept"


class ReviewStatus(Enum):
    """Review status for queue items."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# Column indices
COL_SELECTED = 0
COL_TYPE = 1
COL_CONTENT = 2
COL_SOURCE = 3
COL_TIER = 4
COL_IMPORTANCE = 5
COL_STATUS = 6

COLUMN_HEADERS = ["", "Type", "Content", "Source", "Tier", "Importance", "Status"]


class ReviewItem:
    """Data class for a review queue item."""
    
    def __init__(
        self,
        entity_type: EntityType,
        content: str,
        source_title: str,
        source_id: str = "",
        tier: str = "C",
        importance: float = 0.0,
        status: ReviewStatus = ReviewStatus.PENDING,
        raw_data: Optional[dict] = None,
        item_id: Optional[str] = None,
    ):
        self.item_id = item_id  # Database ID for persistence
        self.entity_type = entity_type
        self.content = content
        self.source_title = source_title
        self.source_id = source_id
        self.tier = tier
        self.importance = importance
        self.status = status
        self.is_selected = False
        self.raw_data = raw_data or {}
    
    def get_type_icon(self) -> str:
        """Get emoji icon for entity type."""
        icons = {
            EntityType.CLAIM: "📝",
            EntityType.JARGON: "📖",
            EntityType.PERSON: "👤",
            EntityType.CONCEPT: "💡",
        }
        return icons.get(self.entity_type, "❓")
    
    def get_status_color(self) -> QColor:
        """Get color for status."""
        colors = {
            ReviewStatus.PENDING: QColor("#ffc107"),
            ReviewStatus.ACCEPTED: QColor("#28a745"),
            ReviewStatus.REJECTED: QColor("#dc3545"),
        }
        return colors.get(self.status, QColor("#6c757d"))


class ReviewQueueModel(QAbstractTableModel):
    """
    Table model for unified review queue.
    
    Displays all entity types (claims, jargon, people, concepts) in a single
    table with columns for selection, type, content, source, tier, importance,
    and review status.
    """
    
    selection_changed = pyqtSignal(int)  # Emits count of selected items
    item_status_changed = pyqtSignal()  # Emits when any item status changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[ReviewItem] = []
        self._all_selected = False
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMN_HEADERS)
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        
        item = self._items[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_SELECTED:
                return None  # Checkbox handled by delegate
            elif col == COL_TYPE:
                return f"{item.get_type_icon()} {item.entity_type.value.title()}"
            elif col == COL_CONTENT:
                # Truncate long content
                return item.content[:100] + "..." if len(item.content) > 100 else item.content
            elif col == COL_SOURCE:
                return item.source_title[:40] + "..." if len(item.source_title) > 40 else item.source_title
            elif col == COL_TIER:
                return item.tier
            elif col == COL_IMPORTANCE:
                return f"{item.importance:.0f}"
            elif col == COL_STATUS:
                return item.status.value.title()
        
        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == COL_SELECTED:
                return Qt.CheckState.Checked if item.is_selected else Qt.CheckState.Unchecked
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            if item.status == ReviewStatus.ACCEPTED:
                return QColor("#e8f5e9")  # Light green
            elif item.status == ReviewStatus.REJECTED:
                return QColor("#ffebee")  # Light red
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_STATUS:
                return item.get_status_color()
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (COL_TIER, COL_IMPORTANCE, COL_STATUS):
                return Qt.AlignmentFlag.AlignCenter
        
        elif role == Qt.ItemDataRole.UserRole:
            # Return the full item for detail panel
            return item
        
        return None
    
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.row() >= len(self._items):
            return False
        
        item = self._items[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.CheckStateRole and col == COL_SELECTED:
            item.is_selected = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role])
            self.selection_changed.emit(self.get_selected_count())
            return True
        
        return False
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == COL_SELECTED:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMN_HEADERS[section]
        return None
    
    # Public API
    def clear(self):
        """Clear all items."""
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.selection_changed.emit(0)
    
    def add_item(self, item: ReviewItem):
        """Add a single item."""
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()
    
    def add_items(self, items: list[ReviewItem]):
        """Add multiple items at once."""
        if not items:
            return
        start = len(self._items)
        end = start + len(items) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._items.extend(items)
        self.endInsertRows()
    
    def get_item(self, row: int) -> Optional[ReviewItem]:
        """Get item at row."""
        if 0 <= row < len(self._items):
            return self._items[row]
        return None
    
    def get_all_items(self) -> list[ReviewItem]:
        """Get all items."""
        return self._items.copy()
    
    def get_selected_items(self) -> list[ReviewItem]:
        """Get all selected items."""
        return [item for item in self._items if item.is_selected]
    
    def get_selected_count(self) -> int:
        """Get count of selected items."""
        return sum(1 for item in self._items if item.is_selected)
    
    def get_selected_indices(self) -> list[int]:
        """Get indices of selected items."""
        return [i for i, item in enumerate(self._items) if item.is_selected]
    
    def select_all(self):
        """Select all items."""
        for item in self._items:
            item.is_selected = True
        self.dataChanged.emit(
            self.index(0, COL_SELECTED),
            self.index(len(self._items) - 1, COL_SELECTED),
            [Qt.ItemDataRole.CheckStateRole]
        )
        self.selection_changed.emit(len(self._items))
    
    def deselect_all(self):
        """Deselect all items."""
        for item in self._items:
            item.is_selected = False
        self.dataChanged.emit(
            self.index(0, COL_SELECTED),
            self.index(len(self._items) - 1, COL_SELECTED),
            [Qt.ItemDataRole.CheckStateRole]
        )
        self.selection_changed.emit(0)
    
    def toggle_selection(self, row: int):
        """Toggle selection for a specific row."""
        if 0 <= row < len(self._items):
            self._items[row].is_selected = not self._items[row].is_selected
            index = self.index(row, COL_SELECTED)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.selection_changed.emit(self.get_selected_count())
    
    def set_item_status(self, row: int, status: ReviewStatus):
        """Set status for a specific item."""
        if 0 <= row < len(self._items):
            self._items[row].status = status
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, len(COLUMN_HEADERS) - 1)
            )
            self.item_status_changed.emit()
    
    def set_selected_status(self, status: ReviewStatus):
        """Set status for all selected items."""
        changed = False
        for i, item in enumerate(self._items):
            if item.is_selected:
                item.status = status
                changed = True
        if changed:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, len(COLUMN_HEADERS) - 1)
            )
            self.item_status_changed.emit()
    
    def accept_selected(self):
        """Accept all selected items."""
        self.set_selected_status(ReviewStatus.ACCEPTED)
    
    def reject_selected(self):
        """Reject all selected items."""
        self.set_selected_status(ReviewStatus.REJECTED)
    
    def remove_item_by_id(self, item_id: str):
        """
        Remove an item from the model by its item_id.
        
        Args:
            item_id: The item_id to remove
        """
        for i, item in enumerate(self._items):
            if item.item_id == item_id:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._items.pop(i)
                self.endRemoveRows()
                break
    
    def get_status_counts(self) -> dict[str, int]:
        """Get counts by status."""
        counts = {"pending": 0, "accepted": 0, "rejected": 0}
        for item in self._items:
            counts[item.status.value] += 1
        return counts
    
    def get_type_counts(self) -> dict[str, int]:
        """Get counts by entity type."""
        counts = {"claim": 0, "jargon": 0, "person": 0, "concept": 0}
        for item in self._items:
            counts[item.entity_type.value] += 1
        return counts


class ReviewQueueFilterModel(QSortFilterProxyModel):
    """Filter proxy for the review queue."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._type_filter: Optional[EntityType] = None
        self._status_filter: Optional[ReviewStatus] = None
        self._source_filter: str = ""
        self._search_text: str = ""
        self._tier_filter: str = ""
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model:
            return True
        
        item = model.get_item(source_row)
        if not item:
            return True
        
        # Type filter
        if self._type_filter and item.entity_type != self._type_filter:
            return False
        
        # Status filter
        if self._status_filter and item.status != self._status_filter:
            return False
        
        # Source filter
        if self._source_filter and self._source_filter.lower() not in item.source_title.lower():
            return False
        
        # Tier filter
        if self._tier_filter and item.tier != self._tier_filter:
            return False
        
        # Search text filter
        if self._search_text:
            search_lower = self._search_text.lower()
            if search_lower not in item.content.lower():
                return False
        
        return True
    
    def set_type_filter(self, entity_type: Optional[EntityType]):
        """Set filter by entity type."""
        self._type_filter = entity_type
        self.invalidateFilter()
    
    def set_status_filter(self, status: Optional[ReviewStatus]):
        """Set filter by status."""
        self._status_filter = status
        self.invalidateFilter()
    
    def set_source_filter(self, source: str):
        """Set filter by source title."""
        self._source_filter = source
        self.invalidateFilter()
    
    def set_tier_filter(self, tier: str):
        """Set filter by tier."""
        self._tier_filter = tier
        self.invalidateFilter()
    
    def set_search_text(self, text: str):
        """Set search text filter."""
        self._search_text = text
        self.invalidateFilter()
    
    def clear_filters(self):
        """Clear all filters."""
        self._type_filter = None
        self._status_filter = None
        self._source_filter = ""
        self._tier_filter = ""
        self._search_text = ""
        self.invalidateFilter()


class ReviewQueueView(QTableView):
    """
    Custom table view for the review queue with optimized settings.
    """
    
    item_activated = pyqtSignal(int)  # Row index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_view()
    
    def _setup_view(self):
        """Configure view settings."""
        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Appearance
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)
        
        # Headers
        h_header = self.horizontalHeader()
        h_header.setStretchLastSection(True)
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        v_header = self.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(32)
        
        # Performance for large datasets
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # Styling
        self.setStyleSheet("""
            QTableView {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                gridline-color: #e9ecef;
            }
            QTableView::item {
                padding: 4px 8px;
            }
            QTableView::item:selected {
                background-color: #cce5ff;
                color: #004085;
            }
            QTableView::item:hover {
                background-color: #e2e6ea;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                border: none;
                border-bottom: 2px solid #4c4c4c;
                padding: 8px;
                font-weight: bold;
            }
        """)
        
        # Connect click to emit activated signal
        self.clicked.connect(self._on_clicked)
    
    def _on_clicked(self, index: QModelIndex):
        """Handle click on a row."""
        if index.isValid():
            # Get source row if using proxy model
            if hasattr(self.model(), 'mapToSource'):
                source_index = self.model().mapToSource(index)
                self.item_activated.emit(source_index.row())
            else:
                self.item_activated.emit(index.row())
    
    def set_column_widths(self):
        """Set appropriate column widths."""
        self.setColumnWidth(COL_SELECTED, 40)
        self.setColumnWidth(COL_TYPE, 100)
        self.setColumnWidth(COL_CONTENT, 300)
        self.setColumnWidth(COL_SOURCE, 200)
        self.setColumnWidth(COL_TIER, 60)
        self.setColumnWidth(COL_IMPORTANCE, 80)
        self.setColumnWidth(COL_STATUS, 100)

