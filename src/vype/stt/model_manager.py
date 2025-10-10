"""Model management for Whisper STT models."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    import requests
except ImportError:
    requests = None  # Optional dependency

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # Optional dependency


@dataclass
class ModelInfo:
    """Information about a Whisper model."""
    name: str
    size_mb: int
    parameters: str
    relative_speed: str
    accuracy: str
    description: str
    is_installed: bool = False
    local_path: Optional[Path] = None


class ModelManager:
    """Manages Whisper model discovery, download, and installation."""
    
    # Curated list of recommended models
    AVAILABLE_MODELS = {
        "tiny": ModelInfo(
            name="tiny",
            size_mb=75,
            parameters="39M",
            relative_speed="~32x",
            accuracy="Good",
            description="Fastest model, good for quick testing and low-end CPUs"
        ),
        "tiny.en": ModelInfo(
            name="tiny.en",
            size_mb=75,
            parameters="39M",
            relative_speed="~32x",
            accuracy="Good",
            description="English-only tiny model, slightly better accuracy for English"
        ),
        "base": ModelInfo(
            name="base",
            size_mb=145,
            parameters="74M",
            relative_speed="~16x",
            accuracy="Better",
            description="Balanced speed/accuracy, recommended for most users"
        ),
        "base.en": ModelInfo(
            name="base.en",
            size_mb=145,
            parameters="74M",
            relative_speed="~16x",
            accuracy="Better",
            description="English-only base model, good balance"
        ),
        "small": ModelInfo(
            name="small",
            size_mb=490,
            parameters="244M",
            relative_speed="~6x",
            accuracy="High",
            description="Higher accuracy, suitable for capable CPUs and GPUs"
        ),
        "small.en": ModelInfo(
            name="small.en",
            size_mb=490,
            parameters="244M",
            relative_speed="~6x",
            accuracy="High",
            description="English-only small model, higher accuracy"
        ),
        "medium": ModelInfo(
            name="medium",
            size_mb=1500,
            parameters="769M",
            relative_speed="~2x",
            accuracy="Very High",
            description="Excellent accuracy, requires GPU for real-time performance"
        ),
        "medium.en": ModelInfo(
            name="medium.en",
            size_mb=1500,
            parameters="769M",
            relative_speed="~2x",
            accuracy="Very High",
            description="English-only medium model, excellent accuracy"
        ),
        "large-v2": ModelInfo(
            name="large-v2",
            size_mb=3100,
            parameters="1550M",
            relative_speed="~1x",
            accuracy="Best",
            description="Best accuracy, requires powerful GPU"
        ),
        "large-v3": ModelInfo(
            name="large-v3",
            size_mb=3100,
            parameters="1550M",
            relative_speed="~1x",
            accuracy="Best",
            description="Latest large model with improvements, requires powerful GPU"
        ),
    }
    
    def __init__(self):
        """Initialize the model manager."""
        # Model directory is managed by faster-whisper (typically ~/.cache/huggingface/hub/)
        self.cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def list_installed_models(self) -> List[ModelInfo]:
        """List all currently installed models.
        
        Returns:
            List of ModelInfo for installed models
        """
        installed = []
        
        # Check cache directory for model folders
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.is_dir() and "whisper" in item.name.lower():
                    # Try to extract model name from directory
                    for model_name, model_info in self.AVAILABLE_MODELS.items():
                        if model_name in item.name or model_name.replace(".", "-") in item.name:
                            info = ModelInfo(
                                name=model_info.name,
                                size_mb=model_info.size_mb,
                                parameters=model_info.parameters,
                                relative_speed=model_info.relative_speed,
                                accuracy=model_info.accuracy,
                                description=model_info.description,
                                is_installed=True,
                                local_path=item
                            )
                            installed.append(info)
                            break
        
        return installed
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a specific model.
        
        Args:
            model_name: Name of the model (e.g., 'base', 'large-v2')
        
        Returns:
            ModelInfo if model exists, None otherwise
        """
        return self.AVAILABLE_MODELS.get(model_name)
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of all available models for download.
        
        Returns:
            List of all available ModelInfo
        """
        # Mark which ones are installed
        installed_names = {m.name for m in self.list_installed_models()}
        
        models = []
        for name, info in self.AVAILABLE_MODELS.items():
            model_copy = ModelInfo(
                name=info.name,
                size_mb=info.size_mb,
                parameters=info.parameters,
                relative_speed=info.relative_speed,
                accuracy=info.accuracy,
                description=info.description,
                is_installed=name in installed_names,
                local_path=None
            )
            models.append(model_copy)
        
        return models
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Download a model using faster-whisper's built-in download.
        
        Args:
            model_name: Name of the model to download
            progress_callback: Optional callback function for progress updates
        
        Returns:
            True if download successful, False otherwise
        """
        try:
            # Use faster-whisper to download the model
            # It will handle caching automatically
            from faster_whisper import WhisperModel
            
            # This will download if not present
            if progress_callback:
                progress_callback(f"Downloading {model_name}...")
            
            # Create a temporary model instance to trigger download
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            
            if progress_callback:
                progress_callback(f"Model {model_name} downloaded successfully!")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error downloading {model_name}: {str(e)}")
            return False
    
    def download_from_url(self, url: str, model_name: str, progress_callback=None) -> bool:
        """Download a model from a custom URL (e.g., HuggingFace).
        
        Args:
            url: URL to download from
            model_name: Name to save the model as
            progress_callback: Optional callback for progress
        
        Returns:
            True if successful, False otherwise
        """
        if requests is None:
            if progress_callback:
                progress_callback("Error: requests library not installed")
            return False
        
        try:
            if progress_callback:
                progress_callback(f"Downloading from {url}...")
            
            # Download with progress
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            # Save to cache directory
            model_path = self.cache_dir / f"models--{model_name}"
            model_path.mkdir(parents=True, exist_ok=True)
            
            file_path = model_path / "pytorch_model.bin"
            
            with open(file_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                progress_callback(f"Downloading... {progress}%")
            
            if progress_callback:
                progress_callback("Download complete!")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """Delete an installed model.
        
        Args:
            model_name: Name of the model to delete
        
        Returns:
            True if deleted successfully, False otherwise
        """
        installed = self.list_installed_models()
        for model in installed:
            if model.name == model_name and model.local_path:
                try:
                    shutil.rmtree(model.local_path)
                    return True
                except Exception:
                    return False
        return False
    
    def get_model_directory(self) -> Path:
        """Get the directory where models are stored.
        
        Returns:
            Path to model directory
        """
        return self.cache_dir
    
    def open_model_directory(self) -> bool:
        """Open the model directory in file explorer.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            import subprocess
            import platform
            
            path = str(self.cache_dir)
            
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(['open', path])
            else:  # Linux
                subprocess.Popen(['xdg-open', path])
            
            return True
        except Exception:
            return False

