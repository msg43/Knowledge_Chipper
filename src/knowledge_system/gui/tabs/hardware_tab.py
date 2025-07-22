"""Hardware detection and performance configuration tab."""

from typing import Optional

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QTextEdit
)
from PyQt6.QtCore import QTimer, pyqtSignal

from ..components.base_tab import BaseTab
from ...logger import get_logger

logger = get_logger(__name__)


class HardwareTab(BaseTab):
    """Tab for hardware detection and performance recommendations (read-only)."""
    
    # Signals for hardware detection
    hardware_detected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def _setup_ui(self):
        """Setup the hardware detection UI."""
        main_layout = QVBoxLayout(self)
        
        # Instructions section
        instructions_group = QGroupBox("About This Tab")
        instructions_layout = QVBoxLayout()
        
        instructions_text = QLabel("""
🔍 Hardware Analysis & Recommendations

This tab analyzes your system hardware and provides optimized settings recommendations. 
The actual transcription controls are in the "Audio Transcription" tab, where you can 
choose to use the recommended settings or manually override them.
        """)
        instructions_text.setWordWrap(True)
        instructions_text.setStyleSheet("""
            background-color: #2b2b2b; 
            color: #ffffff;
            padding: 15px; 
            border: 1px solid #555; 
            border-radius: 5px;
            font-size: 12px;
        """)
        instructions_layout.addWidget(instructions_text)
        
        instructions_group.setLayout(instructions_layout)
        main_layout.addWidget(instructions_group)
        
        # Hardware Detection Section
        hardware_group = QGroupBox("System Hardware Detection & Recommendations")
        hardware_layout = QVBoxLayout()
        
        # Auto-detect button
        detect_btn = QPushButton("🔍 Detect Hardware Capabilities")
        detect_btn.clicked.connect(self._detect_hardware)
        detect_btn.setStyleSheet("background-color: #2196f3; color: white; font-weight: bold; padding: 8px;")
        hardware_layout.addWidget(detect_btn)
        
        # Consolidated hardware info display - make it much larger
        self.hardware_info_text = QTextEdit()
        self.hardware_info_text.setMinimumHeight(700)  # Increased from 500 to 700
        self.hardware_info_text.setReadOnly(True)
        # Set dark theme for the text area too
        self.hardware_info_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        hardware_layout.addWidget(self.hardware_info_text)
        
        hardware_group.setLayout(hardware_layout)
        main_layout.addWidget(hardware_group)
        
        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        
        main_layout.addStretch()
        
    def _connect_signals(self):
        """Connect internal signals."""
        # Auto-detect hardware on tab creation
        QTimer.singleShot(100, self._detect_hardware)
        
    def _get_start_button_text(self) -> str:
        """Get the text for the start button."""
        return "Detect Hardware"
        
    def _start_processing(self):
        """Detect hardware when start button is pressed."""
        self._detect_hardware()
    
    def _detect_hardware(self):
        """Detect and display hardware capabilities."""
        try:
            from ...utils.hardware_detection import get_hardware_detector
            from ...utils.device_selection import get_device_recommendations
            
            detector = get_hardware_detector()
            specs = detector.detect_hardware()
            
            # Build consolidated hardware information display
            hardware_info = []
            
            # System Hardware Information
            hardware_info.append("🖥️ SYSTEM HARDWARE")
            hardware_info.append("=" * 40)
            hardware_info.append(f"🖥️ System: {specs.chip_type.value}")
            hardware_info.append(f"⚡ CPU Cores: {specs.cpu_cores}")
            hardware_info.append(f"🧠 Memory: {specs.memory_gb}GB")
            
            if specs.is_apple_silicon:
                hardware_info.append(f"🎮 GPU Cores: {specs.gpu_cores}")
                if specs.has_neural_engine:
                    hardware_info.append(f"🧠 Neural Engine: {specs.neural_engine_cores} cores")
                hardware_info.append(f"⚡ Memory Bandwidth: {specs.memory_bandwidth_gbps}GB/s")
                hardware_info.append(f"🏠 Design: {specs.thermal_design}")
            
            if specs.supports_cuda and specs.cuda_specs:
                hardware_info.append(f"🚀 CUDA GPUs: {specs.cuda_specs.gpu_count}")
                for i, gpu in enumerate(specs.cuda_specs.gpu_names):
                    hardware_info.append(f"  GPU {i+1}: {gpu}")
                hardware_info.append(f"💾 Total VRAM: {specs.cuda_specs.total_vram_gb:.1f}GB")
                hardware_info.append(f"🔧 CUDA Version: {specs.cuda_specs.cuda_version}")
                if specs.cuda_specs.supports_tensor_cores:
                    hardware_info.append("⭐ Tensor Cores: Supported")
            
            # Get device recommendations
            recommendations = get_device_recommendations("transcription")
            
            # Device Recommendations Section
            hardware_info.append("")
            hardware_info.append("🎯 DEVICE RECOMMENDATIONS")
            hardware_info.append("=" * 40)
            hardware_info.append(f"🎯 Primary Recommendation: {recommendations['primary_device']}")
            hardware_info.append("")
            
            for device in recommendations['available_devices']:
                if device in recommendations['device_info']:
                    info = recommendations['device_info'][device]
                    hardware_info.append(f"🔧 {info['name']}")
                    hardware_info.append(f"   {info['description']}")
                    hardware_info.append(f"   Performance: {info.get('performance', 'Unknown')}")
                    if 'features' in info and info['features']:
                        for feature in info['features']:
                            hardware_info.append(f"   ✓ {feature}")
                    hardware_info.append("")
            
            # Recommended Settings Section
            hardware_info.append("📊 RECOMMENDED SETTINGS")
            hardware_info.append("=" * 40)
            hardware_info.append(f"• Whisper Model: {specs.recommended_whisper_model}")
            hardware_info.append(f"• Device: {specs.recommended_device}")
            hardware_info.append(f"• Batch Size: {specs.optimal_batch_size}")
            hardware_info.append(f"• Max Concurrent: {specs.max_concurrent_transcriptions}")
            
            # Performance Notes
            if recommendations['performance_notes']:
                hardware_info.append("")
                hardware_info.append("💡 PERFORMANCE NOTES")
                hardware_info.append("=" * 40)
                for note in recommendations['performance_notes']:
                    hardware_info.append(f"• {note}")
            
            # Usage Instructions
            hardware_info.append("")
            hardware_info.append("🎛️ HOW TO USE THESE RECOMMENDATIONS")
            hardware_info.append("=" * 40)
            hardware_info.append("• Go to the 'Audio Transcription' tab")
            hardware_info.append("• Click 'Use Recommended Settings' to apply optimal configuration")
            hardware_info.append("• Or manually override any settings as needed")
            hardware_info.append("• Recommended settings are optimized for your specific hardware")
            
            # Display all consolidated information
            self.hardware_info_text.setText("\n".join(hardware_info))
            
            self.status_label.setText("✅ Hardware detection completed successfully")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            
            # Clear success message after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
            
            self.append_log("Hardware detection completed successfully")
            self.hardware_detected.emit({"specs": specs, "recommendations": recommendations})
            
        except Exception as e:
            error_msg = f"Hardware detection failed: {e}"
            self.hardware_info_text.setText(f"❌ {error_msg}")
            self.status_label.setText(f"❌ {error_msg}")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.append_log(error_msg)
            
    def validate_inputs(self) -> bool:
        """Validate hardware settings inputs."""
        # Hardware tab is now read-only, so always valid
        return True 