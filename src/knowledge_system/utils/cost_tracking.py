"""
Cost tracking and reporting system for Bright Data usage.

Provides comprehensive cost monitoring, budget management, and usage analytics
for Bright Data API and proxy services integrated with SQLite database.
"""

import json
from datetime import datetime, timedelta

from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class CostTracker:
    """
    Comprehensive cost tracking system for Bright Data services.

    Tracks API usage, proxy costs, provides budget alerts, and generates
    detailed usage reports for cost optimization.
    """

    # Default cost estimates (update based on actual Bright Data pricing)
    DEFAULT_COSTS = {
        "api_request": 0.001,  # $0.001 per API request
        "proxy_gb": 0.50,  # $0.50 per GB data transfer
        "proxy_request": 0.0001,  # $0.0001 per proxy request
        "residential_session": 0.01,  # $0.01 per session
    }

    def __init__(self, database_service: DatabaseService | None = None):
        """Initialize cost tracker with database service."""
        self.db = database_service or DatabaseService()

    def track_session_cost(
        self,
        session_id: str,
        session_type: str,
        requests_count: int = 0,
        data_bytes: int = 0,
        duration_seconds: int = 0,
        custom_cost: float | None = None,
    ) -> float:
        """
        Track cost for a Bright Data session.

        Args:
            session_id: Unique session identifier
            session_type: Type of session (audio_download, metadata_scrape, etc.)
            requests_count: Number of requests made
            data_bytes: Total data transferred in bytes
            duration_seconds: Session duration
            custom_cost: Custom cost override

        Returns:
            Total cost calculated for this session
        """
        try:
            if custom_cost is not None:
                total_cost = custom_cost
            else:
                # Calculate cost based on usage
                data_gb = data_bytes / (1024 * 1024 * 1024)  # Convert to GB

                request_cost = requests_count * self.DEFAULT_COSTS["proxy_request"]
                data_cost = data_gb * self.DEFAULT_COSTS["proxy_gb"]
                session_cost = self.DEFAULT_COSTS["residential_session"]

                total_cost = request_cost + data_cost + session_cost

            # Update session in database
            self.db.update_bright_data_session_cost(
                session_id=session_id,
                requests_count=requests_count,
                data_downloaded_bytes=data_bytes,
                cost=total_cost,
            )

            logger.info(f"Tracked cost ${total_cost:.4f} for session {session_id}")
            return total_cost

        except Exception as e:
            logger.error(f"Failed to track session cost: {e}")
            return 0.0

    def get_usage_summary(self, days: int = 30) -> dict[str, any]:
        """
        Get comprehensive usage summary for the last N days.

        Args:
            days: Number of days to include in summary

        Returns:
            Dictionary with usage statistics and costs
        """
        try:
            # Get overall statistics
            stats = self.db.get_processing_stats()
            cost_breakdown = self.db.get_cost_breakdown()

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get Bright Data specific costs
            bright_data_costs = cost_breakdown.get("bright_data_costs", [])
            total_bright_data_cost = sum(
                item["total_cost"] for item in bright_data_costs if item["total_cost"]
            )

            # Calculate daily average
            daily_avg = total_bright_data_cost / days if days > 0 else 0

            # Estimate monthly cost
            monthly_estimate = daily_avg * 30

            return {
                "summary": {
                    "period_days": days,
                    "total_videos_processed": stats.get("completed_videos", 0),
                    "total_bright_data_cost": total_bright_data_cost,
                    "average_cost_per_video": stats.get("average_cost_per_video", 0),
                    "daily_average_cost": daily_avg,
                    "monthly_estimated_cost": monthly_estimate,
                },
                "session_breakdown": bright_data_costs,
                "cost_trends": self._calculate_cost_trends(days),
                "optimization_suggestions": self._get_optimization_suggestions(
                    stats, bright_data_costs
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get usage summary: {e}")
            return {}

    def _calculate_cost_trends(self, days: int) -> dict[str, any]:
        """Calculate cost trends and patterns."""
        try:
            # This would require time-series data from the database
            # For now, return basic trend indicators
            return {
                "trend_direction": "stable",  # 'increasing', 'decreasing', 'stable'
                "cost_variance": "low",  # 'low', 'medium', 'high'
                "peak_usage_hours": "unknown",
                "note": "Detailed trend analysis requires time-series data collection",
            }
        except Exception as e:
            logger.error(f"Failed to calculate cost trends: {e}")
            return {}

    def _get_optimization_suggestions(
        self, stats: dict[str, any], cost_breakdown: list[dict[str, any]]
    ) -> list[str]:
        """Generate cost optimization suggestions."""
        suggestions = []

        try:
            avg_cost = stats.get("average_cost_per_video", 0)

            # Analyze cost patterns and suggest optimizations
            if avg_cost > 0.10:  # If cost per video > $0.10
                suggestions.append(
                    "High per-video cost detected. Consider enabling deduplication to avoid reprocessing."
                )

            # Check session type distribution
            session_costs = {
                item["session_type"]: item["total_cost"] for item in cost_breakdown
            }

            if (
                session_costs.get("audio_download", 0)
                > session_costs.get("metadata_scrape", 0) * 2
            ):
                suggestions.append(
                    "Audio downloads are major cost driver. Consider optimizing concurrent connections."
                )

            if len(cost_breakdown) > 0:
                suggestions.append(
                    "Regular cost monitoring enabled. Check monthly reports for budget planning."
                )
            else:
                suggestions.append(
                    "No Bright Data usage detected. Ensure proper session tracking is configured."
                )

        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            suggestions.append(
                "Enable detailed logging for better cost optimization insights."
            )

        return suggestions

    def check_budget_alerts(self, monthly_budget: float) -> dict[str, any]:
        """
        Check if usage is approaching budget limits.

        Args:
            monthly_budget: Monthly budget limit in USD

        Returns:
            Dictionary with alert status and recommendations
        """
        try:
            # Get current month usage
            today = datetime.utcnow()
            days_in_month = today.day
            usage_summary = self.get_usage_summary(days_in_month)

            current_spend = usage_summary["summary"]["total_bright_data_cost"]
            projected_monthly = usage_summary["summary"]["monthly_estimated_cost"]

            # Calculate alert thresholds
            alert_level = "green"  # green, yellow, red
            alert_message = "Budget usage is within normal limits"

            budget_percentage = (
                (current_spend / monthly_budget) * 100 if monthly_budget > 0 else 0
            )
            projected_percentage = (
                (projected_monthly / monthly_budget) * 100 if monthly_budget > 0 else 0
            )

            if projected_percentage > 100:
                alert_level = "red"
                alert_message = f"ALERT: Projected monthly cost (${projected_monthly:.2f}) exceeds budget (${monthly_budget:.2f})"
            elif projected_percentage > 80:
                alert_level = "yellow"
                alert_message = f"WARNING: Projected to use {projected_percentage:.1f}% of monthly budget"
            elif budget_percentage > 50:
                alert_level = "yellow"
                alert_message = (
                    f"NOTICE: Already used {budget_percentage:.1f}% of monthly budget"
                )

            return {
                "alert_level": alert_level,
                "alert_message": alert_message,
                "current_spend": current_spend,
                "monthly_budget": monthly_budget,
                "budget_percentage_used": budget_percentage,
                "projected_monthly_cost": projected_monthly,
                "projected_percentage": projected_percentage,
                "days_remaining_in_month": 30 - days_in_month,
                "recommendations": self._get_budget_recommendations(
                    alert_level, budget_percentage, projected_percentage
                ),
            }

        except Exception as e:
            logger.error(f"Failed to check budget alerts: {e}")
            return {
                "alert_level": "unknown",
                "alert_message": "Unable to check budget status",
                "error": str(e),
            }

    def _get_budget_recommendations(
        self, alert_level: str, budget_percentage: float, projected_percentage: float
    ) -> list[str]:
        """Get budget management recommendations based on alert level."""
        recommendations = []

        if alert_level == "red":
            recommendations.extend(
                [
                    "Immediate action required: Consider pausing non-essential processing",
                    "Review and optimize session usage patterns",
                    "Enable strict deduplication to prevent reprocessing",
                    "Consider increasing monthly budget if usage is business-critical",
                ]
            )
        elif alert_level == "yellow":
            recommendations.extend(
                [
                    "Monitor usage closely for remainder of month",
                    "Prioritize most important video processing tasks",
                    "Review cost optimization suggestions",
                    "Consider batch processing to optimize session costs",
                ]
            )
        else:
            recommendations.extend(
                [
                    "Usage is within normal limits",
                    "Continue regular monitoring",
                    "Consider setting up automated budget alerts",
                ]
            )

        return recommendations

    def generate_cost_report(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        format: str = "dict",
    ) -> dict[str, any] | str:
        """
        Generate comprehensive cost report.

        Args:
            start_date: Report start date (defaults to 30 days ago)
            end_date: Report end date (defaults to now)
            format: Output format ('dict', 'json', 'summary')

        Returns:
            Cost report in specified format
        """
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            days = (end_date - start_date).days
            usage_summary = self.get_usage_summary(days)

            report = {
                "report_metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "period_days": days,
                },
                "cost_summary": usage_summary["summary"],
                "session_breakdown": usage_summary["session_breakdown"],
                "cost_trends": usage_summary["cost_trends"],
                "optimization_suggestions": usage_summary["optimization_suggestions"],
            }

            if format == "json":
                return json.dumps(report, indent=2)
            elif format == "summary":
                return self._format_summary_report(report)
            else:
                return report

        except Exception as e:
            logger.error(f"Failed to generate cost report: {e}")
            return {"error": str(e)}

    def _format_summary_report(self, report: dict[str, any]) -> str:
        """Format report as human-readable summary."""
        try:
            report["cost_summary"]
            suggestions = report["optimization_suggestions"]

            report_text = """
BRIGHT DATA COST REPORT
{'-' * 50}
Period: {report['report_metadata']['period_days']} days
Generated: {report['report_metadata']['generated_at'][:19]}

USAGE SUMMARY:
• Videos Processed: {summary['total_videos_processed']}
• Total Cost: ${summary['total_bright_data_cost']:.4f}
• Average per Video: ${summary['average_cost_per_video']:.4f}
• Daily Average: ${summary['daily_average_cost']:.4f}
• Monthly Estimate: ${summary['monthly_estimated_cost']:.2f}

OPTIMIZATION SUGGESTIONS:
"""
            for i, suggestion in enumerate(suggestions, 1):
                report_text += f"{i}. {suggestion}\n"

            return report_text

        except Exception as e:
            logger.error(f"Failed to format summary report: {e}")
            return "Error formatting report"


# Convenience functions for easy integration
def track_video_processing_cost(
    video_id: str, session_id: str, requests: int = 1, data_mb: float = 0.0
) -> float:
    """Convenience function to track cost for video processing."""
    tracker = CostTracker()
    data_bytes = int(data_mb * 1024 * 1024)
    return tracker.track_session_cost(
        session_id=session_id,
        session_type="audio_download",
        requests_count=requests,
        data_bytes=data_bytes,
    )


def get_monthly_usage_report() -> dict[str, any]:
    """Convenience function to get current month usage report."""
    tracker = CostTracker()
    today = datetime.utcnow()
    return tracker.get_usage_summary(today.day)


def check_budget_status(monthly_budget: float) -> dict[str, any]:
    """Convenience function to check budget status."""
    tracker = CostTracker()
    return tracker.check_budget_alerts(monthly_budget)
