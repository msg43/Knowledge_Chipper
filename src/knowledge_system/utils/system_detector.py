#!/usr/bin/env python3
"""
System Capability Detection

Analyzes the user's system to recommend appropriate AI model tiers.
Considers RAM, storage space, CPU capabilities, and system age.
"""

import platform
import shutil
import subprocess
from pathlib import Path

import psutil


class SystemCapabilityDetector:
    """Detect system capabilities for smart model recommendations."""

    def __init__(self):
        self.system_info = self._gather_system_info()

    def _gather_system_info(self) -> dict:
        """Gather comprehensive system information."""
        info = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "cpu_count": psutil.cpu_count(),
            "available_storage_gb": self._get_available_storage(),
            "is_apple_silicon": self._is_apple_silicon(),
            "macos_version": self._get_macos_version(),
            "performance_tier": None,  # Will be calculated
        }

        # Calculate performance tier
        info["performance_tier"] = self._calculate_performance_tier(info)

        return info

    def _get_available_storage(self) -> float:
        """Get available storage space in GB."""
        try:
            # Check storage on the home directory (most relevant for user)
            home_path = Path.home()
            stats = shutil.disk_usage(home_path)
            available_gb = stats.free / (1024**3)
            return round(available_gb, 1)
        except Exception:
            return 0.0

    def _is_apple_silicon(self) -> bool:
        """Detect if running on Apple Silicon (M1/M2/M3)."""
        try:
            if platform.system() != "Darwin":
                return False

            # Check processor info
            processor = platform.processor().lower()
            if "apple" in processor or platform.machine() == "arm64":
                return True

            # Alternative check using system_profiler
            try:
                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                return (
                    "Apple" in result.stdout
                    and "M1" in result.stdout
                    or "M2" in result.stdout
                    or "M3" in result.stdout
                )
            except Exception:
                return platform.machine() == "arm64"

        except Exception:
            return False

    def _get_macos_version(self) -> tuple[int, int]:
        """Get macOS version as (major, minor)."""
        try:
            if platform.system() != "Darwin":
                return (0, 0)

            version_str = platform.mac_ver()[0]
            parts = version_str.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            return (major, minor)
        except Exception:
            return (0, 0)

    def _calculate_performance_tier(self, info: dict) -> str:
        """Calculate system performance tier based on specs."""
        ram_gb = info["ram_gb"]
        storage_gb = info["available_storage_gb"]
        cpu_count = info["cpu_count"]
        is_apple_silicon = info["is_apple_silicon"]

        # High-end system criteria
        if ram_gb >= 32 and storage_gb >= 50 and (cpu_count >= 8 or is_apple_silicon):
            return "high"

        # Mid-range system criteria
        elif ram_gb >= 16 and storage_gb >= 20 and cpu_count >= 4:
            return "medium"

        # Low-end system
        else:
            return "low"

    def get_model_recommendations(self) -> dict:
        """Get model recommendations based on system capabilities."""
        performance_tier = self.system_info["performance_tier"]
        ram_gb = self.system_info["ram_gb"]
        storage_gb = self.system_info["available_storage_gb"]
        is_apple_silicon = self.system_info["is_apple_silicon"]

        recommendations = {
            "recommended_tier": "base",
            "can_run_premium": False,
            "warnings": [],
            "benefits": [],
            "storage_note": "",
            "performance_explanation": "",
        }

        if performance_tier == "high":
            recommendations.update(
                {
                    "recommended_tier": "premium",
                    "can_run_premium": True,
                    "benefits": [
                        "🚀 Your system can handle the premium models excellently",
                        "🎯 Best transcription quality with Whisper Large",
                        "🧠 Advanced AI reasoning with 30B parameter model",
                        "⚡ Fast processing with your high-end hardware",
                    ],
                    "performance_explanation": f"With {ram_gb}GB RAM and {self.system_info['cpu_count']} CPU cores, you have excellent performance capability.",
                }
            )

            if storage_gb < 25:
                recommendations["warnings"].append(
                    f"⚠️ Only {storage_gb}GB available storage. Premium models need ~20GB."
                )
                recommendations["recommended_tier"] = "base"
                recommendations["can_run_premium"] = False

        elif performance_tier == "medium":
            recommendations.update(
                {
                    "recommended_tier": "base",
                    "can_run_premium": storage_gb >= 25 and ram_gb >= 16,
                    "benefits": [
                        "✅ Base models will run smoothly on your system",
                        "🎤 Good transcription quality with Whisper Base",
                        "💬 Responsive AI with 3B parameter model",
                        "⚡ Quick startup and processing",
                    ],
                    "performance_explanation": f"Your system ({ram_gb}GB RAM, {self.system_info['cpu_count']} cores) is well-suited for base models.",
                }
            )

            if recommendations["can_run_premium"]:
                recommendations["benefits"].append(
                    "🚀 Premium models available if you want maximum quality"
                )
            else:
                if storage_gb < 25:
                    recommendations["warnings"].append(
                        f"💾 {storage_gb}GB available storage is tight for premium models (need ~20GB)"
                    )
                if ram_gb < 16:
                    recommendations["warnings"].append(
                        f"🐏 {ram_gb}GB RAM may struggle with largest models"
                    )

        else:  # low performance
            recommendations.update(
                {
                    "recommended_tier": "base",
                    "can_run_premium": False,
                    "benefits": [
                        "✅ Base models optimized for your system",
                        "📱 Efficient performance on modest hardware",
                        "💾 Reasonable storage requirements (~3GB)",
                        "⚡ Still excellent functionality",
                    ],
                    "warnings": [
                        "💡 Premium models may be slow on this system",
                        f"🐏 {ram_gb}GB RAM is sufficient for base models",
                    ],
                    "performance_explanation": f"Base models are the best choice for your system configuration.",
                }
            )

        # Storage recommendations
        if storage_gb < 5:
            recommendations[
                "storage_note"
            ] = f"❌ Very low storage ({storage_gb}GB). Consider freeing space first."
            recommendations["warnings"].append("💾 Critically low storage space")
        elif storage_gb < 10:
            recommendations[
                "storage_note"
            ] = f"⚠️ Limited storage ({storage_gb}GB). Base models recommended."
        elif storage_gb >= 25:
            recommendations[
                "storage_note"
            ] = f"✅ Plenty of storage ({storage_gb}GB) for any model tier."
        else:
            recommendations["storage_note"] = f"📦 {storage_gb}GB storage available."

        # Apple Silicon specific benefits
        if is_apple_silicon:
            recommendations["benefits"].append(
                "🍎 Apple Silicon provides excellent AI performance"
            )

        return recommendations

    def get_system_summary(self) -> str:
        """Get a human-readable system summary."""
        info = self.system_info

        # Build system description
        system_parts = []

        if info["is_apple_silicon"]:
            system_parts.append("Apple Silicon Mac")
        else:
            system_parts.append(f"{info['machine']} processor")

        system_parts.append(f"{info['ram_gb']}GB RAM")
        system_parts.append(f"{info['cpu_count']} CPU cores")
        system_parts.append(f"{info['available_storage_gb']}GB available storage")

        tier_desc = {
            "high": "High-end system",
            "medium": "Mid-range system",
            "low": "Entry-level system",
        }

        performance = tier_desc.get(info["performance_tier"], "Unknown system")

        return f"{performance}: {', '.join(system_parts)}"

    def get_download_time_estimate(self, size_gb: float) -> str:
        """Estimate download time based on typical connection speeds."""
        # Assume typical broadband speeds
        speeds = [
            (100, "Very fast broadband"),  # 100 Mbps
            (50, "Fast broadband"),  # 50 Mbps
            (25, "Good broadband"),  # 25 Mbps
            (10, "Basic broadband"),  # 10 Mbps
            (5, "Slow connection"),  # 5 Mbps
        ]

        estimates = []
        for speed_mbps, desc in speeds:
            # Convert to practical download speed (accounting for overhead)
            practical_speed = speed_mbps * 0.8  # 80% efficiency
            speed_gbps = practical_speed / 8 / 1000  # Convert to GB/s

            time_seconds = size_gb / speed_gbps
            time_minutes = time_seconds / 60

            if time_minutes < 1:
                time_str = f"{int(time_seconds)}s"
            elif time_minutes < 60:
                time_str = f"{int(time_minutes)}m"
            else:
                time_str = f"{int(time_minutes/60)}h {int(time_minutes%60)}m"

            estimates.append(f"{desc}: ~{time_str}")

        return "\n".join(estimates)


