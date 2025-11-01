"""Claim search and exploration tab for HCE system."""

import json
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database import DatabaseService
from ...logger import get_logger
from ..components.base_tab import BaseTab

logger = get_logger(__name__)


class ClaimSearchWorker(QThread):
    """Worker thread for searching claims."""

    search_completed = pyqtSignal(list)  # List of search results
    search_error = pyqtSignal(str)

    def __init__(self, query: str, filters: dict[str, Any], parent=None):
        super().__init__(parent)
        self.query = query
        self.filters = filters
        self.db = DatabaseService()

    def run(self):
        """Execute claim search."""
        try:
            results = self._search_claims()
            self.search_completed.emit(results)
        except Exception as e:
            self.search_error.emit(str(e))

    def _search_claims(self) -> list[dict]:
        """Search claims in database."""
        results = []

        try:
            with self.db.get_session() as session:
                from knowledge_system.database import MediaSource, Summary

                # Get HCE summaries
                hce_summaries = (
                    session.query(Summary)
                    .filter(
                        Summary.processing_type == "hce",
                        Summary.hce_data_json.isnot(None),
                    )
                    .all()
                )

                for summary in hce_summaries:
                    try:
                        # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
                        hce_data = summary.hce_data_json
                        video = (
                            session.query(MediaSource)
                            .filter(MediaSource.source_id == summary.source_id)
                            .first()
                        )

                        if not video:
                            continue

                        # Search through claims
                        claims = hce_data.get("claims", [])
                        for claim in claims:
                            if self._matches_search(claim, video):
                                results.append(
                                    {
                                        "claim": claim,
                                        "video": {
                                            "source_id": video.source_id,
                                            "title": video.title,
                                            "url": video.url,
                                        },
                                        "summary_id": summary.summary_id,
                                    }
                                )

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"Claim search failed: {e}")

        return results

    def _matches_search(self, claim: dict, video) -> bool:
        """Check if claim matches search criteria."""
        # Text search
        if self.query:
            claim_text = claim.get("canonical", "").lower()
            if self.query.lower() not in claim_text:
                return False

        # Tier filter
        tier_filter = self.filters.get("tier")
        if tier_filter and tier_filter != "All":
            claim_tier = claim.get("tier", "C")
            if tier_filter == "Tier A" and claim_tier != "A":
                return False
            elif tier_filter == "Tier B+" and claim_tier not in ["A", "B"]:
                return False

        # Type filter
        type_filter = self.filters.get("claim_type")
        if type_filter and type_filter != "All":
            if claim.get("claim_type", "") != type_filter:
                return False

        return True


