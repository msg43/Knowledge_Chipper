"""Tests for CUDA detection and hardware optimization."""

from unittest.mock import MagicMock, patch

from knowledge_system.utils.hardware_detection import (
    ChipType,
    CUDASpecs,
    GPUType,
    HardwareDetector,
    get_hardware_detector,
)


class TestCUDADetection:
    """Test CUDA hardware detection functionality."""

    def test_no_torch_available(self):
        """Test CUDA detection when PyTorch is not available."""
        detector = HardwareDetector()

        with patch("knowledge_system.utils.hardware_detection.TORCH_AVAILABLE", False):
            cuda_specs = detector._detect_cuda()
            assert cuda_specs is None

    def test_cuda_not_available(self):
        """Test when CUDA is not available through PyTorch."""
        detector = HardwareDetector()

        with patch("knowledge_system.utils.hardware_detection.TORCH_AVAILABLE", True):
            with patch("torch.cuda.is_available", return_value=False):
                cuda_specs = detector._detect_cuda()
                assert cuda_specs is None

    def test_cuda_available_single_gpu(self):
        """Test CUDA detection with a single GPU."""
        detector = HardwareDetector()

        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024**3  # 8GB
        mock_props.major = 8
        mock_props.minor = 6

        with patch("knowledge_system.utils.hardware_detection.TORCH_AVAILABLE", True):
            with patch("torch.cuda.is_available", return_value=True):
                with patch("torch.cuda.device_count", return_value=1):
                    with patch(
                        "torch.cuda.get_device_name", return_value="GeForce RTX 3080"
                    ):
                        with patch(
                            "torch.cuda.get_device_properties", return_value=mock_props
                        ):
                            with patch("torch.version.cuda", "11.8"):
                                cuda_specs = detector._detect_cuda()

        assert cuda_specs is not None
        assert cuda_specs.gpu_count == 1
        assert cuda_specs.gpu_names == ["GeForce RTX 3080"]
        assert cuda_specs.total_vram_gb == 8.0
        assert cuda_specs.compute_capabilities == ["8.6"]
        assert cuda_specs.supports_tensor_cores is True
        assert cuda_specs.supports_mixed_precision is True

    def test_cuda_available_multiple_gpus(self):
        """Test CUDA detection with multiple GPUs."""
        detector = HardwareDetector()

        mock_props = MagicMock()
        mock_props.total_memory = 16 * 1024**3  # 16GB
        mock_props.major = 8
        mock_props.minor = 0

        with patch("knowledge_system.utils.hardware_detection.TORCH_AVAILABLE", True):
            with patch("torch.cuda.is_available", return_value=True):
                with patch("torch.cuda.device_count", return_value=2):
                    with patch(
                        "torch.cuda.get_device_name",
                        side_effect=["RTX 4090", "RTX 4090"],
                    ):
                        with patch(
                            "torch.cuda.get_device_properties", return_value=mock_props
                        ):
                            with patch("torch.version.cuda", "12.1"):
                                cuda_specs = detector._detect_cuda()

        assert cuda_specs is not None
        assert cuda_specs.gpu_count == 2
        assert cuda_specs.gpu_names == ["RTX 4090", "RTX 4090"]
        assert cuda_specs.total_vram_gb == 32.0  # 16GB * 2
        assert cuda_specs.supports_tensor_cores is True

    def test_gpu_acceleration_detection_cuda(self):
        """Test GPU acceleration detection prioritizes CUDA."""
        detector = HardwareDetector()

        mock_cuda_specs = CUDASpecs(
            gpu_count=1,
            gpu_names=["RTX 3080"],
            total_vram_gb=10.0,
            cuda_version="11.8",
            driver_version="522.25",
            compute_capabilities=["8.6"],
            supports_mixed_precision=True,
            supports_tensor_cores=True,
        )

        with patch.object(detector, "_detect_cuda", return_value=mock_cuda_specs):
            chip_type, gpu_type, cuda_specs = detector._detect_gpu_acceleration()

            assert chip_type == ChipType.NVIDIA_CUDA
            assert gpu_type == GPUType.NVIDIA_CUDA
            assert cuda_specs == mock_cuda_specs

    def test_gpu_acceleration_detection_fallback(self):
        """Test GPU acceleration detection falls back to CPU."""
        detector = HardwareDetector()

        with patch.object(detector, "_detect_cuda", return_value=None):
            with patch.object(detector, "_detect_rocm", return_value=False):
                with patch.object(detector, "_detect_intel_gpu", return_value=False):
                    (
                        chip_type,
                        gpu_type,
                        cuda_specs,
                    ) = detector._detect_gpu_acceleration()

                    assert chip_type == ChipType.INTEL
                    assert gpu_type == GPUType.NONE
                    assert cuda_specs is None

    def test_device_recommendation_cuda_high_vram(self):
        """Test device recommendation for high-VRAM CUDA GPU."""
        detector = HardwareDetector()

        cuda_specs = CUDASpecs(
            gpu_count=1,
            gpu_names=["RTX 4090"],
            total_vram_gb=24.0,
            cuda_version="12.1",
            driver_version="535.98",
            compute_capabilities=["8.9"],
            supports_mixed_precision=True,
            supports_tensor_cores=True,
        )

        device = detector._recommend_device(GPUType.NVIDIA_CUDA, cuda_specs)
        assert device == "cuda"

    def test_device_recommendation_cuda_low_vram(self):
        """Test device recommendation for low-VRAM CUDA GPU."""
        detector = HardwareDetector()

        cuda_specs = CUDASpecs(
            gpu_count=1,
            gpu_names=["GTX 1050"],
            total_vram_gb=4.0,
            cuda_version="11.8",
            driver_version="522.25",
            compute_capabilities=["6.1"],
            supports_mixed_precision=False,
            supports_tensor_cores=False,
        )

        device = detector._recommend_device(GPUType.NVIDIA_CUDA, cuda_specs)
        assert device == "auto"

    def test_device_recommendation_apple_silicon(self):
        """Test device recommendation for Apple Silicon."""
        detector = HardwareDetector()

        device = detector._recommend_device(GPUType.APPLE_SILICON, None)
        assert device == "mps"

    def test_device_recommendation_cpu_only(self):
        """Test device recommendation for CPU-only systems."""
        detector = HardwareDetector()

        device = detector._recommend_device(GPUType.NONE, None)
        assert device == "cpu"

    def test_performance_characteristics_cuda_optimization(self):
        """Test performance characteristics optimization for CUDA."""
        detector = HardwareDetector()

        cuda_specs = CUDASpecs(
            gpu_count=1,
            gpu_names=["RTX 4090"],
            total_vram_gb=24.0,
            cuda_version="12.1",
            driver_version="535.98",
            compute_capabilities=["8.9"],
            supports_mixed_precision=True,
            supports_tensor_cores=True,
        )

        (
            max_concurrent,
            optimal_batch,
            recommended_model,
            recommended_device,
        ) = detector._calculate_performance_characteristics(
            ChipType.NVIDIA_CUDA, 16, 0, 32, "desktop", GPUType.NVIDIA_CUDA, cuda_specs
        )

        # Should be optimized for high-VRAM CUDA
        assert recommended_model == "large-v3"
        assert recommended_device == "cuda"
        assert optimal_batch >= 32  # Should be boosted
        assert max_concurrent >= 8  # Should be boosted

    def test_hardware_report_includes_cuda_info(self):
        """Test that hardware report includes CUDA information."""
        detector = HardwareDetector()

        # Mock a system with CUDA
        mock_specs = MagicMock()
        mock_specs.supports_cuda = True
        mock_specs.cuda_specs = CUDASpecs(
            gpu_count=2,
            gpu_names=["RTX 4090", "RTX 4090"],
            total_vram_gb=48.0,
            cuda_version="12.1",
            driver_version="535.98",
            compute_capabilities=["8.9", "8.9"],
            supports_mixed_precision=True,
            supports_tensor_cores=True,
        )
        mock_specs.chip_type.value = "NVIDIA CUDA"
        mock_specs.gpu_type.value = "NVIDIA CUDA"
        mock_specs.cpu_cores = 16
        mock_specs.gpu_cores = 0
        mock_specs.neural_engine_cores = 0
        mock_specs.memory_gb = 64
        mock_specs.memory_bandwidth_gbps = 100
        mock_specs.is_apple_silicon = False
        mock_specs.has_unified_memory = False
        mock_specs.has_neural_engine = False
        mock_specs.thermal_design = "desktop"
        mock_specs.supports_coreml = False
        mock_specs.supports_mps = False
        mock_specs.supports_rocm = False
        mock_specs.max_concurrent_transcriptions = 16
        mock_specs.optimal_batch_size = 64
        mock_specs.recommended_whisper_model = "large-v3"
        mock_specs.recommended_device = "cuda"

        with patch.object(detector, "detect_hardware", return_value=mock_specs):
            report = detector.get_hardware_report()

        assert report["supports_cuda"] is True
        assert "cuda_info" in report
        assert report["cuda_info"]["gpu_count"] == 2
        assert report["cuda_info"]["total_vram_gb"] == 48.0
        assert report["cuda_info"]["supports_tensor_cores"] is True


