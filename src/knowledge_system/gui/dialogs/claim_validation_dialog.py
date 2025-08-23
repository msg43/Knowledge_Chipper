"""
Claim Tier Validation Dialog

Popup dialog for validating HCE claim tier assignments (A/B/C).
Users can confirm or modify the LLM-assigned tiers for individual claims.
"""

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
    QLabel, QPushButton, QFrame, QProgressBar, QButtonGroup,
    QRadioButton, QTextEdit, QGroupBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QPalette

from ...database.service import DatabaseService
from ...logger import get_logger

logger = get_logger(__name__)


class ClaimCard(QFrame):
    """Individual claim card widget for tier validation."""
    
    tier_changed = pyqtSignal(str, str, str)  # claim_id, old_tier, new_tier
    claim_confirmed = pyqtSignal(str, str, bool)  # claim_id, tier, was_modified
    
    def __init__(self, claim_data: Dict[str, Any], parent=None):
        """Initialize claim card.
        
        Args:
            claim_data: Dictionary containing claim information
                - claim_id: Unique identifier
                - canonical: Claim text
                - tier: Current tier (A, B, or C)
                - claim_type: Type of claim
                - evidence: Evidence spans
                - scores: Confidence scores
        """
        super().__init__(parent)
        self.claim_data = claim_data
        self.original_tier = claim_data.get("tier", "C")
        self.current_tier = self.original_tier
        self.is_confirmed = False
        self.was_modified = False
        
        self.setup_ui()
        self.update_card_style()

    def setup_ui(self):
        """Set up the claim card UI."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Header with claim ID and type
        header_layout = QHBoxLayout()
        
        claim_id = self.claim_data.get("claim_id", "Unknown")
        claim_type = self.claim_data.get("claim_type", "general")
        
        id_label = QLabel(f"Claim: {claim_id[:12]}...")
        id_label.setStyleSheet("font-weight: bold; color: #666;")
        header_layout.addWidget(id_label)
        
        header_layout.addStretch()
        
        type_label = QLabel(f"Type: {claim_type.title()}")
        type_label.setStyleSheet("color: #888; font-style: italic;")
        header_layout.addWidget(type_label)
        
        layout.addLayout(header_layout)
        
        # Claim text
        claim_text = self.claim_data.get("canonical", "No claim text available")
        claim_label = QLabel(claim_text)
        claim_label.setWordWrap(True)
        claim_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 11pt;
                line-height: 1.4;
            }
        """)
        layout.addWidget(claim_label)
        
        # Tier selection section
        tier_group = QGroupBox("Tier Assignment")
        tier_layout = QHBoxLayout()
        
        self.tier_button_group = QButtonGroup()
        self.tier_buttons = {}
        
        # Create tier buttons
        for tier in ["A", "B", "C"]:
            btn = QRadioButton(f"Tier {tier}")
            btn.setChecked(tier == self.original_tier)
            btn.toggled.connect(lambda checked, t=tier: self._on_tier_changed(t, checked))
            
            # Style the buttons
            color = self._get_tier_color(tier)
            btn.setStyleSheet(f"""
                QRadioButton {{
                    font-weight: bold;
                    padding: 5px;
                }}
                QRadioButton::indicator::checked {{
                    background-color: {color};
                    border: 2px solid #333;
                }}
            """)
            
            self.tier_button_group.addButton(btn)
            self.tier_buttons[tier] = btn
            tier_layout.addWidget(btn)
        
        # Add tier descriptions
        tier_layout.addStretch()
        desc_label = QLabel("A: High confidence • B: Medium confidence • C: Supporting")
        desc_label.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        tier_layout.addWidget(desc_label)
        
        tier_group.setLayout(tier_layout)
        layout.addWidget(tier_group)
        
        # Evidence preview (if available)
        evidence = self.claim_data.get("evidence", [])
        if evidence:
            evidence_group = QGroupBox("Evidence")
            evidence_layout = QVBoxLayout()
            
            evidence_text = QTextEdit()
            evidence_text.setMaximumHeight(80)
            evidence_text.setReadOnly(True)
            
            # Show first few evidence spans
            evidence_preview = ""
            for i, span in enumerate(evidence[:2]):  # Show first 2 evidence spans
                quote = span.get("quote", "")
                if quote:
                    evidence_preview += f"• {quote}\n"
            
            if len(evidence) > 2:
                evidence_preview += f"... and {len(evidence) - 2} more evidence spans"
            
            evidence_text.setPlainText(evidence_preview or "No evidence available")
            evidence_text.setStyleSheet("font-size: 9pt; background-color: #f8f9fa;")
            evidence_layout.addWidget(evidence_text)
            
            evidence_group.setLayout(evidence_layout)
            layout.addWidget(evidence_group)
        
        # Confidence scores (if available)
        scores = self.claim_data.get("scores", {})
        if scores:
            scores_layout = QHBoxLayout()
            scores_layout.addWidget(QLabel("Confidence:"))
            
            for score_name, score_value in scores.items():
                score_label = QLabel(f"{score_name}: {score_value:.2f}")
                score_label.setStyleSheet("color: #666; font-size: 9pt;")
                scores_layout.addWidget(score_label)
            
            scores_layout.addStretch()
            layout.addLayout(scores_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.confirm_btn = QPushButton("✓ Confirm")
        self.confirm_btn.clicked.connect(self._confirm_claim)
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._skip_claim)
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        button_layout.addWidget(self.skip_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Set frame properties
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _get_tier_color(self, tier: str) -> str:
        """Get color for tier."""
        colors = {
            "A": "#28a745",  # Green
            "B": "#ffc107",  # Yellow
            "C": "#6c757d"   # Gray
        }
        return colors.get(tier, "#6c757d")

    def _on_tier_changed(self, tier: str, checked: bool):
        """Handle tier selection change."""
        if checked and tier != self.current_tier:
            old_tier = self.current_tier
            self.current_tier = tier
            self.was_modified = (tier != self.original_tier)
            
            self.tier_changed.emit(self.claim_data.get("claim_id", ""), old_tier, tier)
            self.update_card_style()

    def _confirm_claim(self):
        """Confirm the current tier assignment."""
        self.is_confirmed = True
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setText("✓ Confirmed")
        
        # Disable tier buttons
        for btn in self.tier_buttons.values():
            btn.setEnabled(False)
        
        self.claim_confirmed.emit(
            self.claim_data.get("claim_id", ""),
            self.current_tier,
            self.was_modified
        )
        
        self.update_card_style()

    def _skip_claim(self):
        """Skip this claim (don't validate)."""
        self.setEnabled(False)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                opacity: 0.6;
            }
        """)

    def update_card_style(self):
        """Update card styling based on state."""
        if self.is_confirmed:
            # Confirmed state
            color = self._get_tier_color(self.current_tier)
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #f8f9fa;
                    border: 3px solid {color};
                    border-radius: 8px;
                    margin: 5px;
                }}
            """)
        elif self.was_modified:
            # Modified but not confirmed
            self.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 2px solid #ffc107;
                    border-radius: 8px;
                    margin: 5px;
                }
            """)
        else:
            # Default state
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 2px solid #dee2e6;
                    border-radius: 8px;
                    margin: 5px;
                }
                QFrame:hover {
                    border-color: #007bff;
                }
            """)

    def get_validation_result(self) -> Optional[Dict[str, Any]]:
        """Get the validation result for this claim."""
        if not self.is_confirmed:
            return None
        
        return {
            "claim_id": self.claim_data.get("claim_id"),
            "original_tier": self.original_tier,
            "validated_tier": self.current_tier,
            "was_modified": self.was_modified,
            "claim_text": self.claim_data.get("canonical"),
            "claim_type": self.claim_data.get("claim_type")
        }


