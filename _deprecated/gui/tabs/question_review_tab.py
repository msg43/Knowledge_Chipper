"""
Question Review Tab

Provides a QTableView-based interface for reviewing and approving questions
discovered by the Question Mapper system.
"""

import logging
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database.service import DatabaseService
from ...database.models import Question

logger = logging.getLogger(__name__)


class QuestionDetailsDialog(QDialog):
    """Dialog for viewing and editing question details."""

    def __init__(self, question: dict[str, Any], parent=None):
        super().__init__(parent)
        self.question = question
        self.setWindowTitle(f"Question Details - {question.get('question_id', 'Unknown')}")
        self.setModal(True)
        self.setMinimumWidth(700)

        self._setup_ui()
        self._load_question_data()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Question text
        layout.addWidget(QLabel("Question:"))
        self.question_edit = QTextEdit()
        self.question_edit.setMaximumHeight(80)
        self.question_edit.setReadOnly(True)  # Questions shouldn't be edited directly
        layout.addWidget(self.question_edit)

        # Metadata group
        meta_group = QGroupBox("Metadata")
        meta_layout = QVBoxLayout()

        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_label = QLabel()
        type_layout.addWidget(self.type_label)
        type_layout.addStretch()
        meta_layout.addLayout(type_layout)

        # Domain
        domain_layout = QHBoxLayout()
        domain_layout.addWidget(QLabel("Domain:"))
        self.domain_label = QLabel()
        domain_layout.addWidget(self.domain_label)
        domain_layout.addStretch()
        meta_layout.addLayout(domain_layout)

        # Importance
        importance_layout = QHBoxLayout()
        importance_layout.addWidget(QLabel("Importance Score:"))
        self.importance_label = QLabel()
        importance_layout.addWidget(self.importance_label)
        importance_layout.addStretch()
        meta_layout.addLayout(importance_layout)

        meta_group.setLayout(meta_layout)
        layout.addWidget(meta_group)

        # Notes group
        notes_group = QGroupBox("Notes / Rationale")
        notes_layout = QVBoxLayout()
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        notes_layout.addWidget(self.notes_edit)
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.approve_btn = QPushButton("✓ Approve")
        self.approve_btn.setStyleSheet("background-color: #28a745;")
        self.approve_btn.clicked.connect(lambda: self.done(1))  # Approve = code 1
        button_layout.addWidget(self.approve_btn)

        self.reject_btn = QPushButton("✗ Reject")
        self.reject_btn.setStyleSheet("background-color: #dc3545;")
        self.reject_btn.clicked.connect(lambda: self.done(2))  # Reject = code 2
        button_layout.addWidget(self.reject_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_question_data(self):
        """Load question data into form fields."""
        self.question_edit.setPlainText(self.question.get("question_text", ""))
        self.type_label.setText(self.question.get("question_type", "unknown"))
        self.domain_label.setText(self.question.get("domain", "N/A"))

        importance = self.question.get("importance_score")
        if importance is not None:
            self.importance_label.setText(f"{importance:.2f}")
        else:
            self.importance_label.setText("N/A")

        self.notes_edit.setPlainText(self.question.get("notes", ""))

    def get_updated_notes(self) -> str:
        """Get the updated notes text."""
        return self.notes_edit.toPlainText().strip()


class QuestionsTableModel(QAbstractTableModel):
    """Table model for displaying and reviewing questions."""

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db_service = db_service
        self.questions: list[dict[str, Any]] = []

        # Column definitions
        self.columns = [
            ("Question", "question_text"),
            ("Type", "question_type"),
            ("Domain", "domain"),
            ("Importance", "importance_score"),
            ("Status", "reviewed"),
        ]

        self.load_data()

    def load_data(self, domain_filter: str | None = None):
        """Load questions from database with optional domain filter."""
        try:
            if domain_filter:
                self.questions = self.db_service.get_questions_by_domain(
                    domain_filter, status_filter=["open", "answered"]
                )
            else:
                # Get all unreviewed questions
                self.questions = self.db_service.get_unreviewed_questions(limit=100)

            logger.info(f"Loaded {len(self.questions)} questions for review")

        except Exception as e:
            logger.error(f"Failed to load questions: {e}")
            self.questions = []

        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return number of questions."""
        return len(self.questions)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return number of columns."""
        return len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> Any:
        """Return header data."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self.columns):
                return self.columns[section][0]
        return None

    def data(self, index: QModelIndex, role: int) -> Any:
        """Return cell data for display."""
        if not index.isValid() or not (0 <= index.row() < len(self.questions)):
            return None

        question = self.questions[index.row()]
        col_name, col_attr = self.columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_name == "Question":
                # Truncate long questions for display
                text = question.get(col_attr, "")
                return text[:80] + "..." if len(text) > 80 else text
            elif col_name == "Importance":
                score = question.get(col_attr)
                return f"{score:.2f}" if score is not None else "N/A"
            elif col_name == "Status":
                reviewed = question.get("reviewed", False)
                return "✓ Reviewed" if reviewed else "⏳ Pending"
            else:
                value = question.get(col_attr, "")
                return str(value) if value else "N/A"

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Color code by review status
            reviewed = question.get("reviewed", False)
            if reviewed:
                return QColor(200, 255, 200)  # Light green
            else:
                return QColor(255, 255, 200)  # Light yellow

        elif role == Qt.ItemDataRole.FontRole:
            reviewed = question.get("reviewed", False)
            if not reviewed:
                font = QFont()
                font.setBold(True)
                return font

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def get_question(self, row: int) -> dict[str, Any] | None:
        """Get question at row."""
        if 0 <= row < len(self.questions):
            return self.questions[row]
        return None


class QuestionReviewTab(QWidget):
    """Question Review Tab for approving discovered questions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_service = DatabaseService()
        self._setup_ui()

    def _setup_ui(self):
        """Setup the review tab UI."""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<h2>❓ Question Review</h2>"))
        header_layout.addStretch()

        # Domain filter
        self.domain_combo = QComboBox()
        self.domain_combo.addItem("All Domains (Unreviewed)")
        self._populate_domains()
        self.domain_combo.currentTextChanged.connect(self._on_domain_filter_changed)
        header_layout.addWidget(QLabel("Domain:"))
        header_layout.addWidget(self.domain_combo)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_data)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Info label
        info_label = QLabel(
            "Review questions discovered by the Question Mapper system. "
            "Double-click a question to view details and approve/reject."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(info_label)

        # Table view
        self.table_view = QTableView()
        self.model = QuestionsTableModel(self.db_service)
        self.table_view.setModel(self.model)

        # Configure table
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_view.setSortingEnabled(True)
        self.table_view.setWordWrap(True)

        # Set column widths
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Question
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )  # Type
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )  # Domain
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )  # Importance
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )  # Status

        # Connect double-click
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

        layout.addWidget(self.table_view)

        # Action buttons
        button_layout = QHBoxLayout()

        # Stats label
        self.stats_label = QLabel()
        self._update_stats()
        button_layout.addWidget(self.stats_label)

        button_layout.addStretch()

        # Approve selected button
        approve_btn = QPushButton("✓ Approve Selected")
        approve_btn.setStyleSheet("background-color: #28a745; color: white;")
        approve_btn.clicked.connect(self._approve_selected)
        button_layout.addWidget(approve_btn)

        # Reject selected button
        reject_btn = QPushButton("✗ Reject Selected")
        reject_btn.setStyleSheet("background-color: #dc3545; color: white;")
        reject_btn.clicked.connect(self._reject_selected)
        button_layout.addWidget(reject_btn)

        # View claims button
        view_claims_btn = QPushButton("📋 View Claims")
        view_claims_btn.clicked.connect(self._view_claims_for_selected)
        button_layout.addWidget(view_claims_btn)

        layout.addLayout(button_layout)

    def _populate_domains(self):
        """Populate domain filter combo box."""
        try:
            # Get unique domains from questions
            with self.db_service.get_session() as session:
                from sqlalchemy import distinct

                domains = (
                    session.query(distinct(Question.domain))
                    .filter(Question.domain.isnot(None))
                    .order_by(Question.domain)
                    .all()
                )

                for (domain,) in domains:
                    if domain:
                        self.domain_combo.addItem(domain)

        except Exception as e:
            logger.warning(f"Could not populate domains dropdown: {e}")

    def _on_domain_filter_changed(self, text: str):
        """Handle domain filter change."""
        if text == "All Domains (Unreviewed)":
            self.model.load_data()
        else:
            self.model.load_data(domain_filter=text)
        self._update_stats()

    def _on_row_double_clicked(self, index: QModelIndex):
        """Handle row double-click to show details dialog."""
        if not index.isValid():
            return

        question = self.model.get_question(index.row())
        if not question:
            return

        # Get full question details
        full_question = self.db_service.get_question(question["question_id"])
        if not full_question:
            QMessageBox.warning(self, "Error", "Could not load question details")
            return

        # Show details dialog
        dialog = QuestionDetailsDialog(full_question, self)
        result = dialog.exec()

        if result == 1:  # Approved
            self._approve_question(question["question_id"], dialog.get_updated_notes())
        elif result == 2:  # Rejected
            self._reject_question(question["question_id"], dialog.get_updated_notes())

    def _approve_selected(self):
        """Approve all selected questions."""
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(
                self, "No Selection", "Please select questions to approve"
            )
            return

        question_ids = []
        for index in selected_indexes:
            question = self.model.get_question(index.row())
            if question:
                question_ids.append(question["question_id"])

        # Confirm
        reply = QMessageBox.question(
            self,
            "Confirm Approval",
            f"Approve {len(question_ids)} question(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            approved = 0
            for qid in question_ids:
                if self.db_service.update_question_status(qid, reviewed=True):
                    approved += 1

            QMessageBox.information(
                self, "Success", f"Approved {approved} question(s)"
            )
            self._refresh_data()

    def _reject_selected(self):
        """Reject (delete) selected questions."""
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(
                self, "No Selection", "Please select questions to reject"
            )
            return

        question_ids = []
        for index in selected_indexes:
            question = self.model.get_question(index.row())
            if question:
                question_ids.append(question["question_id"])

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Rejection",
            f"Reject and delete {len(question_ids)} question(s)?\n\n"
            "This will remove the questions and their claim assignments.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = 0
            try:
                with self.db_service.get_session() as session:
                    for qid in question_ids:
                        q = session.query(Question).filter_by(question_id=qid).first()
                        if q:
                            session.delete(q)
                            deleted += 1
                    session.commit()

                QMessageBox.information(
                    self, "Success", f"Rejected {deleted} question(s)"
                )
                self._refresh_data()

            except Exception as e:
                logger.error(f"Failed to reject questions: {e}")
                QMessageBox.critical(
                    self, "Error", f"Failed to reject questions:\n{e}"
                )

    def _approve_question(self, question_id: str, notes: str):
        """Approve a single question."""
        success = self.db_service.update_question_status(
            question_id, reviewed=True, notes=notes
        )

        if success:
            QMessageBox.information(self, "Success", "Question approved!")
            self._refresh_data()
        else:
            QMessageBox.critical(self, "Error", "Failed to approve question")

    def _reject_question(self, question_id: str, notes: str):
        """Reject (delete) a single question."""
        try:
            with self.db_service.get_session() as session:
                q = session.query(Question).filter_by(question_id=question_id).first()
                if q:
                    session.delete(q)
                    session.commit()

            QMessageBox.information(self, "Success", "Question rejected and deleted")
            self._refresh_data()

        except Exception as e:
            logger.error(f"Failed to reject question: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reject question:\n{e}")

    def _view_claims_for_selected(self):
        """View claims assigned to selected question."""
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(
                self, "No Selection", "Please select a question to view claims"
            )
            return

        # Get first selected question
        question = self.model.get_question(selected_indexes[0].row())
        if not question:
            return

        question_id = question["question_id"]
        claims = self.db_service.get_claims_for_question(question_id)

        # Show claims dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Claims for Question - {question_id}")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)

        layout = QVBoxLayout(dialog)

        # Question text
        layout.addWidget(QLabel(f"<b>Question:</b> {question['question_text']}"))

        # Claims list
        claims_text = QTextEdit()
        claims_text.setReadOnly(True)

        if claims:
            text = f"Found {len(claims)} claim(s) assigned to this question:\n\n"
            for i, claim in enumerate(claims, 1):
                text += f"{i}. [{claim['relation_type']}] {claim['claim_text']}\n"
                text += f"   Relevance: {claim['relevance_score']:.2f}\n"
                if claim.get("rationale"):
                    text += f"   Rationale: {claim['rationale']}\n"
                text += "\n"
            claims_text.setPlainText(text)
        else:
            claims_text.setPlainText("No claims assigned to this question yet.")

        layout.addWidget(claims_text)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _refresh_data(self):
        """Refresh data from database."""
        current_filter = self.domain_combo.currentText()
        if current_filter == "All Domains (Unreviewed)":
            self.model.load_data()
        else:
            self.model.load_data(domain_filter=current_filter)
        self._update_stats()

    def _update_stats(self):
        """Update statistics label."""
        total = len(self.model.questions)
        reviewed_count = sum(
            1 for q in self.model.questions if q.get("reviewed", False)
        )
        pending_count = total - reviewed_count

        self.stats_label.setText(
            f"📊 {total} total | {pending_count} pending | {reviewed_count} reviewed"
        )