class TestCUDAIntegration:
    """Test CUDA integration with the overall system."""

    def test_global_hardware_detector_singleton(self):
        """Test that global hardware detector is a singleton."""
        detector1 = get_hardware_detector()
        detector2 = get_hardware_detector()

        assert detector1 is detector2

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="x86_64")
    def test_non_apple_silicon_detection(self, mock_machine, mock_system):
        """Test hardware detection on non-Apple Silicon systems."""
        detector = HardwareDetector()

        # Mock CUDA detection
        mock_cuda_specs = CUDASpecs(
            gpu_count=1,
            gpu_names=["RTX 3080"],
            total_vram_gb=10.0,
            cuda_version="11.8",
            driver_version="522.25",
            compute_capabilities=["8.6"],
            supports_mixed_precision=True,
            supports_tensor_cores=True,
        )

        with patch.object(
            detector,
            "_detect_gpu_acceleration",
            return_value=(ChipType.NVIDIA_CUDA, GPUType.NVIDIA_CUDA, mock_cuda_specs),
        ):
            with patch("os.cpu_count", return_value=16):
                with patch("psutil.virtual_memory") as mock_memory:
                    mock_memory.return_value.total = 32 * 1024**3  # 32GB

                    specs = detector.detect_hardware()

        assert specs.chip_type == ChipType.NVIDIA_CUDA
        assert specs.gpu_type == GPUType.NVIDIA_CUDA
        assert specs.supports_cuda is True
        assert specs.supports_mps is False
        assert specs.cuda_specs == mock_cuda_specs
        assert specs.recommended_device == "cuda"
