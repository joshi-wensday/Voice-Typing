"""Model management for NVIDIA Canary STT models.

Models are cached by NeMo/HuggingFace in  ~/.cache/huggingface/hub/
No manual download step is required — models auto-download on first preload().
"""

from __future__ import annotations

import os
import shutil
import subprocess
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ModelInfo:
    """Information about a Canary STT model."""
    name: str          # HuggingFace model ID  e.g. "nvidia/canary-qwen-2.5b"
    size_gb: float     # Approximate download size
    parameters: str    # Parameter count
    description: str
    is_installed: bool = False
    local_path: Optional[Path] = None


class ModelManager:
    """Manages Canary model discovery and cache directory operations."""

    # Curated list of supported Canary models
    AVAILABLE_MODELS: dict[str, ModelInfo] = {
        "nvidia/canary-qwen-2.5b": ModelInfo(
            name="nvidia/canary-qwen-2.5b",
            size_gb=5.0,
            parameters="2.5B",
            description="Best quality — SALM architecture with Qwen-2.5 LLM decoder. Requires CUDA.",
        ),
        "nvidia/canary-1b": ModelInfo(
            name="nvidia/canary-1b",
            size_gb=2.0,
            parameters="1B",
            description="High quality — encoder-decoder (EncDecMultiTask). CUDA recommended.",
        ),
        "nvidia/canary-1b-flash": ModelInfo(
            name="nvidia/canary-1b-flash",
            size_gb=2.0,
            parameters="1B",
            description="Fast variant of canary-1b, optimised for low-latency streaming.",
        ),
        "nvidia/canary-1b-v2": ModelInfo(
            name="nvidia/canary-1b-v2",
            size_gb=2.0,
            parameters="1B",
            description="Updated canary-1b with improved accuracy on diverse accents.",
        ),
    }

    def __init__(self) -> None:
        # NeMo / HuggingFace shared cache
        self.cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_available_models(self) -> List[ModelInfo]:
        """Return all supported models, marking which are already cached."""
        installed_names = {m.name for m in self.list_installed_models()}
        result = []
        for key, info in self.AVAILABLE_MODELS.items():
            result.append(
                ModelInfo(
                    name=info.name,
                    size_gb=info.size_gb,
                    parameters=info.parameters,
                    description=info.description,
                    is_installed=key in installed_names,
                )
            )
        return result

    def list_installed_models(self) -> List[ModelInfo]:
        """Return models whose HuggingFace cache directory exists locally."""
        installed = []
        if not self.cache_dir.exists():
            return installed

        for item in self.cache_dir.iterdir():
            if not item.is_dir():
                continue
            # HuggingFace stores model dirs as "models--{org}--{name}"
            for key, info in self.AVAILABLE_MODELS.items():
                slug = key.replace("/", "--")
                if item.name == f"models--{slug}" or slug in item.name:
                    installed.append(
                        ModelInfo(
                            name=info.name,
                            size_gb=info.size_gb,
                            parameters=info.parameters,
                            description=info.description,
                            is_installed=True,
                            local_path=item,
                        )
                    )
                    break
        return installed

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Look up a model by its HuggingFace ID."""
        return self.AVAILABLE_MODELS.get(model_name)

    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Trigger a NeMo/HuggingFace download for *model_name*.

        The actual download happens via ``SALM.from_pretrained()`` (or
        ``EncDecMultiTaskModel.from_pretrained()`` for the 1B variants).
        This method simply instantiates the engine, which causes NeMo to pull
        the weights into the HuggingFace cache.
        """
        if model_name not in self.AVAILABLE_MODELS:
            if progress_callback:
                progress_callback(f"Unknown model: {model_name}")
            return False

        try:
            if progress_callback:
                progress_callback(f"Downloading {model_name} — this may take several minutes...")

            if "qwen" in model_name.lower():
                from nemo.collections.speechlm2.models import SALM  # type: ignore[import]
                SALM.from_pretrained(model_name)
            else:
                from nemo.collections.asr.models import EncDecMultiTaskModel  # type: ignore[import]
                EncDecMultiTaskModel.from_pretrained(model_name)

            if progress_callback:
                progress_callback(f"✓ {model_name} downloaded successfully.")
            return True

        except Exception as exc:
            if progress_callback:
                progress_callback(f"Error downloading {model_name}: {exc}")
            return False

    def delete_model(self, model_name: str) -> bool:
        """Delete the local cache directory for *model_name*."""
        for model in self.list_installed_models():
            if model.name == model_name and model.local_path:
                try:
                    shutil.rmtree(model.local_path)
                    return True
                except Exception:
                    return False
        return False

    def get_model_directory(self) -> Path:
        """Return the HuggingFace hub cache directory."""
        return self.cache_dir

    def open_model_directory(self) -> bool:
        """Open the model cache directory in the system file explorer."""
        try:
            path = str(self.cache_dir)
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False
