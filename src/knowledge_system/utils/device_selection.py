""" Intelligent device selection for optimal performance.
Intelligent device selection for optimal performance.

This module provides smart device selection that considers hardware capabilities,
workload requirements, and user preferences to choose the best processing device.
"""

import os
from typing import Any, Dict, Optional

from ..logger import get_logger
from .hardware_detection import CUDASpecs, GPUType, get_hardware_detector

logger = get_logger(__name__)


def select_optimal_device(
    preference: str = "auto",
    workload_type: str = "transcription",
    model_size: str = "base",
    batch_size: int = 16,
    force_device: str | None = None,
) -> str:
    """ Select the optimal device for processing based on hardware and workload.
    Select the optimal device for processing based on hardware and workload.

    Args:
        preference: User preference ("auto", "cuda", "mps", "cpu")
        workload_type: Type of workload ("transcription", "summarization", "general")
        model_size: Model size requirement ("tiny", "base", "small", "medium", "large", "large-v3")
        batch_size: Expected batch size
        force_device: Force a specific device (overrides all logic)

    Returns:
        Device string for PyTorch/Whisper
    """ if force_device:.
    
    if force_device:
        logger.info(f"Device selection forced to: {force_device}")
        return force_device

    # If not auto, respect user preference but validate capability
    if preference != "auto":
        if _validate_device_capability(preference, model_size, batch_size):
            logger.info(f"Using user preference: {preference}")
            return preference
        else:
            logger.warning(
                f"User preference '{preference}' not optimal for workload, falling back to auto selection"
            )

    # Auto selection logic
    detector = get_hardware_detector()
    specs = detector.detect_hardware()

    logger.info(
        f"Auto-selecting device for {workload_type} workload with {model_size} model"
    )

    # CUDA gets highest priority for suitable workloads
    if specs.supports_cuda and specs.cuda_specs:
        cuda_device = _evaluate_cuda_suitability(
            specs.cuda_specs, model_size, batch_size, workload_type
        )
        if cuda_device:
            logger.info(
                f"Selected CUDA: {specs.cuda_specs.gpu_names[0]} ({specs.cuda_specs.total_vram_gb:.1f}GB VRAM)"
            )
            return cuda_device

    # Apple Silicon MPS gets second priority
    if specs.supports_mps:
        if _evaluate_mps_suitability(specs, model_size, batch_size, workload_type):
            logger.info(
                f"Selected MPS: {specs.chip_type.value} GPU ({specs.gpu_cores} cores)"
            )
            return "mps"

    # AMD ROCm support (basic)
    if specs.supports_rocm:
        logger.info("Selected ROCm for AMD GPU acceleration")
        return "auto"  # Let PyTorch handle ROCm detection

    # Fallback to CPU
    logger.info("Selected CPU (no suitable GPU acceleration found)")
    return "cpu"


def _validate_device_capability(device: str, model_size: str, batch_size: int) -> bool:
    """ Validate that a device can handle the specified workload.""".
    detector = get_hardware_detector()
    specs = detector.detect_hardware()

    if device == "cuda":
        if not specs.supports_cuda or not specs.cuda_specs:
            logger.warning("CUDA device requested but not available")
            return False
        return (
            _evaluate_cuda_suitability(
                specs.cuda_specs, model_size, batch_size, "validation"
            )
            is not None
        )

    elif device == "mps":
        if not specs.supports_mps:
            logger.warning("MPS device requested but not available")
            return False
        return _evaluate_mps_suitability(specs, model_size, batch_size, "validation")

    elif device == "cpu":
        return True  # CPU is always available

    elif device == "auto":
        return True  # Auto is always valid

    else:
        logger.warning(f"Unknown device: {device}")
        return False


def _evaluate_cuda_suitability(
    cuda_specs: CUDASpecs, model_size: str, batch_size: int, workload_type: str
) -> str | None:
    """ Evaluate if CUDA is suitable for the workload and return device string.""".

    # Estimate VRAM requirements (rough estimates)
    vram_requirements = {
        "tiny": 1.0,
        "base": 1.5,
        "small": 2.5,
        "medium": 5.0,
        "large": 10.0,
        "large-v3": 10.0,
    }

    base_vram_needed = vram_requirements.get(model_size, 5.0)

    # Adjust for batch size (rough linear scaling)
    estimated_vram_needed = base_vram_needed * (1 + (batch_size - 16) * 0.1)

    # Add safety margin
    estimated_vram_needed *= 1.3

    # Check if any GPU has enough VRAM
    if cuda_specs.total_vram_gb < estimated_vram_needed:
        logger.debug(
            f"CUDA GPUs have {cuda_specs.total_vram_gb:.1f}GB VRAM, need ~{estimated_vram_needed:.1f}GB for {model_size} model"
        )
        return None

    # Prefer CUDA for larger models and higher batch sizes
    if model_size in ["large", "large-v3"] or batch_size >= 32:
        if cuda_specs.supports_tensor_cores:
            logger.debug("CUDA preferred for large model with Tensor Core support")
            return "cuda"
        elif cuda_specs.total_vram_gb >= 8.0:
            logger.debug("CUDA preferred for large model with high VRAM")
            return "cuda"

    # Use CUDA for medium workloads if we have good hardware
    if cuda_specs.total_vram_gb >= 6.0:
        logger.debug("CUDA selected for good VRAM availability")
        return "cuda"

    # For smaller models and lower VRAM, let PyTorch decide
    if cuda_specs.total_vram_gb >= 4.0:
        logger.debug("CUDA available but using auto for smaller workload")
        return "auto"

    # Not enough VRAM
    logger.debug(
        f"CUDA GPUs insufficient for workload (need {estimated_vram_needed:.1f}GB, have {cuda_specs.total_vram_gb:.1f}GB)"
    )
    return None