class ClaimValidationDialog(QDialog):
    """Dialog for validating claim tier assignments."""
    
    validation_completed = pyqtSignal(list)  # List of validation results
    
    def __init__(self, claims_data: List[Dict[str, Any]], parent=None):
        """Initialize claim validation dialog.
        
        Args:
            claims_data: List of claim dictionaries to validate
            parent: Parent widget
        """
        super().__init__(parent)
        self.claims_data = claims_data
        self.claim_cards = []
        self.confirmed_count = 0
        self.modified_count = 0
        
        self.setup_ui()
        self.create_claim_cards()

    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Validate Claim Tier Assignments")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # Header
        header_layout = QVBoxLayout()
        
        title_label = QLabel("Claim Tier Validation")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        instruction_label = QLabel(
            "Review each claim and confirm or modify its tier assignment. "
            "Your feedback helps improve the AI's claim evaluation accuracy."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setStyleSheet("color: #666; margin: 10px;")
        header_layout.addWidget(instruction_label)
        
        layout.addLayout(header_layout)
        
        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.claims_data))
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel(f"0 of {len(self.claims_data)} claims validated")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Scrollable claims area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.claims_widget = QWidget()
        self.claims_layout = QVBoxLayout(self.claims_widget)
        self.claims_layout.setSpacing(10)
        
        scroll_area.setWidget(self.claims_widget)
        layout.addWidget(scroll_area)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.confirm_all_btn = QPushButton("Confirm All Remaining")
        self.confirm_all_btn.clicked.connect(self._confirm_all_remaining)
        self.confirm_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        
        self.finish_btn = QPushButton("Finish Validation")
        self.finish_btn.clicked.connect(self._finish_validation)
        self.finish_btn.setEnabled(False)
        self.finish_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.confirm_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.finish_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def create_claim_cards(self):
        """Create claim cards for each claim."""
        for claim_data in self.claims_data:
            card = ClaimCard(claim_data, self)
            card.claim_confirmed.connect(self._on_claim_confirmed)
            card.tier_changed.connect(self._on_tier_changed)
            
            self.claim_cards.append(card)
            self.claims_layout.addWidget(card)
        
        # Add stretch to push cards to top
        self.claims_layout.addStretch()

    def _on_claim_confirmed(self, claim_id: str, tier: str, was_modified: bool):
        """Handle claim confirmation."""
        self.confirmed_count += 1
        if was_modified:
            self.modified_count += 1
        
        self._update_progress()
        
        # Enable finish button if all claims are confirmed
        if self.confirmed_count >= len(self.claims_data):
            self.finish_btn.setEnabled(True)
            self.confirm_all_btn.setEnabled(False)

    def _on_tier_changed(self, claim_id: str, old_tier: str, new_tier: str):
        """Handle tier change."""
        logger.debug(f"Claim {claim_id} tier changed from {old_tier} to {new_tier}")

    def _update_progress(self):
        """Update progress display."""
        self.progress_bar.setValue(self.confirmed_count)
        self.progress_label.setText(
            f"{self.confirmed_count} of {len(self.claims_data)} claims validated "
            f"({self.modified_count} modified)"
        )

    def _confirm_all_remaining(self):
        """Confirm all remaining unconfirmed claims with their current tiers."""
        for card in self.claim_cards:
            if not card.is_confirmed:
                card._confirm_claim()

    def _finish_validation(self):
        """Finish validation and emit results."""
        results = []
        for card in self.claim_cards:
            result = card.get_validation_result()
            if result:
                results.append(result)
        
        # Save results to database
        self._save_validation_results(results)
        
        self.validation_completed.emit(results)
        self.accept()

    def _save_validation_results(self, results: List[Dict[str, Any]]):
        """Save validation results to database."""
        try:
            db = DatabaseService()
            
            for result in results:
                # Save claim tier validation
                rating_id = db.save_quality_rating(
                    content_type="claim_tier",
                    content_id=result["claim_id"],
                    user_rating=self._tier_to_rating(result["validated_tier"]),
                    criteria_scores={"tier_validation": 1.0},
                    user_feedback=f"Tier validation: {result['original_tier']} -> {result['validated_tier']}",
                    llm_rating=self._tier_to_rating(result["original_tier"]),
                    is_user_corrected=result["was_modified"],
                    model_used="hce_system",
                    input_characteristics={
                        "claim_text": result["claim_text"],
                        "claim_type": result["claim_type"],
                        "original_tier": result["original_tier"],
                        "validated_tier": result["validated_tier"]
                    }
                )
                
                logger.info(f"Saved claim validation: {rating_id}")
            
        except Exception as e:
            logger.error(f"Failed to save validation results: {e}")

    def _tier_to_rating(self, tier: str) -> float:
        """Convert tier to numeric rating."""
        tier_map = {"A": 0.9, "B": 0.7, "C": 0.5}
        return tier_map.get(tier, 0.5)

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation session."""
        return {
            "total_claims": len(self.claims_data),
            "confirmed_claims": self.confirmed_count,
            "modified_claims": self.modified_count,
            "accuracy_rate": (self.confirmed_count - self.modified_count) / len(self.claims_data) if self.claims_data else 0
        }
