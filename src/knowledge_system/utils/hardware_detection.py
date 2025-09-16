"""
Hardware Detection and Performance Profiling for Knowledge System
Hardware Detection and Performance Profiling for Knowledge System

Automatically detects Apple Silicon hardware specifications and provides
optimized performance profiles for different hardware configurations.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

import psutil

from ..logger import get_logger

logger = get_logger(__name__)

# Try to import CUDA detection libraries
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False


class ChipType(Enum):
    """Apple Silicon chip types."""

    M1 = "M1"
    M1_PRO = "M1 Pro"
    M1_MAX = "M1 Max"
    M1_ULTRA = "M1 Ultra"
    M2 = "M2"
    M2_PRO = "M2 Pro"
    M2_MAX = "M2 Max"
    M2_ULTRA = "M2 Ultra"
    M3 = "M3"
    M3_PRO = "M3 Pro"
    M3_MAX = "M3 Max"
    M3_ULTRA = "M3 Ultra"
    INTEL = "Intel"
    AMD = "AMD"
    NVIDIA_CUDA = "NVIDIA CUDA"
    UNKNOWN = "Unknown"


class GPUType(Enum):
    """GPU types for acceleration."""

    APPLE_SILICON = "Apple Silicon"
    NVIDIA_CUDA = "NVIDIA CUDA"
    AMD_ROCM = "AMD ROCm"
    INTEL_GPU = "Intel GPU"
    NONE = "None"


@dataclass
class CUDASpecs:
    """CUDA-specific hardware specifications."""

    gpu_count: int
    gpu_names: list[str]
    total_vram_gb: float
    cuda_version: str | None
    driver_version: str | None
    compute_capabilities: list[str]
    supports_mixed_precision: bool
    supports_tensor_cores: bool


class PerformanceProfile(Enum):
    """Performance profiles numbered 1-6 for scalability as hardware advances."""

    LEVEL_1 = "level_1"  # Minimal performance for very constrained systems
    LEVEL_2 = "level_2"  # Conservative performance for low-end laptops
    LEVEL_3 = "level_3"  # Balanced performance for mainstream systems
    LEVEL_4 = "level_4"  # High performance for enthusiast systems
    LEVEL_5 = "level_5"  # Ultra performance for workstation-class systems
    LEVEL_6 = "level_6"  # Extreme performance for server-class systems


@dataclass
class HardwareSpecs:
    """Hardware specifications for performance optimization."""

    chip_type: ChipType
    cpu_cores: int
    gpu_cores: int
    neural_engine_cores: int
    memory_gb: int
    memory_bandwidth_gbps: int
    is_apple_silicon: bool
    has_unified_memory: bool
    has_neural_engine: bool
    thermal_design: str  # "mobile", "desktop", "pro"

    # GPU acceleration support
    gpu_type: GPUType
    supports_coreml: bool
    supports_mps: bool
    supports_cuda: bool
    supports_rocm: bool

    # CUDA-specific specs (None if CUDA not available)
    cuda_specs: CUDASpecs | None

    # Derived performance characteristics
    max_concurrent_transcriptions: int
    optimal_batch_size: int
    recommended_whisper_model: str
    recommended_device: str


class HardwareDetector:
    """Detects hardware specifications and creates performance profiles."""

    def __init__(self) -> None:
        self.specs: HardwareSpecs | None = None
        self._detection_cache: dict[str, Any] = {}

    def detect_hardware(self) -> HardwareSpecs:
        """Detect current hardware specifications."""
        if self.specs is not None:
            return self.specs

        logger.info("Detecting hardware specifications...")

        # Basic platform detection
        is_apple_silicon = (
            platform.system() == "Darwin" and platform.machine() == "arm64"
        )

        # CPU detection
        cpu_cores = os.cpu_count() or 4

        # Memory detection
        memory_bytes = psutil.virtual_memory().total
        memory_gb = round(memory_bytes / (1024**3))

        if is_apple_silicon:
            (
                chip_type,
                gpu_cores,
                neural_engine_cores,
                memory_bandwidth_gbps,
                thermal_design,
            ) = self._detect_apple_silicon()
            gpu_type = GPUType.APPLE_SILICON
            supports_cuda = False
            supports_rocm = False
            cuda_specs = None
        else:
            chip_type, gpu_type, cuda_specs = self._detect_gpu_acceleration()
            gpu_cores = 0
            neural_engine_cores = 0
            memory_bandwidth_gbps = 60  # Estimate for non-Apple systems
            thermal_design = "desktop"
            supports_cuda = gpu_type == GPUType.NVIDIA_CUDA
            supports_rocm = gpu_type == GPUType.AMD_ROCM

        # Calculate performance characteristics and device recommendation
        (
            max_concurrent,
            optimal_batch,
            recommended_model,
            recommended_device,
        ) = self._calculate_performance_characteristics(
            chip_type,
            cpu_cores,
            gpu_cores,
            memory_gb,
            thermal_design,
            gpu_type,
            cuda_specs,
        )

        self.specs = HardwareSpecs(
            chip_type=chip_type,
            cpu_cores=cpu_cores,
            gpu_cores=gpu_cores,
            neural_engine_cores=neural_engine_cores,
            memory_gb=memory_gb,
            memory_bandwidth_gbps=memory_bandwidth_gbps,
            is_apple_silicon=is_apple_silicon,
            has_unified_memory=is_apple_silicon,
            has_neural_engine=neural_engine_cores > 0,
            thermal_design=thermal_design,
            gpu_type=gpu_type,
            supports_coreml=is_apple_silicon,
            supports_mps=is_apple_silicon,
            supports_cuda=supports_cuda,
            supports_rocm=supports_rocm,
            cuda_specs=cuda_specs,
            max_concurrent_transcriptions=max_concurrent,
            optimal_batch_size=optimal_batch,
            recommended_whisper_model=recommended_model,
            recommended_device=recommended_device,
        )

        logger.info(
            f"Detected: {chip_type.value} with {cpu_cores} CPU cores, {gpu_cores} GPU cores, {memory_gb}GB RAM"
        )
        return self.specs

    def _detect_apple_silicon(self) -> tuple[ChipType, int, int, int, str]:
        """Detect specific Apple Silicon chip and specifications."""
        try:
            # Get system info using system_profiler
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(
                    "Could not run system_profiler, using fallback detection"
                )
                return self._fallback_apple_silicon_detection()

            import json

            data = json.loads(result.stdout)
            hardware_info = data["SPHardwareDataType"][0]

            chip_name = hardware_info.get("chip_type", "").lower()
            machine_name = hardware_info.get("machine_name", "").lower()

            # Detect chip type and specs
            (
                chip_type,
                gpu_cores,
                neural_engine_cores,
                memory_bandwidth_gbps,
                thermal_design,
            ) = self._parse_chip_specs(chip_name, machine_name)

            logger.info(f"Detected Apple Silicon: {chip_type.value}")
            return (
                chip_type,
                gpu_cores,
                neural_engine_cores,
                memory_bandwidth_gbps,
                thermal_design,
            )

        except Exception as e:
            logger.warning(f"Apple Silicon detection failed: {e}")
            return self._fallback_apple_silicon_detection()

    def _parse_chip_specs(
        self, chip_name: str, machine_name: str
    ) -> tuple[ChipType, int, int, int, str]:
        """Parse chip specifications from system info."""

        # M3 Series
        if "m3" in chip_name:
            if "ultra" in chip_name:
                return ChipType.M3_ULTRA, 76, 32, 800, "desktop"
            elif "max" in chip_name:
                return ChipType.M3_MAX, 40, 16, 400, "desktop"
            elif "pro" in chip_name:
                return ChipType.M3_PRO, 18, 11, 150, "mobile"
            else:
                return ChipType.M3, 10, 16, 100, "mobile"

        # M2 Series
        elif "m2" in chip_name:
            if "ultra" in chip_name:
                return ChipType.M2_ULTRA, 76, 32, 800, "desktop"
            elif "max" in chip_name:
                return ChipType.M2_MAX, 38, 16, 400, "desktop"
            elif "pro" in chip_name:
                return ChipType.M2_PRO, 19, 16, 200, "mobile"
            else:
                return ChipType.M2, 10, 16, 100, "mobile"

        # M1 Series
        elif "m1" in chip_name:
            if "ultra" in chip_name:
                return ChipType.M1_ULTRA, 64, 32, 800, "desktop"
            elif "max" in chip_name:
                return ChipType.M1_MAX, 32, 16, 400, "desktop"
            elif "pro" in chip_name:
                return ChipType.M1_PRO, 16, 16, 200, "mobile"
            else:
                return ChipType.M1, 8, 16, 68, "mobile"

        # Fallback for unknown Apple Silicon
        else:
            logger.warning(f"Unknown Apple Silicon chip: {chip_name}")
            return ChipType.UNKNOWN, 10, 16, 100, "mobile"

    def _fallback_apple_silicon_detection(self) -> tuple[ChipType, int, int, int, str]:
        """Fallback detection for Apple Silicon when system_profiler fails."""
        cpu_cores = os.cpu_count() or 8

        # Estimate based on CPU cores (rough approximation)
        if cpu_cores >= 20:
            return ChipType.M3_ULTRA, 76, 32, 800, "desktop"
        elif cpu_cores >= 12:
            return ChipType.M3_MAX, 40, 16, 400, "desktop"
        elif cpu_cores >= 10:
            return ChipType.M3_PRO, 18, 11, 150, "mobile"
        else:
            return ChipType.M3, 10, 16, 100, "mobile"

    def _detect_gpu_acceleration(self) -> tuple[ChipType, GPUType, CUDASpecs | None]:
        """Detect GPU acceleration capabilities (CUDA, ROCm, etc.)."""

        # First try CUDA detection
        cuda_specs = self._detect_cuda()
        if cuda_specs and cuda_specs.gpu_count > 0:
            return ChipType.NVIDIA_CUDA, GPUType.NVIDIA_CUDA, cuda_specs

        # Try AMD ROCm detection
        if self._detect_rocm():
            return ChipType.AMD, GPUType.AMD_ROCM, None

        # Check for Intel GPUs
        if self._detect_intel_gpu():
            return ChipType.INTEL, GPUType.INTEL_GPU, None

        # Default to CPU-only
        return ChipType.INTEL, GPUType.NONE, None

    def _detect_cuda(self) -> CUDASpecs | None:
        """Detect CUDA-capable NVIDIA GPUs."""
        if not TORCH_AVAILABLE:
            logger.debug("PyTorch not available, skipping CUDA detection")
            return None

        try:
            # Check if CUDA is available through PyTorch
            if not torch.cuda.is_available():
                logger.debug("CUDA not available through PyTorch")
                return None

            gpu_count = torch.cuda.device_count()
            if gpu_count == 0:
                return None

            # Get basic CUDA info from PyTorch
            gpu_names = []
            compute_capabilities = []
            total_vram_gb = 0.0

            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_names.append(gpu_name)

                # Get memory info
                gpu_memory = torch.cuda.get_device_properties(i).total_memory
                total_vram_gb += gpu_memory / (1024**3)

                # Get compute capability
                props = torch.cuda.get_device_properties(i)
                compute_cap = f"{props.major}.{props.minor}"
                compute_capabilities.append(compute_cap)

            # Determine capabilities based on compute capability
            supports_mixed_precision = any(
                float(cap) >= 7.0 for cap in compute_capabilities
            )
            supports_tensor_cores = any(
                float(cap) >= 7.0 for cap in compute_capabilities
            )

            # Try to get detailed info with pynvml if available
            cuda_version = None
            driver_version = None

            if PYNVML_AVAILABLE:
                try:
                    pynvml.nvmlInit()
                    driver_version = pynvml.nvmlSystemGetDriverVersion().decode("utf-8")
                    cuda_version = pynvml.nvmlSystemGetCudaDriverVersion_v2()
                    if cuda_version:
                        cuda_version = (
                            f"{cuda_version // 1000}.{(cuda_version % 1000) // 10}"
                        )
                except Exception as e:
                    logger.debug(f"pynvml detection failed: {e}")

            # Fallback to PyTorch CUDA version
            if not cuda_version:
                try:
                    if hasattr(torch, "version") and hasattr(torch.version, "cuda"):
                        cuda_version = torch.version.cuda
                    else:
                        cuda_version = "Unknown"
                except Exception:
                    cuda_version = "Unknown"

            cuda_specs = CUDASpecs(
                gpu_count=gpu_count,
                gpu_names=gpu_names,
                total_vram_gb=total_vram_gb,
                cuda_version=cuda_version,
                driver_version=driver_version,
                compute_capabilities=compute_capabilities,
                supports_mixed_precision=supports_mixed_precision,
                supports_tensor_cores=supports_tensor_cores,
            )

            logger.info(
                f"Detected CUDA: {gpu_count} GPU(s), {total_vram_gb:.1f}GB VRAM, CUDA {cuda_version}"
            )
            return cuda_specs

        except Exception as e:
            logger.debug(f"CUDA detection failed: {e}")
            return None

    def _detect_rocm(self) -> bool:
        """Detect AMD ROCm support."""
        if not TORCH_AVAILABLE:
            return False

        try:
            # Check if ROCm/HIP is available
            hip_available = False
            if hasattr(torch, "version"):
                hip_available = (
                    hasattr(torch.version, "hip") and torch.version.hip is not None
                )
            return torch.cuda.is_available() and hip_available
        except Exception:
            return False

    def _detect_intel_gpu(self) -> bool:
        """Detect Intel GPU support."""
        # This is a basic detection - can be enhanced with Intel GPU libraries
        try:
            # Check for Intel GPU on Linux/Windows
            import subprocess

            result = subprocess.run(
                ["lspci", "-nn"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "Intel" in result.stdout and (
                    "VGA" in result.stdout or "Display" in result.stdout
                )
        except Exception:
            pass
        return False

    def _calculate_performance_characteristics(
        self,
        chip_type: ChipType,
        cpu_cores: int,
        gpu_cores: int,
        memory_gb: int,
        thermal_design: str,
        gpu_type: GPUType,
        cuda_specs: CUDASpecs | None,
    ) -> tuple[int, int, str, str]:
        """Calculate optimal performance characteristics based on hardware."""

        # Base calculations
        max(1, cpu_cores // 2)
        base_batch_size = max(
            8, min(8, memory_gb * 2)
        )  # Capped at 8 for whisper.cpp compatibility

        # Hardware-specific optimizations
        # Cap model recommendations at 'base' since it provides sufficient quality
        # while being much faster and using less resources
        if chip_type in [ChipType.M3_ULTRA, ChipType.M2_ULTRA, ChipType.M1_ULTRA]:
            # Ultra chips: Push the limits for maximum performance
            max_concurrent = min(24, int(cpu_cores * 0.8))  # Use 80% of cores
            optimal_batch = 32  # Larger batches for Ultra chips
            recommended_model = (
                "small" if memory_gb >= 64 else "base"
            )  # Upgrade model for high memory

        elif chip_type in [ChipType.M3_MAX, ChipType.M2_MAX, ChipType.M1_MAX]:
            # Max chips: High performance with base model
            max_concurrent = min(12, cpu_cores // 2)
            optimal_batch = 8  # Capped for whisper.cpp compatibility
            recommended_model = "base"

        elif chip_type in [ChipType.M3_PRO, ChipType.M2_PRO, ChipType.M1_PRO]:
            # Pro chips: Balanced performance with base model
            max_concurrent = min(8, cpu_cores // 2)
            optimal_batch = 8  # Capped for whisper.cpp compatibility
            recommended_model = "base"

        else:
            # Base chips: Conservative settings with base model
            max_concurrent = min(6, cpu_cores // 2)
            optimal_batch = 8  # Capped for whisper.cpp compatibility
            recommended_model = "base"

        # Thermal design adjustments
        if thermal_design == "mobile":
            # Reduce for mobile/laptop thermal constraints
            max_concurrent = max(1, max_concurrent // 2)
            optimal_batch = max(8, optimal_batch // 2)

        # Memory constraints - account for OS, apps, and safety margin
        # Reserve memory for OS and other applications
        os_overhead_gb = max(4, memory_gb * 0.25)  # 25% or min 4GB for OS + apps
        available_memory_gb = max(2, memory_gb - os_overhead_gb)

        # Model memory requirements (rough estimates including processing overhead)
        model_memory_requirements = {
            "tiny": 1.5,
            "base": 2.0,
            "small": 3.5,
            "medium": 6.0,
            "large": 12.0,
            "large-v3": 12.0,
        }

        # Calculate safe concurrent limit based on available memory
        model_memory_needed = model_memory_requirements.get(recommended_model, 6.0)
        safe_concurrent = max(
            1, int(available_memory_gb // (model_memory_needed * 1.2))
        )  # 20% safety margin

        # Apply memory-based constraints
        # Since we're already using "base" model, focus on concurrent processing limits
        if available_memory_gb < 8:
            max_concurrent = min(max_concurrent, 2, safe_concurrent)
            optimal_batch = min(optimal_batch, 16)
            # recommended_model already set to "base" above
        elif available_memory_gb < 16:
            max_concurrent = min(max_concurrent, 4, safe_concurrent)
            optimal_batch = min(optimal_batch, 24)
            # recommended_model already set to "base" above
        elif available_memory_gb < 24:
            max_concurrent = min(max_concurrent, 6, safe_concurrent)
            optimal_batch = min(optimal_batch, 32)

        # CUDA-specific optimizations
        # Focus on performance improvements while keeping "base" model
        if gpu_type == GPUType.NVIDIA_CUDA and cuda_specs:
            # Boost concurrent processing for high-VRAM CUDA GPUs
            if cuda_specs.total_vram_gb >= 16:
                max_concurrent = min(max_concurrent * 2, 16)
                optimal_batch = min(optimal_batch * 2, 64)
                # Keep recommended_model as "base" for consistency
            elif cuda_specs.total_vram_gb >= 8:
                max_concurrent = min(max_concurrent + 2, 12)
                optimal_batch = min(optimal_batch + 16, 48)
                # Keep recommended_model as "base" for consistency

            # Use mixed precision for Tensor Core GPUs
            if cuda_specs.supports_tensor_cores:
                optimal_batch = min(optimal_batch + 8, 64)

        # Device recommendation
        recommended_device = self._recommend_device(gpu_type, cuda_specs)

        return max_concurrent, optimal_batch, recommended_model, recommended_device

    def _recommend_device(self, gpu_type: GPUType, cuda_specs: CUDASpecs | None) -> str:
        """Recommend the best device for processing."""
        if gpu_type == GPUType.APPLE_SILICON:
            return "mps"
        elif gpu_type == GPUType.NVIDIA_CUDA and cuda_specs:
            # Prefer CUDA for high-VRAM GPUs
            if cuda_specs.total_vram_gb >= 6:
                return "cuda"
            else:
                return "auto"  # Let PyTorch decide between CUDA and CPU
        elif gpu_type == GPUType.AMD_ROCM:
            return "auto"  # PyTorch will use ROCm if available
        else:
            return "cpu"

    def get_performance_profile(self, profile: PerformanceProfile) -> dict[str, Any]:
        """Get performance configuration for a specific profile."""
        specs = self.detect_hardware()

        if profile == PerformanceProfile.LEVEL_1:
            return {
                "omp_num_threads": max(1, specs.cpu_cores // 4),
                "max_concurrent_files": 1,
                "per_process_thread_limit": 1,
                "enable_parallel_processing": False,
                "sequential_processing": True,
                "whisper_model": "tiny",
                "batch_size": 8,
                "device": "cpu" if not specs.is_apple_silicon else "mps",
                "use_coreml": False,
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": False,
            }

        elif profile == PerformanceProfile.LEVEL_2:
            return {
                "omp_num_threads": max(1, specs.cpu_cores // 2),
                "max_concurrent_files": max(
                    1, specs.max_concurrent_transcriptions // 2
                ),
                "per_process_thread_limit": max(1, specs.cpu_cores // 4),
                "enable_parallel_processing": True,
                "sequential_processing": False,
                "whisper_model": "base",
                "batch_size": specs.optimal_batch_size // 2,
                "device": (
                    specs.recommended_device
                    if specs.recommended_device != "cpu"
                    else "auto"
                ),
                "use_coreml": specs.supports_coreml,
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": False,
            }

        elif profile == PerformanceProfile.LEVEL_3:
            return {
                "omp_num_threads": max(1, specs.cpu_cores),
                "max_concurrent_files": specs.max_concurrent_transcriptions,
                "per_process_thread_limit": max(1, specs.cpu_cores // 2),
                "enable_parallel_processing": True,
                "sequential_processing": False,
                "whisper_model": specs.recommended_whisper_model,
                "batch_size": specs.optimal_batch_size,
                "device": specs.recommended_device,
                "use_coreml": specs.supports_coreml,
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": True,
            }

        elif profile == PerformanceProfile.LEVEL_4:
            return {
                "omp_num_threads": specs.cpu_cores,
                "max_concurrent_files": specs.max_concurrent_transcriptions,
                "per_process_thread_limit": specs.cpu_cores,
                "enable_parallel_processing": True,
                "sequential_processing": False,
                "whisper_model": specs.recommended_whisper_model,
                "batch_size": specs.optimal_batch_size,
                "device": specs.recommended_device,
                "use_coreml": False,  # Prefer GPU acceleration for large batch processing
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": True,
            }

        elif profile == PerformanceProfile.LEVEL_5:
            # For workstation-class machines (64GB+, 16+ cores)
            # Push harder but still maintain stability
            return {
                "omp_num_threads": specs.cpu_cores,
                "max_concurrent_files": min(
                    20, specs.max_concurrent_transcriptions * 2
                ),  # Allow higher concurrency
                "per_process_thread_limit": specs.cpu_cores,
                "enable_parallel_processing": True,
                "sequential_processing": False,
                "whisper_model": "small"
                if specs.memory_gb >= 64
                else specs.recommended_whisper_model,  # Upgrade model
                "batch_size": min(64, specs.optimal_batch_size * 4),  # Larger batches
                "device": specs.recommended_device,
                "use_coreml": False,  # Prefer raw GPU power
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": True,
            }

        elif profile == PerformanceProfile.LEVEL_6:
            # For server-class machines (128GB+, 20+ cores)
            # Maximum utilization - user wants speed over caution
            return {
                "omp_num_threads": specs.cpu_cores,
                "max_concurrent_files": min(
                    32, specs.cpu_cores
                ),  # Up to 32 concurrent or 1 per core
                "per_process_thread_limit": specs.cpu_cores,
                "enable_parallel_processing": True,
                "sequential_processing": False,
                "whisper_model": "medium"
                if specs.memory_gb >= 128
                else "small",  # Even larger model
                "batch_size": min(
                    128, specs.optimal_batch_size * 8
                ),  # Very large batches
                "device": specs.recommended_device,
                "use_coreml": False,  # Raw performance over efficiency
                "pytorch_enable_mps_fallback": True,
                "tokenizers_parallelism": True,
            }

        else:
            raise ValueError(f"Unknown performance profile: {profile}")

    def get_hardware_report(self) -> dict[str, Any]:
        """Get comprehensive hardware report."""
        specs = self.detect_hardware()

        report = {
            "chip_type": specs.chip_type.value,
            "cpu_cores": specs.cpu_cores,
            "gpu_cores": specs.gpu_cores,
            "neural_engine_cores": specs.neural_engine_cores,
            "memory_gb": specs.memory_gb,
            "memory_bandwidth_gbps": specs.memory_bandwidth_gbps,
            "is_apple_silicon": specs.is_apple_silicon,
            "has_unified_memory": specs.has_unified_memory,
            "has_neural_engine": specs.has_neural_engine,
            "thermal_design": specs.thermal_design,
            "gpu_type": specs.gpu_type.value,
            "supports_coreml": specs.supports_coreml,
            "supports_mps": specs.supports_mps,
            "supports_cuda": specs.supports_cuda,
            "supports_rocm": specs.supports_rocm,
            "performance_characteristics": {
                "max_concurrent_transcriptions": specs.max_concurrent_transcriptions,
                "optimal_batch_size": specs.optimal_batch_size,
                "recommended_whisper_model": specs.recommended_whisper_model,
                "recommended_device": specs.recommended_device,
            },
        }

        # Add CUDA-specific information if available
        if specs.cuda_specs:
            report["cuda_info"] = {
                "gpu_count": specs.cuda_specs.gpu_count,
                "gpu_names": specs.cuda_specs.gpu_names,
                "total_vram_gb": specs.cuda_specs.total_vram_gb,
                "cuda_version": specs.cuda_specs.cuda_version,
                "driver_version": specs.cuda_specs.driver_version,
                "compute_capabilities": specs.cuda_specs.compute_capabilities,
                "supports_mixed_precision": specs.cuda_specs.supports_mixed_precision,
                "supports_tensor_cores": specs.cuda_specs.supports_tensor_cores,
            }

        return report

    def recommend_profile(self, use_case: str = "general") -> PerformanceProfile:
        """Recommend optimal performance profile based on hardware and use case."""
        specs = self.detect_hardware()

        # For large batch processing, prioritize maximum performance on high-end hardware
        if use_case == "large_batch":
            if specs.chip_type in [
                ChipType.M3_ULTRA,
                ChipType.M2_ULTRA,
                ChipType.M1_ULTRA,
            ]:
                return PerformanceProfile.LEVEL_4
            elif specs.chip_type in [ChipType.M3_MAX, ChipType.M2_MAX, ChipType.M1_MAX]:
                return PerformanceProfile.LEVEL_3
            else:
                return PerformanceProfile.LEVEL_2

        # For battery-powered devices, recommend balanced mode
        elif use_case == "mobile":
            if specs.thermal_design == "mobile":
                return PerformanceProfile.LEVEL_2
            else:
                return PerformanceProfile.LEVEL_3

        # General use case - balance performance and resource usage
        else:
            if specs.memory_gb >= 64 and specs.gpu_cores >= 30:
                return PerformanceProfile.LEVEL_3
            elif specs.memory_gb >= 32 and specs.gpu_cores >= 16:
                return PerformanceProfile.LEVEL_2
            else:
                return PerformanceProfile.LEVEL_2


# Global hardware detector instance
_hardware_detector: HardwareDetector | None = None


def get_hardware_detector() -> HardwareDetector:
    """Get or create global hardware detector instance."""
    global _hardware_detector
    if _hardware_detector is None:
        _hardware_detector = HardwareDetector()
    return _hardware_detector


def detect_hardware() -> HardwareSpecs:
    """Convenience function to detect hardware."""
    return get_hardware_detector().detect_hardware()


def get_performance_profile(profile: PerformanceProfile) -> dict[str, Any]:
    """Convenience function to get performance profile."""
    return get_hardware_detector().get_performance_profile(profile)


def get_hardware_report() -> dict[str, Any]:
    """Convenience function to get hardware report."""
    return get_hardware_detector().get_hardware_report()


def recommend_profile(use_case: str = "general") -> PerformanceProfile:
    """Convenience function to recommend performance profile."""
    return get_hardware_detector().recommend_profile(use_case)
