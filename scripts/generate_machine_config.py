#!/usr/bin/env python3
"""
Machine-Specific Configuration Generator

Detects hardware specifications and generates optimized configuration files
tailored to the specific machine's capabilities during installation.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

# Add src to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from knowledge_system.utils.hardware_detection import (
        HardwareDetector,
        PerformanceProfile,
    )
    from knowledge_system.utils.process_isolation import ProcessIsolationConfig
except ImportError as e:
    print(f"❌ Failed to import hardware detection: {e}")
    print("⚠️  Falling back to default configuration")
    sys.exit(1)


class MachineConfigGenerator:
    """Generates machine-specific configuration files."""

    def __init__(self):
        self.detector = HardwareDetector()
        self.specs = None

    def detect_hardware(self) -> dict[str, Any]:
        """Detect and return hardware specifications."""
        print("🔍 Detecting hardware specifications...")

        try:
            self.specs = self.detector.detect_hardware()

            print(f"✅ Detected Hardware:")
            print(
                f"   • CPU: {self.specs.cpu_cores} cores ({self.specs.chip_type.value if self.specs.chip_type else 'Unknown'})"
            )
            print(f"   • Memory: {self.specs.memory_gb:.1f}GB")
            print(
                f"   • GPU: {self.specs.gpu_cores} cores ({self.specs.gpu_type.value if self.specs.gpu_type else 'None'})"
            )
            print(
                f"   • Platform: {'Apple Silicon' if self.specs.is_apple_silicon else 'Intel/AMD'}"
            )

            return {
                "cpu_cores": self.specs.cpu_cores,
                "memory_gb": self.specs.memory_gb,
                "gpu_cores": self.specs.gpu_cores,
                "chip_type": self.specs.chip_type.value
                if self.specs.chip_type
                else None,
                "gpu_type": self.specs.gpu_type.value if self.specs.gpu_type else None,
                "is_apple_silicon": self.specs.is_apple_silicon,
                "max_concurrent": self.specs.max_concurrent_transcriptions,
                "optimal_batch": self.specs.optimal_batch_size,
                "recommended_model": self.specs.recommended_whisper_model,
                "recommended_device": self.specs.recommended_device,
            }

        except Exception as e:
            print(f"❌ Hardware detection failed: {e}")
            return self._get_fallback_specs()

    def _get_fallback_specs(self) -> dict[str, Any]:
        """Provide safe fallback specifications for unknown hardware."""
        import psutil

        cpu_cores = os.cpu_count() or 2
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # More intelligent fallback based on detected specs
        if memory_gb <= 4:
            # Very low-end machine - be extremely conservative
            max_concurrent = 1
            batch_size = 8
            model = "tiny"  # Use smallest model
            print(
                f"⚠️  Low-memory system detected ({memory_gb:.1f}GB) - using minimal settings"
            )
        elif memory_gb < 8:
            # Low-end machine - conservative but functional
            max_concurrent = max(1, cpu_cores // 4)  # Very conservative
            batch_size = 8
            model = "base"
            print(
                f"⚠️  Limited-memory system detected ({memory_gb:.1f}GB) - using conservative settings"
            )
        else:
            # Normal fallback for unknown but decent hardware
            max_concurrent = max(1, min(4, cpu_cores // 2))
            batch_size = 16
            model = "base"
            print(f"⚠️  Using fallback detection for normal system")

        print(f"   • CPU: {cpu_cores} cores (detected)")
        print(f"   • Memory: {memory_gb:.1f}GB (detected)")
        print(f"   • Max concurrent: {max_concurrent}")
        print(f"   • Model: {model}")

        return {
            "cpu_cores": cpu_cores,
            "memory_gb": memory_gb,
            "gpu_cores": 0,
            "chip_type": None,
            "gpu_type": None,
            "is_apple_silicon": False,
            "max_concurrent": max_concurrent,
            "optimal_batch": batch_size,
            "recommended_model": model,
            "recommended_device": "cpu",
        }

    def generate_performance_profile(self, hardware_specs: dict[str, Any]) -> str:
        """Determine the best performance profile for this machine."""
        memory_gb = hardware_specs["memory_gb"]
        cpu_cores = hardware_specs["cpu_cores"]
        is_apple_silicon = hardware_specs.get("is_apple_silicon", False)

        # Machine categorization for automatic profile selection
        # Apple Silicon adjustments: more efficient, so lower thresholds for higher performance
        if is_apple_silicon:
            memory_threshold_high = 16  # Apple Silicon efficient with memory
            memory_threshold_ultra = 64  # Ultra performance threshold
            memory_threshold_extreme = 128  # Extreme performance threshold
            cpu_threshold_high = 8  # Fewer cores needed due to efficiency
            cpu_threshold_ultra = 16  # Ultra performance threshold
            cpu_threshold_extreme = 20  # Extreme performance threshold
        else:
            memory_threshold_high = 32  # Intel/AMD needs more resources
            memory_threshold_ultra = 64  # Ultra performance threshold
            memory_threshold_extreme = 128  # Extreme performance threshold
            cpu_threshold_high = 12  # Higher threshold for Intel/AMD
            cpu_threshold_ultra = 16  # Ultra performance threshold
            cpu_threshold_extreme = 24  # Extreme performance threshold

        if memory_gb <= 4 or cpu_cores <= 2:
            return "LEVEL_1"  # Very low-end machines (2-4GB, dual-core)
        elif memory_gb < 8 or cpu_cores < 4:
            return "LEVEL_2"  # Low-end laptops (4-8GB, 2-4 cores) - avoid overwhelming them
        elif (
            memory_gb >= memory_threshold_extreme and cpu_cores >= cpu_threshold_extreme
        ):
            return "LEVEL_6"  # Server-class machines (128GB+, 20-24+ cores)
        elif memory_gb >= memory_threshold_ultra and cpu_cores >= cpu_threshold_ultra:
            return "LEVEL_5"  # Workstation-class machines (64GB+, 16+ cores)
        elif memory_gb >= memory_threshold_high and cpu_cores >= cpu_threshold_high:
            return (
                "LEVEL_4"  # High-end machines (adjusted for Apple Silicon efficiency)
            )
        else:
            return "LEVEL_3"  # Most modern laptops

    def _get_timeout_for_machine(self, hardware_specs: dict[str, Any]) -> int:
        """Get appropriate timeout based on machine capabilities."""
        memory_gb = hardware_specs["memory_gb"]
        cpu_cores = hardware_specs["cpu_cores"]

        if memory_gb <= 4 or cpu_cores <= 2:
            return 900  # 15 minutes for very slow machines
        elif memory_gb < 8 or cpu_cores < 4:
            return 600  # 10 minutes for slow machines
        else:
            return 300  # 5 minutes for normal machines

    def generate_config(self, hardware_specs: dict[str, Any]) -> dict[str, Any]:
        """Generate machine-optimized configuration."""

        # Determine performance profile
        performance_profile = self.generate_performance_profile(hardware_specs)

        print(f"📊 Machine Category: {performance_profile}")
        print(f"✅ Recommended Settings:")
        print(f"   • Max Concurrent Files: {hardware_specs['max_concurrent']}")
        print(f"   • Batch Size: {hardware_specs['optimal_batch']}")
        print(f"   • Whisper Model: {hardware_specs['recommended_model']}")
        print(f"   • Device: {hardware_specs['recommended_device']}")

        # Base configuration template
        config = {
            # Automatically detected hardware info (for debugging/support)
            "_machine_info": {
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "cpu_cores": hardware_specs["cpu_cores"],
                "memory_gb": hardware_specs["memory_gb"],
                "chip_type": hardware_specs["chip_type"],
                "gpu_type": hardware_specs["gpu_type"],
                "performance_profile": performance_profile,
            },
            # Performance settings optimized for this machine
            "performance": {
                "profile": performance_profile,
            },
            # Thread management optimized for this CPU
            "thread_management": {
                "omp_num_threads": max(1, min(8, hardware_specs["cpu_cores"] // 2)),
                "max_concurrent_files": hardware_specs["max_concurrent"],
                "per_process_thread_limit": max(1, hardware_specs["cpu_cores"] // 4),
                "enable_parallel_processing": hardware_specs["max_concurrent"] > 1,
                "sequential_processing": hardware_specs["max_concurrent"] == 1,
                "tokenizers_parallelism": False,  # Avoid warnings
                "pytorch_enable_mps_fallback": True,
            },
            # Transcription settings optimized for this hardware
            "transcription": {
                "whisper_model": hardware_specs["recommended_model"],
                "use_gpu": hardware_specs["recommended_device"] != "cpu",
                "diarization": hardware_specs["memory_gb"]
                >= 8,  # Only enable if enough RAM
                "min_words": 50,
                "use_whisper_cpp": hardware_specs[
                    "is_apple_silicon"
                ],  # Use Core ML on Apple Silicon
                "batch_size": hardware_specs["optimal_batch"],
                "device": hardware_specs["recommended_device"],
            },
            # Processing limits based on available resources
            "processing": {
                "batch_size": min(
                    hardware_specs["optimal_batch"], 20
                ),  # Cap for stability
                "concurrent_jobs": hardware_specs[
                    "max_concurrent"
                ],  # Use detected capability
                "retry_attempts": 3,
                "timeout_seconds": self._get_timeout_for_machine(hardware_specs),
            },
            # API keys placeholder (user will fill these)
            "api_keys": {
                "openai_api_key": "${OPENAI_API_KEY}",
                "anthropic_api_key": "${ANTHROPIC_API_KEY}",
                "youtube_api_key": "${YOUTUBE_API_KEY}",
                "huggingface_token": "${HUGGINGFACE_HUB_TOKEN}",
            },
            # LLM settings with conservative defaults
            "llm": {
                "provider": "openai",
                "model": "gpt-4o-mini",  # More affordable default
                "max_tokens": 10000,
                "temperature": 0.1,
            },
            # Local LLM fallback
            "local_config": {
                "base_url": "http://localhost:11434",
                "model": "qwen2.5:32b-instruct-q6_K"
                if hardware_specs["memory_gb"] >= 32
                else "qwen2.5:14b-instruct-q6_K",
                "max_tokens": 10000,
                "temperature": 0.1,
            },
        }

        # Apply machine-specific optimizations
        if hardware_specs["memory_gb"] < 6:
            # Ultra-conservative settings for low-memory machines
            print("⚠️  Low memory detected - applying ultra-conservative settings")
            config["thread_management"]["max_concurrent_files"] = 1
            config["thread_management"]["sequential_processing"] = True
            config["thread_management"]["enable_parallel_processing"] = False
            config["transcription"]["whisper_model"] = "tiny"  # Smallest model
            config["transcription"]["diarization"] = False  # Disable to save memory
            config["transcription"]["batch_size"] = 8
            config["processing"]["concurrent_jobs"] = 1
            config["processing"][
                "timeout_seconds"
            ] = 900  # Extra time for slow processing
            config["local_config"]["model"] = "phi3:mini"  # Use smallest local model

        elif hardware_specs["memory_gb"] < 16:
            # Mid-range laptops (8-16GB) - slightly conservative
            print("⚙️  Mid-range system detected - applying balanced settings")
            config["transcription"][
                "diarization"
            ] = False  # Still disable diarization to be safe
            config["local_config"][
                "model"
            ] = "qwen2.5:7b-instruct-q6_K"  # Smaller model
            config["thread_management"]["max_concurrent_files"] = min(
                4, hardware_specs["max_concurrent"]
            )

        elif hardware_specs["memory_gb"] >= 32 and hardware_specs["cpu_cores"] >= 10:
            # High-end machine optimizations
            print("🚀 High-end machine detected - enabling performance optimizations")
            config["transcription"]["whisper_model"] = hardware_specs[
                "recommended_model"
            ]  # Use detected model
            config["transcription"]["batch_size"] = hardware_specs[
                "optimal_batch"
            ]  # Use full detected batch size
            config["thread_management"]["max_concurrent_files"] = hardware_specs[
                "max_concurrent"
            ]  # Use full detected concurrency

        # Apple Silicon specific optimizations
        if hardware_specs["is_apple_silicon"]:
            print("🍎 Apple Silicon detected - enabling Core ML optimizations")
            config["transcription"]["use_whisper_cpp"] = True
            config["transcription"]["device"] = "mps"

        return config

    def save_config(self, config: dict[str, Any], output_path: str) -> bool:
        """Save the generated configuration to a YAML file."""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Add header comment
            header = f"""# Machine-Optimized Configuration for Knowledge Chipper
