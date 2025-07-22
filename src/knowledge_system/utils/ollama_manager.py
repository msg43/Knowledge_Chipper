"""Ollama service and model management utilities."""

import json
import requests
import subprocess
import time
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import platform
from dataclasses import dataclass
import shutil
import tempfile
import os

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModelInfo:
    """Information about an Ollama model."""
    name: str
    size_bytes: int
    size_display: str
    modified_at: Optional[str] = None
    family: str = ""
    format: str = ""
    parameters: str = ""
    quantization: str = ""


@dataclass
class DownloadProgress:
    """Download progress information."""
    status: str
    completed: int = 0
    total: int = 0
    percent: float = 0.0
    speed_mbps: float = 0.0
    eta_seconds: Optional[int] = None


@dataclass 
class InstallationProgress:
    """Installation progress information."""
    status: str
    completed: int = 0
    total: int = 0
    percent: float = 0.0
    current_step: str = ""


class OllamaManager:
    """Manages Ollama service and model operations."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30
        
    def is_installed(self) -> Tuple[bool, Optional[str]]:
        """Check if Ollama is installed and return the path if found."""
        ollama_paths = [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama", 
            "/Applications/Ollama.app/Contents/Resources/ollama"
        ]
        
        for path in ollama_paths:
            if Path(path).exists():
                return True, path
                
        # Also check if it's in PATH
        ollama_in_path = shutil.which("ollama")
        if ollama_in_path:
            return True, ollama_in_path
            
        return False, None
        
    def is_service_running(self) -> bool:
        """Check if Ollama service is running."""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def install_ollama_macos(self, progress_callback=None) -> Tuple[bool, str]:
        """Install Ollama on macOS by downloading and running the installer."""
        try:
            if progress_callback:
                progress_callback(InstallationProgress(
                    status="downloading", 
                    percent=0.0,
                    current_step="Downloading Ollama installer..."
                ))

            # Download URL for macOS
            download_url = "https://ollama.com/download/Ollama-darwin.zip"
            
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "Ollama-darwin.zip"
                
                # Download the installer
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                percent = (downloaded / total_size) * 50  # First 50% is download
                                progress_callback(InstallationProgress(
                                    status="downloading",
                                    completed=downloaded,
                                    total=total_size,
                                    percent=percent,
                                    current_step=f"Downloading... {downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB"
                                ))
                
                if progress_callback:
                    progress_callback(InstallationProgress(
                        status="extracting",
                        percent=60.0,
                        current_step="Extracting installer..."
                    ))
                
                # Extract the zip
                subprocess.run(['unzip', '-q', str(zip_path), '-d', temp_dir], check=True)
                
                if progress_callback:
                    progress_callback(InstallationProgress(
                        status="installing",
                        percent=80.0, 
                        current_step="Installing Ollama.app..."
                    ))
                
                # Find the Ollama.app and copy to Applications
                ollama_app = Path(temp_dir) / "Ollama.app"
                if not ollama_app.exists():
                    return False, "Ollama.app not found in downloaded package"
                
                # Copy to Applications folder
                apps_dir = Path("/Applications")
                target_app = apps_dir / "Ollama.app"
                
                # Remove existing installation if present
                if target_app.exists():
                    shutil.rmtree(target_app)
                
                shutil.copytree(ollama_app, target_app)
                
                if progress_callback:
                    progress_callback(InstallationProgress(
                        status="installing",
                        percent=90.0,
                        current_step="Setting up command line tools..."
                    ))
                
                # Create symlink for command line access
                cli_path = target_app / "Contents" / "Resources" / "ollama"
                symlink_path = Path("/usr/local/bin/ollama")
                
                # Ensure /usr/local/bin exists
                symlink_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Remove existing symlink if present
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                
                # Create new symlink
                symlink_path.symlink_to(cli_path)
                
                if progress_callback:
                    progress_callback(InstallationProgress(
                        status="completed",
                        percent=100.0,
                        current_step="Installation completed successfully!"
                    ))
                
                return True, "Ollama installed successfully"
                
        except Exception as e:
            logger.error(f"Failed to install Ollama: {e}")
            return False, f"Installation failed: {str(e)}"
    
    def start_service(self) -> Tuple[bool, str]:
        """Start Ollama service."""
        if self.is_service_running():
            return True, "Ollama service is already running"
        
        # Check if Ollama is installed
        is_installed, ollama_cmd = self.is_installed()
        if not is_installed or ollama_cmd is None:
            return False, "OLLAMA_NOT_INSTALLED"
        
        try:
            # Start Ollama service in background
            subprocess.Popen([ollama_cmd, "serve"], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # Wait for service to start
            for _ in range(10):  # Wait up to 10 seconds
                if self.is_service_running():
                    return True, "Ollama service started successfully"
                time.sleep(1)
                
            return False, "Ollama service failed to start within 10 seconds"
            
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")
            return False, f"Failed to start Ollama: {str(e)}"
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of models available in Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                name = model_data.get("name", "")
                size_bytes = model_data.get("size", 0)
                size_display = self._format_size(size_bytes)
                
                model_info = ModelInfo(
                    name=name,
                    size_bytes=size_bytes,
                    size_display=size_display,
                    modified_at=model_data.get("modified_at"),
                    family=model_data.get("details", {}).get("family", ""),
                    format=model_data.get("details", {}).get("format", ""),
                    parameters=model_data.get("details", {}).get("parameter_size", ""),
                    quantization=model_data.get("details", {}).get("quantization_level", "")
                )
                models.append(model_info)
            
            return models
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available locally."""
        models = self.get_available_models()
        return any(model.name == model_name for model in models)
    
    def get_model_info_from_registry(self, model_name: str) -> Optional[ModelInfo]:
        """Get model information from Ollama registry (before download)."""
        try:
            # This is a simplified version - in reality, Ollama doesn't have a public registry API
            # But we can estimate sizes for known popular models
            model_sizes = {
                # 128K Context Models
                "phi3:mini-128k": 2_300_000_000,     # ~2.3GB - 3.8B params, 128K context
                "llama3.1:8b-instruct": 4_700_000_000,  # ~4.7GB - 8B params, 128K context
                "mistral:7b-instruct-v0.3": 4_100_000_000,   # ~4.1GB - 7B params, 128K context
                
                # High-performance models
                "qwen2.5:72b-instruct-q6_K": 54_000_000_000,  # ~54GB
                "qwen2.5:72b-instruct-q4_K_M": 41_000_000_000,  # ~41GB
                "llama3.1:70b-instruct-q6_K": 53_000_000_000,  # ~53GB
                "llama3.1:70b-instruct-q4_K_M": 40_000_000_000,  # ~40GB
                
                # Standard models
                "llama3.2:8b": 4_700_000_000,  # ~4.7GB
                "llama3.2:3b": 2_000_000_000,  # ~2GB
                "mistral:7b": 4_100_000_000,   # ~4.1GB
                "mixtral:8x7b": 26_000_000_000, # ~26GB
                "codellama:13b": 7_300_000_000,  # ~7.3GB
                "phi3:mini": 2_300_000_000,     # ~2.3GB
            }
            
            estimated_size = model_sizes.get(model_name, 5_000_000_000)  # Default 5GB
            
            return ModelInfo(
                name=model_name,
                size_bytes=estimated_size,
                size_display=self._format_size(estimated_size),
                family="Unknown",
                format="GGUF",
                parameters="Unknown",
                quantization=self._extract_quantization(model_name)
            )
            
        except Exception as e:
            logger.error(f"Failed to get model registry info: {e}")
            return None
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Download a model with progress tracking."""
        try:
            url = f"{self.base_url}/api/pull"
            payload = {"name": model_name, "stream": True}
            
            response = requests.post(url, json=payload, stream=True, timeout=3600)  # 1 hour timeout
            response.raise_for_status()
            
            total_size = None
            downloaded = 0
            start_time = time.time()
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        status = data.get("status", "")
                        
                        if progress_callback:
                            if "total" in data and "completed" in data:
                                total_size = data["total"]
                                downloaded = data["completed"]
                                
                                percent = (downloaded / total_size * 100) if total_size > 0 else 0
                                elapsed = time.time() - start_time
                                speed_mbps = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                                
                                eta = None
                                if speed_mbps > 0 and total_size:
                                    remaining_mb = (total_size - downloaded) / (1024 * 1024)
                                    eta = int(remaining_mb / speed_mbps)
                                
                                progress = DownloadProgress(
                                    status=status,
                                    completed=downloaded,
                                    total=total_size or 0,
                                    percent=percent,
                                    speed_mbps=speed_mbps,
                                    eta_seconds=eta
                                )
                                progress_callback(progress)
                            else:
                                # Status-only update
                                progress = DownloadProgress(status=status)
                                progress_callback(progress)
                        
                        # Check for completion
                        if "success" in data or status == "success":
                            if progress_callback:
                                progress_callback(DownloadProgress(status="completed", percent=100.0))
                            return True
                            
                    except json.JSONDecodeError:
                        continue
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            return False
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _extract_quantization(self, model_name: str) -> str:
        """Extract quantization info from model name."""
        if "q8" in model_name.lower():
            return "Q8"
        elif "q6_k" in model_name.lower():
            return "Q6_K"
        elif "q4_k_m" in model_name.lower():
            return "Q4_K_M"
        elif "q4" in model_name.lower():
            return "Q4"
        elif "q2" in model_name.lower():
            return "Q2"
        return "Unknown"


# Global instance
_ollama_manager = None

def get_ollama_manager() -> OllamaManager:
    """Get global Ollama manager instance."""
    global _ollama_manager
    if _ollama_manager is None:
        from knowledge_system.config import get_settings
        settings = get_settings()
        _ollama_manager = OllamaManager(settings.local_config.base_url)
    return _ollama_manager 