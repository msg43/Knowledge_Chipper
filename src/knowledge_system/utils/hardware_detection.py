#!/usr/bin/env python3
"""
Hardware Detection Utilities

Provides hardware detection capabilities for the knowledge system,
enabling automatic optimization based on system specifications.
"""

import json
import platform
import subprocess
from typing import Any, Dict, Optional


def detect_hardware_specs() -> dict[str, Any]:
    """
    Detect current hardware specifications.

    Returns:
        Dictionary containing hardware information:
        - chip_type: CPU/chip type (e.g., "M3 Ultra", "Intel")
        - memory_gb: Total RAM in GB
        - cpu_cores: Number of CPU cores
        - platform: Operating system platform
    """
    try:
        if platform.system() == "Darwin":  # macOS
            return _detect_macos_hardware()
        else:
            return _detect_generic_hardware()
    except Exception as e:
        # Return safe defaults if detection fails
        return {
            "chip_type": "Unknown",
            "memory_gb": 16,
            "cpu_cores": 8,
            "platform": platform.system(),
            "detection_error": str(e),
        }


def _detect_macos_hardware() -> dict[str, Any]:
    """Detect hardware on macOS using system_profiler."""
    try:
        # Get hardware information using system_profiler
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise Exception("system_profiler failed")

        data = json.loads(result.stdout)
        hardware_info = data["SPHardwareDataType"][0]

        # Extract chip type
        chip_name = hardware_info.get("chip_type", "").lower()

        # Extract memory
        memory_str = hardware_info.get("physical_memory", "16 GB")
        memory_gb = int(memory_str.split()[0])

        # Extract CPU cores
        cpu_cores = int(hardware_info.get("number_processors", "8"))

        return {
            "chip_type": chip_name,
            "memory_gb": memory_gb,
            "cpu_cores": cpu_cores,
            "platform": "macOS",
            "detection_method": "system_profiler",
        }

    except Exception as e:
        # Fallback to sysctl for basic info
        try:
            return _detect_macos_hardware_fallback()
        except Exception:
            return {
                "chip_type": "Unknown",
                "memory_gb": 16,
                "cpu_cores": 8,
                "platform": "macOS",
                "detection_error": str(e),
            }


def _detect_macos_hardware_fallback() -> dict[str, Any]:
    """Fallback hardware detection for macOS using sysctl."""
    try:
        # Get memory using sysctl
        memory_result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        )
        memory_bytes = int(memory_result.stdout.strip())
        memory_gb = memory_bytes // (1024**3)

        # Get CPU info
        cpu_result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=True,
        )
        cpu_info = cpu_result.stdout.strip()

        # Get CPU cores
        cores_result = subprocess.run(
            ["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, check=True
        )
        cpu_cores = int(cores_result.stdout.strip())

        return {
            "chip_type": cpu_info.lower(),
            "memory_gb": memory_gb,
            "cpu_cores": cpu_cores,
            "platform": "macOS",
            "detection_method": "sysctl_fallback",
        }

    except Exception as e:
        return {
            "chip_type": "Unknown",
            "memory_gb": 16,
            "cpu_cores": 8,
            "platform": "macOS",
            "detection_error": f"sysctl fallback failed: {e}",
        }


def _detect_generic_hardware() -> dict[str, Any]:
    """Detect hardware on generic systems."""
    try:
        import psutil

        # Get memory
        memory = psutil.virtual_memory()
        memory_gb = memory.total // (1024**3)

        # Get CPU cores
        cpu_cores = psutil.cpu_count(logical=True)

        # Get CPU info
        try:
            cpu_info = platform.processor()
        except:
            cpu_info = "Unknown"

        return {
            "chip_type": cpu_info.lower(),
            "memory_gb": memory_gb,
            "cpu_cores": cpu_cores,
            "platform": platform.system(),
            "detection_method": "psutil",
        }

    except ImportError:
        # Fallback without psutil
        return {
            "chip_type": "Unknown",
            "memory_gb": 16,
            "cpu_cores": 8,
            "platform": platform.system(),
            "detection_method": "platform_fallback",
        }
    except Exception as e:
        return {
            "chip_type": "Unknown",
            "memory_gb": 16,
            "cpu_cores": 8,
            "platform": platform.system(),
            "detection_error": str(e),
        }


def get_optimization_recommendations(hardware_specs: dict[str, Any]) -> dict[str, Any]:
    """
    Get optimization recommendations based on hardware specs.

    Args:
        hardware_specs: Hardware specifications from detect_hardware_specs()

    Returns:
        Dictionary with optimization recommendations
    """
    memory_gb = hardware_specs.get("memory_gb", 16)
    cpu_cores = hardware_specs.get("cpu_cores", 8)
    chip_type = hardware_specs.get("chip_type", "").lower()

    # Determine optimization level
    if memory_gb >= 64 and ("ultra" in chip_type or "max" in chip_type):
        optimization_level = "Maximum"
        model_type = "Qwen2.5-14B-instruct FP16"
        parallelization_level = "Aggressive"
        recommended_downloads = 4
        recommended_mining = 8
        recommended_evaluation = 6
        model_ram_usage = 32.0
    elif memory_gb >= 32 and ("max" in chip_type or "pro" in chip_type):
        optimization_level = "High"
        model_type = "Qwen2.5-14B-instruct FP16"
        parallelization_level = "Moderate"
        recommended_downloads = 3
        recommended_mining = 6
        recommended_evaluation = 4
        model_ram_usage = 32.0
    elif memory_gb >= 16:
        optimization_level = "Balanced"
        model_type = "Qwen2.5-7b-instruct"
        parallelization_level = "Conservative"
        recommended_downloads = 2
        recommended_mining = 4
        recommended_evaluation = 3
        model_ram_usage = 8.0
    else:
        optimization_level = "Basic"
        model_type = "Qwen2.5-3b-instruct"
        parallelization_level = "Minimal"
        recommended_downloads = 1
        recommended_mining = 2
        recommended_evaluation = 2
        model_ram_usage = 4.0

    return {
        "optimization_level": optimization_level,
        "model_type": model_type,
        "parallelization_level": parallelization_level,
        "recommended_settings": {
            "max_parallel_downloads": recommended_downloads,
            "max_parallel_mining": recommended_mining,
            "max_parallel_evaluation": recommended_evaluation,
        },
        "resource_usage": {
            "model_ram_gb": model_ram_usage,
            "available_ram_gb": memory_gb
            - model_ram_usage
            - 2.0,  # 2GB system overhead
            "total_ram_gb": memory_gb,
            "cpu_cores": cpu_cores,
        },
        "performance_estimate": {
            "expected_speedup": "4-6x"
            if optimization_level in ["Maximum", "High"]
            else "2-3x",
            "parallelization_efficiency": "90%+"
            if optimization_level in ["Maximum", "High"]
            else "70%+",
        },
    }
