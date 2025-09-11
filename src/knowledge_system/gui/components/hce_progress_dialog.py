"""Progress dialog for HCE pipeline stages."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class HCEProgressDialog(QDialog):
    """Dialog showing detailed progress for HCE pipeline stages."""

    cancelled = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Claim Extraction Progress")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Main layout
        layout = QVBoxLayout(self)

        # Current file label
        self.file_label = QLabel("Processing...")
        self.file_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.file_label)

        # Overall progress
        overall_group = QGroupBox("Overall Progress")
        overall_layout = QVBoxLayout()

        self.overall_progress = QProgressBar()
        self.overall_label = QLabel("0 of 0 files processed")
        overall_layout.addWidget(self.overall_progress)
        overall_layout.addWidget(self.overall_label)

        overall_group.setLayout(overall_layout)
        layout.addWidget(overall_group)

        # HCE Pipeline stages
        stages_group = QGroupBox("Pipeline Stages")
        stages_layout = QVBoxLayout()

        # Individual stage progress bars
        self.stage_bars = {}
        self.stage_labels = {}

        stages = [
            ("analyzing", "Analyzing Document Structure"),
            ("mining", "Mining Claims"),
            ("evidence", "Linking Evidence"),
            ("deduplicating", "Deduplicating Claims"),
            ("ranking", "Ranking Claims"),
            ("routing", "Routing Claims"),
            ("evaluating", "Evaluating Claims"),
            ("people", "Extracting People"),
            ("concepts", "Extracting Concepts"),
            ("jargon", "Extracting Jargon"),
            ("categorizing", "Categorizing Content"),
            ("finalizing", "Finalizing Summary"),
        ]

        for stage_id, stage_name in stages:
            stage_layout = QHBoxLayout()

            label = QLabel(stage_name)
            label.setMinimumWidth(150)
            self.stage_labels[stage_id] = label

            bar = QProgressBar()
            bar.setTextVisible(True)
            self.stage_bars[stage_id] = bar

            stage_layout.addWidget(label)
            stage_layout.addWidget(bar)
            stages_layout.addLayout(stage_layout)

        stages_group.setLayout(stages_layout)
        layout.addWidget(stages_group)

        # Statistics
        stats_group = QGroupBox("Extraction Statistics")
        stats_layout = QVBoxLayout()

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(100)
        stats_layout.addWidget(self.stats_text)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Reset all progress bars
        self.reset_progress()

    def reset_progress(self) -> None:
        """Reset all progress bars to 0."""
        self.overall_progress.setValue(0)
        for bar in self.stage_bars.values():
            bar.setValue(0)
            bar.setStyleSheet("")
        self.stats_text.clear()

    def update_overall_progress(self, current: int, total: int) -> None:
        """Update overall file progress."""
        if total > 0:
            percentage = int((current / total) * 100)
            self.overall_progress.setValue(percentage)
            self.overall_label.setText(f"{current} of {total} files processed")

    def update_file(self, filename: str) -> None:
        """Update current file being processed."""
        self.file_label.setText(f"Processing: {filename}")

    def _map_step_to_stage(self, step: str) -> str | None:
        """Map progress step names to stage IDs."""
        step_lower = step.lower()

        if "analyzing" in step_lower or "document structure" in step_lower:
            return "analyzing"
        elif "mining" in step_lower:
            return "mining"
        elif "linking evidence" in step_lower or "evidence" in step_lower:
            return "evidence"
        elif "deduplicating" in step_lower or "dedupe" in step_lower:
            return "deduplicating"
        elif "ranking" in step_lower or "rerank" in step_lower:
            return "ranking"
        elif "routing" in step_lower:
            return "routing"
        elif "evaluating" in step_lower or "judging" in step_lower:
            return "evaluating"
        elif "extracting people" in step_lower or "people" in step_lower:
            return "people"
        elif "extracting concepts" in step_lower or "concepts" in step_lower:
            return "concepts"
        elif "extracting jargon" in step_lower or "jargon" in step_lower:
            return "jargon"
        elif "categorizing" in step_lower:
            return "categorizing"
        elif "finalizing" in step_lower:
            return "finalizing"
        # Note: temporality and relationships steps removed due to computational complexity

        return None

    def update_stage_progress(
        self, stage: str, percentage: int, status: str = ""
    ) -> None:
        """Update progress for a specific HCE stage."""
        if stage in self.stage_bars:
            bar = self.stage_bars[stage]
            bar.setValue(percentage)

            # Update bar color based on completion
            if percentage == 100:
                bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            elif percentage > 0:
                bar.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")

            # Update label with status if provided
            if status and stage in self.stage_labels:
                original_text = self.stage_labels[stage].text().split(":")[0]
                self.stage_labels[stage].setText(f"{original_text}: {status}")

    def update_progress_from_step(
        self, step_name: str, percentage: int, status: str = ""
    ) -> None:
        """Update progress using step name from HCE pipeline."""
        stage_id = self._map_step_to_stage(step_name)
        if stage_id:
            self.update_stage_progress(stage_id, int(percentage), status)

    def update_statistics(self, stats: dict) -> None:
        """Update extraction statistics."""
        stats_text = []

        if "claims" in stats:
            stats_text.append(f"Claims extracted: {stats['claims']}")
        if "tier1_claims" in stats:
            stats_text.append(f"High-quality claims: {stats['tier1_claims']}")
        if "people" in stats:
            stats_text.append(f"People identified: {stats['people']}")
        if "concepts" in stats:
            stats_text.append(f"Concepts found: {stats['concepts']}")
        if "relations" in stats:
            stats_text.append(f"Relations mapped: {stats['relations']}")
        if "contradictions" in stats:
            stats_text.append(f"Contradictions detected: {stats['contradictions']}")

        self.stats_text.setPlainText("\n".join(stats_text))

    def on_cancel(self) -> None:
        """Handle cancel button click."""
        self.cancelled.emit()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")

    def set_finished(self) -> None:
        """Set dialog to finished state."""
        self.cancel_button.setText("Close")
        self.cancel_button.setEnabled(True)
        self.cancel_button.clicked.disconnect()
        self.cancel_button.clicked.connect(self.accept)