class ClaimSearchTab(BaseTab):
    """Tab for searching and exploring claims across all processed content."""

    def __init__(self, parent=None):
        self.search_worker = None
        self.tab_name = "🔍 Claim Search"
        super().__init__(parent)

    def _setup_ui(self):
        """Setup the claim search UI."""
        layout = QVBoxLayout(self)

        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Search controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Search section
        search_group = QGroupBox("🔍 Search Claims")
        search_layout = QVBoxLayout()

        # Search input
        search_text_layout = QHBoxLayout()
        search_text_layout.addWidget(QLabel("Search Text:"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms...")
        self.search_input.returnPressed.connect(self._start_search)
        self.search_input.setToolTip(
            "Search for claims containing specific text or keywords.\n"
            "• Search across claim text, evidence, and related metadata\n"
            "• Use specific terms for better results\n"
            "• Press Enter or click Search button to execute\n"
            "• Results are ranked by relevance and confidence tier"
        )
        search_text_layout.addWidget(self.search_input)

        # Add info indicator for search input
        search_info_label = QLabel("ⓘ")
        search_info_label.setFixedSize(16, 16)
        search_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_info_label.setToolTip(
            "<b>Search Text:</b><br/><br/>"
            "Search for claims containing specific text or keywords.<br/>"
            "• Search across claim text, evidence, and related metadata<br/>"
            "• Use specific terms for better results<br/>"
            "• Press Enter or click Search button to execute<br/>"
            "• Results are ranked by relevance and confidence tier"
        )
        search_info_label.setStyleSheet(
            """
            QLabel {
                color: #007AFF;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0051D5;
            }
        """
        )
        search_text_layout.addWidget(search_info_label)
        search_layout.addLayout(search_text_layout)

        # Filters
        filters_layout = QHBoxLayout()

        # Tier filter
        tier_filter_layout = QHBoxLayout()
        tier_filter_layout.addWidget(QLabel("Tier:"))
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All", "Tier A", "Tier B+", "Tier C+"])
        self.tier_filter.setToolTip(
            "Filter claims by confidence tier:\n"
            "• All: Show claims from all tiers\n"
            "• Tier A: High-confidence, core claims (85%+ confidence)\n"
            "• Tier B+: Medium+ confidence claims (includes A and B tiers)\n"
            "• Tier C+: All claims (includes A, B, and C tiers)\n"
            "Higher tiers indicate more reliable and important claims"
        )
        tier_filter_layout.addWidget(self.tier_filter)

        # Add info indicator for tier filter
        tier_info_label = QLabel("ⓘ")
        tier_info_label.setFixedSize(16, 16)
        tier_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tier_info_label.setToolTip(
            "<b>Tier Filter:</b><br/><br/>"
            "Filter claims by confidence tier:<br/>"
            "• All: Show claims from all tiers<br/>"
            "• Tier A: High-confidence, core claims (85%+ confidence)<br/>"
            "• Tier B+: Medium+ confidence claims (includes A and B tiers)<br/>"
            "• Tier C+: All claims (includes A, B, and C tiers)<br/>"
            "Higher tiers indicate more reliable and important claims"
        )
        tier_info_label.setStyleSheet(
            """
            QLabel {
                color: #007AFF;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0051D5;
            }
        """
        )
        tier_filter_layout.addWidget(tier_info_label)
        filters_layout.addLayout(tier_filter_layout)

        # Type filter
        type_filter_layout = QHBoxLayout()
        type_filter_layout.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(
            ["All", "factual", "opinion", "prediction", "causal", "definition"]
        )
        self.type_filter.setToolTip(
            "Filter claims by type:\n"
            "• All: Show all claim types\n"
            "• Factual: Objective, verifiable statements\n"
            "• Opinion: Subjective viewpoints and interpretations\n"
            "• Prediction: Future-oriented claims and forecasts\n"
            "• Causal: Cause-and-effect relationships\n"
            "• Definition: Explanations and terminology"
        )
        type_filter_layout.addWidget(self.type_filter)

        # Add info indicator for type filter
        type_info_label = QLabel("ⓘ")
        type_info_label.setFixedSize(16, 16)
        type_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_info_label.setToolTip(
            "<b>Type Filter:</b><br/><br/>"
            "Filter claims by type:<br/>"
            "• All: Show all claim types<br/>"
            "• Factual: Objective, verifiable statements<br/>"
            "• Opinion: Subjective viewpoints and interpretations<br/>"
            "• Prediction: Future-oriented claims and forecasts<br/>"
            "• Causal: Cause-and-effect relationships<br/>"
            "• Definition: Explanations and terminology"
        )
        type_info_label.setStyleSheet(
            """
            QLabel {
                color: #007AFF;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0051D5;
            }
        """
        )
        type_filter_layout.addWidget(type_info_label)
        filters_layout.addLayout(type_filter_layout)

        search_layout.addLayout(filters_layout)

        # Search button
        self.search_btn = QPushButton("🔍 Search Claims")
        self.search_btn.clicked.connect(self._start_search)
        self.search_btn.setStyleSheet("background-color: #1976d2; font-weight: bold;")
        self.search_btn.setToolTip(
            "Execute claim search with current filters and query.\n"
            "• Searches across all processed HCE summaries\n"
            "• Results are grouped by tier (A, B, C) for easy review\n"
            "• Select any result to view detailed claim information\n"
            "• Shows claim relationships and evidence when available"
        )
        search_layout.addWidget(self.search_btn)

        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)

        # Results section
        results_group = QGroupBox("📋 Search Results")
        results_layout = QVBoxLayout()

        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self._on_result_selected)
        results_layout.addWidget(self.results_list)

        # Results stats
        self.results_stats = QLabel("Ready to search...")
        self.results_stats.setStyleSheet("color: #666; font-style: italic;")
        results_layout.addWidget(self.results_stats)

        results_group.setLayout(results_layout)
        left_layout.addWidget(results_group)

        splitter.addWidget(left_widget)

        # Right side: Claim details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Claim details
        details_group = QGroupBox("📄 Claim Details")
        details_layout = QVBoxLayout()

        self.claim_details = QTextEdit()
        self.claim_details.setReadOnly(True)
        self.claim_details.setPlaceholderText(
            "Select a claim from search results to view details..."
        )
        details_layout.addWidget(self.claim_details)

        details_group.setLayout(details_layout)
        right_layout.addWidget(details_group)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

    def _start_search(self):
        """Start claim search."""
        query = self.search_input.text().strip()

        if not query:
            self.show_warning("Empty Search", "Please enter search terms.")
            return

        # Prepare filters
        filters = {
            "tier": self.tier_filter.currentText(),
            "claim_type": self.type_filter.currentText(),
        }

        # Clear previous results
        self.results_list.clear()
        self.claim_details.clear()
        self.results_stats.setText("Searching...")

        # Start search worker
        self.search_worker = ClaimSearchWorker(query, filters)
        self.search_worker.search_completed.connect(self._on_search_completed)
        self.search_worker.search_error.connect(self._on_search_error)
        self.search_worker.start()

        # Update UI
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")

    def _on_search_completed(self, results: list[dict]):
        """Handle search completion."""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 Search Claims")

        # Display results
        self.results_list.clear()

        if not results:
            self.results_stats.setText("No claims found matching your search.")
            return

        # Group results by tier for better display
        tier_a_results = [r for r in results if r["claim"]["tier"] == "A"]
        tier_b_results = [r for r in results if r["claim"]["tier"] == "B"]
        tier_c_results = [r for r in results if r["claim"]["tier"] == "C"]

        # Add tier A claims first
        if tier_a_results:
            header_item = QListWidgetItem("🥇 Tier A Claims (High Confidence)")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header_item.setBackground(self.palette().alternateBase())
            self.results_list.addItem(header_item)

            for result in tier_a_results:
                self._add_result_item(result)

        # Add tier B claims
        if tier_b_results:
            header_item = QListWidgetItem("🥈 Tier B Claims (Medium Confidence)")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header_item.setBackground(self.palette().alternateBase())
            self.results_list.addItem(header_item)

            for result in tier_b_results:
                self._add_result_item(result)

        # Add tier C claims
        if tier_c_results:
            header_item = QListWidgetItem("🥉 Tier C Claims (Supporting)")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header_item.setBackground(self.palette().alternateBase())
            self.results_list.addItem(header_item)

            for result in tier_c_results:
                self._add_result_item(result)

        # Update stats
        self.results_stats.setText(
            f"Found {len(results)} claims: "
            f"{len(tier_a_results)} Tier A, {len(tier_b_results)} Tier B, {len(tier_c_results)} Tier C"
        )

    def _add_result_item(self, result: dict):
        """Add a result item to the list."""
        claim = result["claim"]
        video = result["video"]

        # Create display text
        canonical = claim.get("canonical", "")
        claim_type = claim.get("claim_type", "")
        video_title = video.get("title", "")

        display_text = f"{canonical[:100]}{'...' if len(canonical) > 100 else ''}"
        if claim_type:
            display_text += f" ({claim_type})"
        display_text += f" - {video_title[:50]}{'...' if len(video_title) > 50 else ''}"

        item = QListWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, result)
        self.results_list.addItem(item)

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection."""
        result = item.data(Qt.ItemDataRole.UserRole)
        if not result:
            return

        claim = result["claim"]
        result["video"]

        # Format claim details
        details = """# Claim Details

