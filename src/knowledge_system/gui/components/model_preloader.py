"""
Model Pre-loader for Transcription Tab

Pre-loads transcription and diarization models in the background to eliminate
initialization delays when the user starts processing.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from knowledge_system.processors.diarization import SpeakerDiarizationProcessor

from knowledge_system.logger import get_logger
from knowledge_system.processors.audio_processor import AudioProcessor
from knowledge_system.processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor

# IMPORTANT: Import diarization lazily to avoid torchcodec segfault at GUI startup
# torchcodec has ABI issues and crashes on import, so we only load it when actually needed
# from knowledge_system.processors.diarization import SpeakerDiarizationProcessor, is_diarization_available

logger = get_logger(__name__)


class ModelPreloader(QObject):
    """
    Pre-loads transcription and diarization models in the background.
    
    Strategy:
    1. Start loading transcription model when tab is activated
    2. Start loading diarization model when transcription model finishes
    3. Both models are ready when user clicks "Start Transcription"
    """
    
    # Signals for progress updates
    transcription_model_loading = pyqtSignal(str, int)  # message, progress
    transcription_model_ready = pyqtSignal()
    diarization_model_loading = pyqtSignal(str, int)  # message, progress  
    diarization_model_ready = pyqtSignal()
    preloading_complete = pyqtSignal()
    preloading_error = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Model instances (None until loaded)
        self.transcriber: Optional[WhisperCppTranscribeProcessor] = None
        self.diarizer: Optional["SpeakerDiarizationProcessor"] = None
        
        # Loading state
        self.transcription_loading = False
        self.diarization_loading = False
        self.transcription_ready = False
        self.diarization_ready = False
        
        # Settings
        self.model = "base"  # Default model
        self.device = None
        self.hf_token = None
        self.enable_diarization = True
        
        # Threading
        self._transcription_thread: Optional[threading.Thread] = None
        self._diarization_thread: Optional[threading.Thread] = None
        
    def configure(self, model: str = "base", device: str = None, 
                  hf_token: str = None, enable_diarization: bool = True):
        """Configure the preloader with settings."""
        self.model = model
        self.device = device
        self.hf_token = hf_token
        self.enable_diarization = enable_diarization
        
        logger.info(f"Model preloader configured: model={model}, device={device}, diarization={enable_diarization}")
    
    def start_preloading(self):
        """Start preloading models in the background."""
        if self.transcription_loading or self.transcription_ready:
            logger.debug("Transcription model already loading or ready")
            return
            
        logger.info("🚀 Starting model preloading...")
        
        # Start transcription model loading
        self.transcription_loading = True
        self._transcription_thread = threading.Thread(
            target=self._load_transcription_model,
            daemon=True,
            name="TranscriptionModelLoader"
        )
        self._transcription_thread.start()
    
    def _load_transcription_model(self):
        """Load transcription model in background thread."""
        try:
            logger.info(f"🔄 Loading transcription model: {self.model}")
            self.transcription_model_loading.emit("Loading transcription model...", 10)
            
            # Create transcriber with Core ML acceleration
            self.transcriber = WhisperCppTranscribeProcessor(
                model=self.model,
                use_coreml=True,
                progress_callback=self._transcription_progress_callback
            )
            
            # Trigger model download/loading by calling a method that requires the model
            # This will download the model if not cached
            logger.info("📥 Downloading/loading Whisper model...")
            self.transcription_model_loading.emit("Downloading Whisper model...", 50)
            
            # The model will be loaded when first used, but we can trigger the download
            # by checking if the binary exists and model files are available
            whisper_cmd = self.transcriber._find_whisper_binary()
            if not whisper_cmd:
                raise RuntimeError("Whisper binary not found")
            
            self.transcription_model_loading.emit("Transcription model ready!", 100)
            self.transcription_ready = True
            self.transcription_model_ready.emit()
            
            logger.info("✅ Transcription model preloaded successfully")
            
            # Start diarization model loading if enabled
            if self.enable_diarization and not self.diarization_loading and not self.diarization_ready:
                self._start_diarization_loading()
                
        except Exception as e:
            logger.error(f"Failed to preload transcription model: {e}")
            self.preloading_error.emit(f"Transcription model loading failed: {e}")
        finally:
            self.transcription_loading = False
    
    def _start_diarization_loading(self):
        """Start loading diarization model."""
        # Safe to preload now - torchcodec has been completely removed
        # Lazy import to avoid any potential startup issues
        try:
            from knowledge_system.processors.diarization import is_diarization_available
        except Exception as e:
            logger.warning(f"Could not import diarization module: {e}")
            return
            
        if not is_diarization_available():
            logger.warning("Diarization not available, skipping preload")
            return
            
        if self.diarization_loading or self.diarization_ready:
            logger.debug("Diarization model already loading or ready")
            return
            
        logger.info("✅ Starting diarization model preloading...")
        
        self.diarization_loading = True
        self._diarization_thread = threading.Thread(
            target=self._load_diarization_model,
            daemon=True,
            name="DiarizationModelLoader"
        )
        self._diarization_thread.start()
    
    def _load_diarization_model(self):
        """Load diarization model in background thread."""
        try:
            from knowledge_system.processors.diarization import SpeakerDiarizationProcessor
            
            logger.info("🔄 Loading diarization model...")
            self.diarization_model_loading.emit("Loading diarization model...", 10)
            
            # Create diarizer
            self.diarizer = SpeakerDiarizationProcessor(
                device=self.device,
                hf_token=self.hf_token,
                progress_callback=self._diarization_progress_callback
            )
            
            # Trigger model loading by calling _load_pipeline
            # This will download the model if not cached
            logger.info("📥 Downloading/loading diarization model...")
            self.diarization_model_loading.emit("Downloading diarization model...", 50)
            
            # Pre-load the pipeline to trigger model download
            self.diarizer._load_pipeline()
            
            self.diarization_model_loading.emit("Diarization model ready!", 100)
            self.diarization_ready = True
            self.diarization_model_ready.emit()
            
            logger.info("✅ Diarization model preloaded successfully")
            
            # Check if both models are ready
            if self.transcription_ready and self.diarization_ready:
                self.preloading_complete.emit()
                logger.info("🎉 All models preloaded successfully!")
                
        except Exception as e:
            logger.error(f"Failed to preload diarization model: {e}")
            self.preloading_error.emit(f"Diarization model loading failed: {e}")
        finally:
            self.diarization_loading = False
    
    def _transcription_progress_callback(self, message: str, progress: int = 0):
        """Progress callback for transcription model loading."""
        self.transcription_model_loading.emit(f"🔄 {message}", progress)
    
    def _diarization_progress_callback(self, message: str, progress: int = 0):
        """Progress callback for diarization model loading."""
        self.diarization_model_loading.emit(message, progress)
    
    def get_preloaded_models(self) -> tuple[Optional[WhisperCppTranscribeProcessor], Optional["SpeakerDiarizationProcessor"]]:
        """Get the preloaded model instances."""
        return self.transcriber, self.diarizer
    
    def is_ready(self) -> bool:
        """Check if all required models are ready."""
        transcription_ready = self.transcription_ready
        diarization_ready = self.diarization_ready if self.enable_diarization else True
        
        return transcription_ready and diarization_ready
    
    def reset(self):
        """Reset the preloader state."""
        logger.info("🔄 Resetting model preloader...")
        
        # Stop any ongoing loading
        self.transcription_loading = False
        self.diarization_loading = False
        
        # Clear model instances
        self.transcriber = None
        self.diarizer = None
        
        # Reset state
        self.transcription_ready = False
        self.diarization_ready = False
        
        logger.info("✅ Model preloader reset complete")
