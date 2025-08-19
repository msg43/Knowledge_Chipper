#!/usr/bin/env python3
"""
Beta Testing Setup Script for HCE System

Sets up beta testing environment and feedback collection for HCE system.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class BetaTestingSetup:
    """Setup and manage beta testing for HCE system."""

    def __init__(self):
        """Initialize beta testing setup."""
        self.beta_dir = Path("beta_testing")
        self.feedback_file = self.beta_dir / "feedback.json"
        self.test_results_file = self.beta_dir / "test_results.json"
        self.user_guide_file = self.beta_dir / "BETA_USER_GUIDE.md"

    def setup_beta_environment(self) -> bool:
        """Set up beta testing environment.

        Returns:
            True if setup was successful
        """
        try:
            # Create beta testing directory
            self.beta_dir.mkdir(exist_ok=True)

            # Create feedback collection file
            self._create_feedback_system()

            # Create beta user guide
            self._create_beta_user_guide()

            # Create test results tracking
            self._create_test_results_tracking()

            logger.info("Beta testing environment setup completed")
            return True

        except Exception as e:
            logger.error(f"Beta testing setup failed: {e}")
            return False

    def _create_feedback_system(self):
        """Create feedback collection system."""
        feedback_structure = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "HCE v2.0 Beta",
                "feedback_format": "1.0",
            },
            "feedback_categories": {
                "ui_usability": [],
                "claim_quality": [],
                "performance": [],
                "bugs": [],
                "feature_requests": [],
                "general": [],
            },
            "user_sessions": [],
        }

        with open(self.feedback_file, "w") as f:
            json.dump(feedback_structure, f, indent=2)

    def _create_beta_user_guide(self):
        """Create beta user guide."""
        guide_content = """# HCE Beta Testing Guide

## Welcome Beta Testers! 🎉

Thank you for helping test the new HCE (Hybrid Claim Extractor) system! This guide will help you get the most out of your beta testing experience.

## What's New in HCE

### 🔍 **Claim Analysis Instead of Summaries**
- Get structured claims with confidence tiers (A/B/C)
- See contradictions and relationships between claims
- Evidence citations for each claim

### 🎛️ **Enhanced Controls**
- **Claim Filtering**: Filter by confidence tier, type, or limit count
- **Analysis Depth**: 5-level slider for processing intensity
- **Real-Time Analytics**: Live display during processing

### 🔍 **New Search Tab**
- Search across all extracted claims
- Filter by tier, type, and content
- Explore relationships between claims

## Beta Testing Focus Areas

### 1. **User Interface Testing**
Please test:
- [ ] Claim filtering controls in Content Analysis tab
- [ ] Analysis depth slider in Process tab
- [ ] Search functionality in Claim Search tab
- [ ] Real-time analytics display during processing

**Feedback Questions:**
- Are the controls intuitive and easy to use?
- Is the real-time feedback helpful?
- Any confusing terminology or unclear features?

### 2. **Output Quality Testing**
Please review:
- [ ] Generated markdown files with claim analysis
- [ ] Executive summaries from high-confidence claims
- [ ] People, concepts, and jargon sections
- [ ] Obsidian tags and wikilinks

**Feedback Questions:**
- Is the output format useful for your workflow?
- Are the extracted claims accurate and relevant?
- How's the confidence tiering (A/B/C)?

### 3. **Performance Testing**
Please test with:
- [ ] Small files (< 10 pages / 30 minutes)
- [ ] Medium files (10-50 pages / 1-2 hours)
- [ ] Large files (50+ pages / 2+ hours)
- [ ] Batch processing multiple files

**Feedback Questions:**
- How's the processing speed compared to before?
- Any memory issues or crashes?
- Is the progress tracking accurate?

### 4. **Workflow Integration**
Please test:
- [ ] Obsidian integration with generated files
- [ ] Searching and filtering claims
- [ ] Using generated tags and wikilinks
- [ ] Cross-document claim exploration

**Feedback Questions:**
- Does this fit into your existing workflow?
- What features are missing?
- How could the integration be improved?

## How to Provide Feedback

### 📝 **Structured Feedback**
1. Use the feedback collection system: `python scripts/collect_beta_feedback.py`
2. Or manually edit: `beta_testing/feedback.json`

### 🐛 **Bug Reports**
Include:
- What you were doing
- What you expected to happen
- What actually happened
- Steps to reproduce
- Any error messages