## Claim
**Text:** {claim.get('canonical', '')}
**Type:** {claim.get('claim_type', 'Unknown')}
**Tier:** {claim.get('tier', 'C')} (Confidence: {'High' if claim.get('tier') == 'A' else 'Medium' if claim.get('tier') == 'B' else 'Supporting'})

## Source Video
**Title:** {video.get('title', '')}
**URL:** {video.get('url', '')}
**Video ID:** {video.get('source_id', '')}

## Evidence
"""

        evidence = claim.get("evidence", [])
        if evidence:
            for i, ev in enumerate(evidence, 1):
                details += f"{i}. {ev}\n"
        else:
            details += "*No evidence recorded for this claim.*\n"

        # Add claim metadata
        if claim.get("claim_id"):
            details += f"\n## Metadata\n**Claim ID:** {claim.get('claim_id')}\n"

        # Add relationship visualization
        relations = self._get_claim_relations(
            claim.get("claim_id", ""), result["video"]["source_id"]
        )
        if relations:
            details += "\n## Relationships\n"
            for relation in relations:
                rel_type = relation.get("type", "unknown")
                target_claim = relation.get("target_claim", "")
                strength = relation.get("strength", 0.0)

                if rel_type == "supports":
                    details += f"🔗 **Supports:** {target_claim[:100]}{'...' if len(target_claim) > 100 else ''}\n"
                elif rel_type == "contradicts":
                    details += f"⚡ **Contradicts:** {target_claim[:100]}{'...' if len(target_claim) > 100 else ''}\n"
                elif rel_type == "depends_on":
                    details += f"🔄 **Depends on:** {target_claim[:100]}{'...' if len(target_claim) > 100 else ''}\n"
                else:
                    details += f"🔀 **{rel_type.title()}:** {target_claim[:100]}{'...' if len(target_claim) > 100 else ''}\n"

                if strength > 0:
                    details += f"   *Strength: {strength:.2f}*\n"
                details += "\n"

        self.claim_details.setMarkdown(details)

    def _get_claim_relations(self, claim_id: str, source_id: str) -> list[dict]:
        """Get relationships for a specific claim."""
        if not claim_id:
            return []

        try:
            db = DatabaseService()
            with db.get_session() as session:
                from knowledge_system.database.models import Summary

                # Get the HCE summary for this video
                summary = (
                    session.query(Summary)
                    .filter(
                        Summary.source_id == source_id, Summary.processing_type == "hce"
                    )
                    .first()
                )

                if not summary or not summary.hce_data_json:
                    return []

                # Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
                hce_data = summary.hce_data_json
                relations = hce_data.get("relations", [])
                claims = hce_data.get("claims", [])

                # Build claim lookup
                claim_lookup = {
                    c.get("claim_id"): c.get("canonical", "") for c in claims
                }

                # Find relations involving this claim
                relevant_relations = []
                for relation in relations:
                    source_id = relation.get("source")
                    target_id = relation.get("target")

                    if source_id == claim_id:
                        # This claim is the source
                        target_claim = claim_lookup.get(target_id, "Unknown claim")
                        relevant_relations.append(
                            {
                                "type": relation.get("type", "unknown"),
                                "target_claim": target_claim,
                                "strength": relation.get("strength", 0.0),
                                "direction": "outgoing",
                            }
                        )
                    elif target_id == claim_id:
                        # This claim is the target
                        source_claim = claim_lookup.get(source_id, "Unknown claim")
                        relevant_relations.append(
                            {
                                "type": relation.get("type", "unknown"),
                                "target_claim": source_claim,
                                "strength": relation.get("strength", 0.0),
                                "direction": "incoming",
                            }
                        )

                return relevant_relations

        except Exception as e:
            logger.error(f"Failed to get claim relations: {e}")
            return []

    def _on_search_error(self, error: str):
        """Handle search error."""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 Search Claims")
        self.results_stats.setText(f"Search failed: {error}")
        self.show_error("Search Error", f"Failed to search claims: {error}")

    def validate_inputs(self) -> bool:
        """Validate search inputs."""
        return len(self.search_input.text().strip()) > 0