# Generated automatically during installation
# Hardware: {config['_machine_info']['cpu_cores']} cores, {config['_machine_info']['memory_gb']:.1f}GB RAM
# Profile: {config['_machine_info']['performance_profile']}
# Generated: {config['_machine_info']['generated_at']}

"""

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(header)
                yaml.dump(
                    config, f, default_flow_style=False, indent=2, allow_unicode=True
                )

            print(f"✅ Configuration saved to: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return False


def main():
    """Main entry point for configuration generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate machine-specific configuration"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="config/settings.yaml",
        help="Output path for configuration file",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing configuration file",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show configuration without saving"
    )

    args = parser.parse_args()

    # Check if config already exists
    output_path = Path(args.output)
    if output_path.exists() and not args.force and not args.dry_run:
        print(f"⚠️  Configuration file already exists: {output_path}")
        print("   Use --force to overwrite or --dry-run to preview")
        sys.exit(1)

    # Generate configuration
    generator = MachineConfigGenerator()
    hardware_specs = generator.detect_hardware()
    config = generator.generate_config(hardware_specs)

    if args.dry_run:
        print("\n📋 Generated Configuration (dry run):")
        print(yaml.dump(config, default_flow_style=False, indent=2))
    else:
        success = generator.save_config(config, args.output)
        if success:
            print(f"\n🎉 Machine-optimized configuration created!")
            print(f"   Your system is configured for optimal performance")
            print(f"   You can adjust these settings later in: {args.output}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