def _evaluate_mps_suitability(
    specs, model_size: str, batch_size: int, workload_type: str
) -> bool:
    """ Evaluate if MPS is suitable for the workload.""".

    # MPS is generally good for Apple Silicon
    if not specs.is_apple_silicon:
        return False

    # Check memory constraints (Apple Silicon uses unified memory)
    memory_requirements = {
        "tiny": 4,
        "base": 8,
        "small": 12,
        "medium": 16,
        "large": 24,
        "large-v3": 24,
    }

    min_memory_needed = memory_requirements.get(model_size, 16)

    # Adjust for batch size
    estimated_memory_needed = min_memory_needed + (batch_size // 8) * 2

    if specs.memory_gb < estimated_memory_needed:
        logger.debug(
            f"MPS needs {estimated_memory_needed}GB RAM, have {specs.memory_gb}GB"
        )
        return False

    # MPS is preferred for Apple Silicon in most cases
    logger.debug("MPS suitable for Apple Silicon")
    return True


def get_device_recommendations(workload_type: str = "transcription") -> dict[str, Any]:
    """ Get device recommendations and capability information.
    Get device recommendations and capability information.

    Returns detailed information about available devices and their suitability
    for different workloads.
    """ detector = get_hardware_detector().
    
    detector = get_hardware_detector()
    specs = detector.detect_hardware()

    recommendations: dict[str, Any] = {
        "primary_device": select_optimal_device("auto", workload_type),
        "available_devices": [],
        "device_info": {},
        "performance_notes": [],
    }

    # Always available
    recommendations["available_devices"].append("cpu")
    recommendations["device_info"]["cpu"] = {
        "name": "CPU",
        "description": f"{specs.cpu_cores} cores, {specs.memory_gb}GB RAM",
        "suitable_for": ["small models", "low batch sizes", "compatibility"],
        "performance": "baseline",
    }

    # CUDA information
    if specs.supports_cuda and specs.cuda_specs:
        recommendations["available_devices"].append("cuda")
        gpu_names = ", ".join(specs.cuda_specs.gpu_names)
        recommendations["device_info"]["cuda"] = {
            "name": f"NVIDIA CUDA ({specs.cuda_specs.gpu_count} GPU{'s' if specs.cuda_specs.gpu_count > 1 else ''})",
            "description": f"{gpu_names}, {specs.cuda_specs.total_vram_gb:.1f}GB VRAM total",
            "suitable_for": ["large models", "high batch sizes", "maximum performance"],
            "performance": "high" if specs.cuda_specs.total_vram_gb >= 8 else "medium",
            "features": [],
        }

        if specs.cuda_specs.supports_tensor_cores:
            recommendations["device_info"]["cuda"]["features"].append(
                "Tensor Cores (mixed precision)"
            )

        if specs.cuda_specs.total_vram_gb >= 16:
            recommendations["performance_notes"].append(
                "High VRAM enables large-v3 model with large batch sizes"
            )
        elif specs.cuda_specs.total_vram_gb >= 8:
            recommendations["performance_notes"].append(
                "Good VRAM for medium to large models"
            )

        recommendations["available_devices"].append("auto")  # CUDA auto-fallback

    # MPS information
    if specs.supports_mps:
        recommendations["available_devices"].append("mps")
        recommendations["device_info"]["mps"] = {
            "name": f"Apple Silicon GPU ({specs.chip_type.value})",
            "description": f"{specs.gpu_cores} GPU cores, {specs.memory_gb}GB unified memory",
            "suitable_for": [
                "optimized for Apple Silicon",
                "energy efficient",
                "good performance",
            ],
            "performance": "high" if specs.gpu_cores >= 16 else "medium",
        }

        if specs.memory_gb >= 32:
            recommendations["performance_notes"].append(
                "High unified memory enables large models"
            )

        if not specs.supports_cuda:  # If no CUDA, MPS auto is available
            recommendations["available_devices"].append("auto")

    # ROCm information
    if specs.supports_rocm:
        recommendations["available_devices"].append("auto")  # ROCm through auto
        recommendations["device_info"]["rocm"] = {
            "name": "AMD ROCm",
            "description": "AMD GPU acceleration",
            "suitable_for": ["AMD GPU optimization"],
            "performance": "medium",
        }

    # Auto device (if not already added)
    if "auto" not in recommendations["available_devices"]:
        recommendations["available_devices"].append("auto")

    recommendations["device_info"]["auto"] = {
        "name": "Auto",
        "description": "Let PyTorch automatically select the best device",
        "suitable_for": ["general use", "compatibility"],
        "performance": "varies",
    }

    return recommendations


def set_device_environment(device: str) -> None:
    """ Set environment variables for optimal device performance.""".

    if device == "cuda":
        # CUDA optimizations
        os.environ["CUDA_LAUNCH_BLOCKING"] = "0"  # Allow async launches

        # Get CUDA specs for further optimization
        detector = get_hardware_detector()
        specs = detector.detect_hardware()

        if specs.cuda_specs and specs.cuda_specs.supports_mixed_precision:
            # Enable mixed precision for Tensor Core GPUs
            logger.debug("CUDA environment configured for mixed precision")

    elif device == "mps":
        # MPS optimizations
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        logger.debug("MPS environment configured with CPU fallback")

    elif device == "cpu":
        # CPU optimizations
        detector = get_hardware_detector()
        specs = detector.detect_hardware()

        # Set optimal thread count for CPU-only processing
        optimal_threads = min(specs.cpu_cores, 8)  # Cap at 8 for Whisper
        os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
        logger.debug(f"CPU environment configured with {optimal_threads} threads")