### 💡 **Feature Requests**
Describe:
- What you want to accomplish
- Why current features don't meet your needs
- How important this is for your workflow

## Test Scenarios

### **Scenario 1: Research Paper Analysis**
1. Upload a research paper (PDF)
2. Set Analysis Depth to "Deep (4)"
3. Enable contradiction analysis
4. Review extracted claims and relationships
5. Check Obsidian integration

### **Scenario 2: Video Content Analysis**
1. Process a YouTube video or local video file
2. Use "Balanced (3)" analysis depth
3. Filter results to show only Tier A claims
4. Search for specific topics in Claim Search tab
5. Review generated markdown format

### **Scenario 3: Batch Processing**
1. Process multiple related documents
2. Use Process tab with batch processing
3. Review consolidated results
4. Search across all processed content
5. Look for cross-document patterns

## Known Limitations

- Relationship visualization is basic (text-based)
- Some advanced batch processing features still in development
- Performance optimization ongoing

## Support

If you encounter issues:
1. Check logs in the Output section
2. Try different analysis depth settings
3. Use the migration validation script
4. Contact the development team

Thank you for your valuable feedback! 🙏
"""

        with open(self.user_guide_file, "w") as f:
            f.write(guide_content)

    def _create_test_results_tracking(self):
        """Create test results tracking system."""
        test_structure = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "beta_version": "HCE v2.0 Beta",
            },
            "test_sessions": [],
            "performance_metrics": [],
            "bug_reports": [],
            "feature_usage_stats": {},
        }

        with open(self.test_results_file, "w") as f:
            json.dump(test_structure, f, indent=2)

    def collect_feedback(
        self, category: str, feedback: str, user_id: str = "anonymous"
    ) -> bool:
        """Collect feedback from beta testers.

        Args:
            category: Feedback category
            feedback: Feedback text
            user_id: User identifier

        Returns:
            True if feedback was collected successfully
        """
        try:
            # Load existing feedback
            if self.feedback_file.exists():
                with open(self.feedback_file) as f:
                    data = json.load(f)
            else:
                return False

            # Add new feedback
            feedback_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "category": category,
                "feedback": feedback,
            }

            if category in data["feedback_categories"]:
                data["feedback_categories"][category].append(feedback_entry)
            else:
                data["feedback_categories"]["general"].append(feedback_entry)

            # Save updated feedback
            with open(self.feedback_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Feedback collected: {category}")
            return True

        except Exception as e:
            logger.error(f"Failed to collect feedback: {e}")
            return False

    def generate_beta_report(self) -> str:
        """Generate beta testing report."""
        try:
            # Load feedback data
            if not self.feedback_file.exists():
                return "No feedback data available"

            with open(self.feedback_file) as f:
                feedback_data = json.load(f)

            # Count feedback by category
            category_counts = {}
            for category, items in feedback_data["feedback_categories"].items():
                category_counts[category] = len(items)

            report = f"""# HCE Beta Testing Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Feedback Summary
"""

            for category, count in category_counts.items():
                report += f"- **{category.replace('_', ' ').title()}**: {count} items\n"

            report += f"\n**Total Feedback Items**: {sum(category_counts.values())}\n"

            return report

        except Exception as e:
            logger.error(f"Failed to generate beta report: {e}")
            return f"Error generating report: {e}"


def main():
    """Run beta testing setup."""
    import argparse

    parser = argparse.ArgumentParser(description="Setup HCE beta testing")
    parser.add_argument("--setup", action="store_true", help="Setup beta environment")
    parser.add_argument("--feedback", help="Collect feedback")
    parser.add_argument("--category", default="general", help="Feedback category")
    parser.add_argument("--user", default="anonymous", help="User ID")
    parser.add_argument("--report", action="store_true", help="Generate beta report")
    args = parser.parse_args()

    beta_setup = BetaTestingSetup()

    if args.setup:
        success = beta_setup.setup_beta_environment()
        print(
            "✅ Beta testing environment setup completed!"
            if success
            else "❌ Setup failed"
        )
    elif args.feedback:
        success = beta_setup.collect_feedback(args.category, args.feedback, args.user)
        print("✅ Feedback collected!" if success else "❌ Feedback collection failed")
    elif args.report:
        report = beta_setup.generate_beta_report()
        print(report)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