def get_system_recommendations() -> dict:
    """Get system recommendations for model selection."""
    detector = SystemCapabilityDetector()
    return {
        "system_info": detector.system_info,
        "recommendations": detector.get_model_recommendations(),
        "system_summary": detector.get_system_summary(),
    }


if __name__ == "__main__":
    # Test the system detection
    detector = SystemCapabilityDetector()

    print("🖥️ System Detection Results")
    print("=" * 50)
    print(detector.get_system_summary())
    print()

    recommendations = detector.get_model_recommendations()
    print(f"📦 Recommended Tier: {recommendations['recommended_tier'].title()}")
    print(f"🚀 Can Run Premium: {recommendations['can_run_premium']}")
    print()

    print("✅ Benefits:")
    for benefit in recommendations["benefits"]:
        print(f"   {benefit}")
    print()

    if recommendations["warnings"]:
        print("⚠️ Considerations:")
        for warning in recommendations["warnings"]:
            print(f"   {warning}")
        print()

    print(f"💾 Storage: {recommendations['storage_note']}")
    print(f"🎯 {recommendations['performance_explanation']}")
    print()

    # Show download estimates
    print("📥 Download Time Estimates:")
    print("Base Tier (3GB):")
    print(detector.get_download_time_estimate(3.0))
    print("\nPremium Tier (18GB):")
    print(detector.get_download_time_estimate(18.0))
