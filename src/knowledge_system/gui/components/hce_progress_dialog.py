"""Progress dialog for HCE pipeline stages."""

from PyQt6.QtCore import Qt, pyqtSignal
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

    def __init__(self, parent=None):
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
            ("skim", "Skimming Document"),
            ("miner", "Mining Claims"),
            ("judge", "Judging Claim Quality"),
            ("dedupe", "Deduplicating Claims"),
            ("rerank", "Reranking Claims"),
            ("nli", "Checking Contradictions"),
            ("relations", "Extracting Relations"),
            ("people", "Identifying People"),
            ("concepts", "Extracting Concepts"),
            ("glossary", "Building Glossary"),
            ("export", "Exporting Results"),
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

    def reset_progress(self):
        """Reset all progress bars to 0."""
        self.overall_progress.setValue(0)
        for bar in self.stage_bars.values():
            bar.setValue(0)
            bar.setStyleSheet("")
        self.stats_text.clear()

    def update_overall_progress(self, current: int, total: int):
        """Update overall file progress."""
        if total > 0:
            percentage = int((current / total) * 100)
            self.overall_progress.setValue(percentage)
            self.overall_label.setText(f"{current} of {total} files processed")

    def update_file(self, filename: str):
        """Update current file being processed."""
        self.file_label.setText(f"Processing: {filename}")

    def update_stage_progress(self, stage: str, percentage: int, status: str = ""):
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
                self.stage_labels[stage].setText(
                    f"{self.stage_labels[stage].text().split(':')[0]}: {status}"
                )

    def update_statistics(self, stats: dict):
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

    def on_cancel(self):
        """Handle cancel button click."""
        self.cancelled.emit()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")

    def set_finished(self):
        """Set dialog to finished state."""
        self.cancel_button.setText("Close")
        self.cancel_button.setEnabled(True)
        self.cancel_button.clicked.disconnect()
        self.cancel_button.clicked.connect(self.accept)
